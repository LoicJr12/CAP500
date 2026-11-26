"""
Test de l'interface : chaque écran s'affiche sans erreur.
Les téléchargements sont remplacés par des cours fictifs (pas besoin d'internet).
"""
import time

import pytest
from streamlit.testing.v1 import AppTest

import auth
import donnees
import ecrans
import portefeuille
from conftest import RACINE

PAGES = ecrans.PAGES


@pytest.fixture
def appli(cours_fictifs, monkeypatch):
    monkeypatch.setattr(donnees, "telecharger_cours", lambda code, periode="1y": True)
    monkeypatch.setattr(donnees, "telecharger_actualites", lambda code: True)
    ecrans.tout_recalculer()
    auth.creer_compte("client", "MotDePasse2026", "MotDePasse2026")
    yield
    ecrans.tout_recalculer()


def lancer(page: str) -> AppTest:
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=60)
    at.session_state["connecte"] = True
    at.session_state["identifiant"] = "client"
    at.session_state["derniere_activite"] = time.time()
    at.session_state["page"] = page
    at.run()
    return at


def test_ecran_de_connexion(appli):
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=60).run()
    assert not at.exception
    assert at.button or at.get("form_submit_button")
    assert any("Se connecter" in t.label for t in at.tabs)


@pytest.mark.parametrize("page", PAGES)
def test_chaque_ecran_s_affiche(appli, page):
    at = lancer(page)
    assert not at.exception, at.exception


def test_ecrans_avec_portefeuille_rempli(appli, cours_fictifs):
    prix = donnees.cours_actuels()
    ok, _ = portefeuille.repartir({"AI.PA": 100_000, "CAP.PA": 100_000}, prix, 0.001)
    assert ok
    for page in PAGES:
        at = lancer(page)
        assert not at.exception, (page, at.exception)


def test_parcours_profil_puis_repartition_avec_virgule(appli, cours_fictifs):
    at = lancer("Mon profil")
    for i, reponse in enumerate(["J'attends que le marché remonte", "Une croissance régulière",
                                 "Quelques opérations", "Entre 5 et 8 %"]):
        at.radio(key=f"question_{i}").set_value(reponse)
    at.get("form_submit_button")[0].click().run()
    assert not at.exception
    assert any("Profil Équilibré appliqué" in s.value for s in at.success)
    assert at.session_state["page"] == "Répartition de départ"

    at.text_input(key="montant_AI.PA").set_value("100 000,50").run()
    at.text_input(key="montant_TTE.PA").set_value("50 000").run()
    assert not at.exception
    [b for b in at.button if b.label == "Valider la répartition"][0].click().run()
    [b for b in at.button if b.label == "Confirmer"][0].click().run()
    assert not at.exception
    assert any("Portefeuille de départ enregistré" in s.value for s in at.success)
    pos = portefeuille.positions()
    assert set(pos) == {"AI.PA", "TTE.PA"}
