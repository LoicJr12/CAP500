"""Tests des algorithmes A2 (infos), A3 (financier), A4 (hasard), A5 et A6 (moteur)."""
import pandas as pd
import pytest

import config
import donnees
import financier
import hasard
import infos
import moteur
import profil
from affichage import lire_nombre
from conftest import serie_cours
from modele import Argument

REGLAGES = dict(config.REGLAGES_DEFAUT)


# ---------- A2 ----------
def test_potentiel_des_analystes():
    assert infos.note_potentiel(0.20) == 2
    assert infos.note_potentiel(0.10) == 1
    assert infos.note_potentiel(0.00) == 0
    assert infos.note_potentiel(-0.10) == -1
    assert infos.note_potentiel(-0.20) == -2


def test_note_infos_avec_actualites():
    actus = [{"tonalite": 1}, {"tonalite": 1}, {"tonalite": -1}]
    note, arguments, potentiel = infos.note_infos(100, 110, actus)   # potentiel +10 % → +1 ; actus → +0,5
    assert round(potentiel, 2) == 0.10
    assert note == 1.5
    assert len(arguments) == 3


def test_note_infos_sans_objectif():
    note, _, potentiel = infos.note_infos(100, None, [])
    assert note == 0 and potentiel is None


def test_tonalite_des_actualites():
    assert donnees.tonalite("Capgemini relève ses objectifs annuels") == 1
    assert donnees.tonalite("Dassault Systèmes chute après des résultats décevants") == -1
    assert donnees.tonalite("Assemblée générale de Hermès") == 0


# ---------- A3 ----------
def test_ratios_et_note_financiere():
    comptes = donnees.charger_comptes()
    cours = {code: serie_cours(graine=i) for i, code in enumerate(config.ACTIONS)}
    ratios = financier.calculer_ratios(comptes, cours)
    assert list(ratios.index) == list(config.ACTIONS)
    assert ratios["marge_nette"].notna().all()
    for code in config.ACTIONS:
        note, _ = financier.note_financiere(code, ratios)
        assert -2 <= note <= 2


def test_note_financiere_meilleure_entreprise():
    ratios = pd.DataFrame({
        "croissance_ca": [0.10, 0.0], "marge_nette": [0.30, 0.05], "per": [10.0, 30.0],
        "dette_ebitda": [0.5, 3.0], "rendement_total": [0.20, -0.1],
    }, index=["A", "B"])
    assert financier.note_financiere("A", ratios)[0] == 2
    assert financier.note_financiere("B", ratios)[0] == -2


# ---------- A4 ----------
def test_simulation_reproductible():
    cloture = serie_cours()["cloture"]
    a = hasard.simuler(cloture, graine=42)
    b = hasard.simuler(cloture, graine=42)
    assert a["proba_hausse"] == b["proba_hausse"]
    assert a["perte_95"] == b["perte_95"]
    assert 0 <= a["proba_hausse"] <= 1


def test_simulation_trop_risquee_donne_moins_2():
    cloture = serie_cours(volatilite=0.08)["cloture"]   # action très volatile
    resultat = hasard.simuler(cloture, graine=1)
    assert resultat["perte_95"] > config.PERTE_MAX_SIMULATION
    assert hasard.note_hasard(resultat)[0] == -2


# ---------- A5 ----------
def test_recommandation_selon_le_score():
    assert moteur.recommander(1.0, False, REGLAGES) == "Acheter"
    assert moteur.recommander(0.0, True, REGLAGES) == "Ne rien faire"
    assert moteur.recommander(-1.0, True, REGLAGES) == "Vendre"
    assert moteur.recommander(-1.0, False, REGLAGES) == "Ne rien faire"   # règle RG9


def test_calcul_du_score():
    notes = {"graphique": 2, "infos": 1, "financier": 0, "hasard": -1}
    assert round(moteur.calculer_score(notes, REGLAGES), 2) == round(0.8 + 0.25 - 0.15, 2)


# ---------- A6 ----------
def test_phrase_d_argumentation():
    arguments = [
        Argument("une tendance haussière", 1, "graphique"),
        Argument("un objectif des analystes 18 % au-dessus du cours", 2, "infos"),
        Argument("2 actualités positives cette semaine", 1, "infos"),
        Argument("un RSI à 75 (action surachetée)", -1, "graphique"),
    ]
    phrase = moteur.construire_phrase("Acheter", arguments, REGLAGES)
    assert phrase.startswith("Compte tenu d'un objectif")
    assert "nous vous conseillons l'achat" in phrase
    assert "RSI" not in phrase   # un argument contraire n'est pas cité pour justifier un achat


def test_analyse_complete():
    df = serie_cours()
    cours = {code: df for code in config.ACTIONS}
    ratios = financier.calculer_ratios(donnees.charger_comptes(), cours)
    analyse = moteur.analyser("AI.PA", df, ratios, donnees.charger_analystes(), [], REGLAGES, graine=1)
    assert set(analyse.notes) == {"graphique", "infos", "financier", "hasard"}
    assert -2 <= analyse.score <= 2
    conseil, phrase = moteur.conseiller(analyse, False, REGLAGES)
    assert conseil in ("Acheter", "Ne rien faire")
    assert phrase.endswith(".")


# ---------- Saisie des nombres à la française ----------
@pytest.mark.parametrize("texte, attendu", [
    ("12 500,50", 12500.5), ("1.234,5", 1234.5), ("0,25", 0.25), ("150", 150.0), ("−0,5", -0.5),
    ("25 000 €", 25000.0), ("12,5 %", 12.5), ("1\u202f000", 1000.0), ("", None), ("abc", None),
])
def test_lire_nombre(texte, attendu):
    assert lire_nombre(texte) == attendu


def test_profil_questionnaire():
    assert profil.calculer_profil([0, 0, 1, 1]) == "Prudent"
    assert profil.calculer_profil([1, 1, 1, 1]) == "Équilibré"
    assert profil.calculer_profil([2, 2, 1, 2]) == "Dynamique"
