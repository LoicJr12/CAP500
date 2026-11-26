"""Tests des ordres (A7), de la protection contre les pertes (A8) et de la répartition."""
import sqlite3

import pytest

import base
import config
import portefeuille


def texte(message: str) -> str:
    """Remplace les espaces insécables par des espaces simples pour comparer les messages."""
    return message.replace("\u202f", " ").replace("\u00a0", " ")

TAUX = 0.001


def test_achat_puis_vente(uid):
    ok, message = portefeuille.passer_ordre(uid, "AI.PA", "achat", 100, 200.0, TAUX)
    assert ok and "Ordre enregistré" in texte(message)
    assert portefeuille.positions(uid)["AI.PA"]["quantite"] == 100
    assert portefeuille.liquidites(uid) == pytest.approx(config.CAPITAL - 20_000 - 20)
    ok, _ = portefeuille.passer_ordre(uid, "AI.PA", "vente", 40, 210.0, TAUX)
    assert ok
    assert portefeuille.positions(uid)["AI.PA"]["quantite"] == 60


def test_achat_refuse_si_liquidites_insuffisantes(uid):           # RG3
    ok, message = portefeuille.passer_ordre(uid, "RMS.PA", "achat", 1000, 1300.0, TAUX)
    assert not ok and texte(message).startswith("Liquidités insuffisantes")


def test_vente_refusee_sans_titres(uid):                          # RG4
    ok, message = portefeuille.passer_ordre(uid, "CAP.PA", "vente", 5, 117.0, TAUX)
    assert not ok and texte(message) == "Vous détenez seulement 0 titre."


@pytest.mark.parametrize("quantite", [0, -3, 2.5])
def test_quantite_invalide(uid, quantite):                          # RG5
    ok, message = portefeuille.passer_ordre(uid, "AI.PA", "achat", quantite, 200.0, TAUX)
    assert not ok and "nombre entier" in texte(message)


def test_action_non_autorisee(uid):                               # RG2
    ok, _ = portefeuille.passer_ordre(uid, "MC.PA", "achat", 1, 400.0, TAUX)
    assert not ok


def test_un_ordre_ne_peut_pas_etre_modifie(uid):
    portefeuille.passer_ordre(uid, "AI.PA", "achat", 10, 200.0, TAUX)
    with pytest.raises(sqlite3.DatabaseError):
        with base.ouvrir() as con:
            con.execute("UPDATE ordres SET quantite = 1")


def test_alerte_a_moins_8_pourcent(uid):                          # A8
    assert portefeuille.passer_ordre(uid, "AI.PA", "achat", 990, 200.0, TAUX)[0]
    assert portefeuille.passer_ordre(uid, "TTE.PA", "achat", 2400, 80.0, TAUX)[0]       # 390 000 € investis
    niveau, message = portefeuille.controler_perte(uid, {"AI.PA": 180.0, "TTE.PA": 70.0}, TAUX)  # environ −8,8 %
    assert niveau == "alerte" and "Attention" in texte(message)
    assert portefeuille.positions(uid)["AI.PA"]["quantite"] == 990


def test_vente_automatique_a_moins_10_pourcent(uid):              # A8 / RG11
    assert portefeuille.passer_ordre(uid, "AI.PA", "achat", 990, 200.0, TAUX)[0]
    assert portefeuille.passer_ordre(uid, "TTE.PA", "achat", 2400, 80.0, TAUX)[0]
    niveau, message = portefeuille.controler_perte(uid, {"AI.PA": 150.0, "TTE.PA": 60.0}, TAUX)  # −19 %
    assert niveau == "vente"
    assert texte(message) == "Limite de 10 % atteinte : toutes vos actions ont été vendues automatiquement."
    assert portefeuille.positions(uid) == {}
    assert portefeuille.lire_ordres(uid)["automatique"].iloc[-1] == 1
    ok, message = portefeuille.passer_ordre(uid, "AI.PA", "achat", 1, 170.0, TAUX)
    assert not ok and "bloqués" in texte(message)


def test_repartition_superieure_au_capital(uid):                  # RG1
    ok, message = portefeuille.repartir(uid, {"AI.PA": 300_000, "TTE.PA": 250_000}, {"AI.PA": 200, "TTE.PA": 80}, TAUX)
    assert not ok and texte(message) == "Le total dépasse votre capital de 50 000,00 €."


def test_repartition_de_depart(uid):
    montants = {"AI.PA": 100_000, "TTE.PA": 100_000, "CAP.PA": 0}
    ok, message = portefeuille.repartir(uid, montants, {"AI.PA": 188.0, "TTE.PA": 80.0, "CAP.PA": 117.0}, TAUX)
    assert ok and "2 actions achetées" in texte(message)
    pos = portefeuille.positions(uid)
    assert pos["AI.PA"]["quantite"] == portefeuille.quantite_possible(100_000, 188.0, TAUX)
    assert portefeuille.liquidites(uid) >= 300_000
    assert portefeuille.depart_fait(uid)
    ok, _ = portefeuille.repartir(uid, montants, {"AI.PA": 188.0, "TTE.PA": 80.0}, TAUX)
    assert not ok   # une seule répartition de départ


def test_reinitialisation(uid):
    portefeuille.passer_ordre(uid, "AI.PA", "achat", 10, 200.0, TAUX)
    base.reinitialiser_portefeuille(uid)
    assert portefeuille.lire_ordres(uid).empty
    assert portefeuille.liquidites(uid) == config.CAPITAL
    with base.ouvrir() as con:                                   # l'ancien ordre reste archivé
        assert con.execute("SELECT COUNT(*) FROM ordres").fetchone()[0] == 1


def test_chaque_compte_a_son_portefeuille(uid):
    import auth
    _, _, autre = auth.creer_compte("autre", "AutreMotDePasse", "AutreMotDePasse")
    assert portefeuille.passer_ordre(uid, "AI.PA", "achat", 10, 200.0, TAUX)[0]
    base.choisir_profil(autre, "Prudent")
    assert portefeuille.positions(autre) == {}
    assert portefeuille.liquidites(autre) == config.CAPITAL
    assert base.lire_reglages(uid)["profil"] == config.PROFIL_DEFAUT
    assert base.lire_reglages(autre)["profil"] == "Prudent"


# ---------- Profil de risque ----------
def test_part_maximale_par_action(uid):                           # profil Équilibré : 40 %
    ok, message = portefeuille.passer_ordre(uid, "AI.PA", "achat", 1100, 200.0, TAUX)   # 44 %
    assert not ok and "ne doit pas dépasser 40 %" in texte(message) and "au plus 1 000 titres" in texte(message)


def test_reserve_de_liquidites(uid):                              # profil Prudent : 20 % minimum
    base.choisir_profil(uid, "Prudent")
    for code, qte, prix in [("AI.PA", 600, 200.0), ("TTE.PA", 1500, 80.0), ("CAP.PA", 1000, 117.0)]:
        assert portefeuille.passer_ordre(uid, code, "achat", qte, prix, TAUX)[0]
    ok, message = portefeuille.passer_ordre(uid, "DSY.PA", "achat", 3000, 25.0, TAUX)   # resterait ~12 %
    assert not ok and "gardez au moins 20 %" in texte(message)


def test_vente_automatique_plus_tot_en_profil_prudent(uid):
    base.choisir_profil(uid, "Prudent")
    portefeuille.passer_ordre(uid, "AI.PA", "achat", 600, 200.0, TAUX)
    portefeuille.passer_ordre(uid, "TTE.PA", "achat", 1500, 80.0, TAUX)
    niveau, message = portefeuille.controler_perte(uid, {"AI.PA": 160.0, "TTE.PA": 64.0}, TAUX)   # −9,6 %
    assert niveau == "vente" and texte(message).startswith("Limite de 6 % atteinte")


def test_repartition_respecte_le_profil(uid):
    ok, message = portefeuille.repartir(uid, {"AI.PA": 250_000}, {"AI.PA": 200.0}, TAUX)
    assert not ok and "ne doit pas dépasser 200 000 €" in texte(message)
    ok, message = portefeuille.repartir(uid, {c: 95_000 for c in config.ACTIONS}, {c: 100.0 for c in config.ACTIONS}, TAUX)
    assert not ok and "gardez au moins 50 000 €" in texte(message)


@pytest.mark.parametrize("profil", list(config.PROFILS))
def test_repartition_conseillee_valide(uid, profil):
    base.choisir_profil(uid, profil)
    r = base.lire_reglages(uid)
    scores = {"RMS.PA": 0.9, "AI.PA": 0.3, "TTE.PA": -0.2, "DSY.PA": -1.5, "CAP.PA": 1.5}
    montants = portefeuille.repartition_conseillee(scores, r)
    assert montants["DSY.PA"] == 0                                   # action à vendre exclue
    assert max(montants.values()) <= r["max_par_action"] * config.CAPITAL
    ok, _ = portefeuille.repartir(uid, montants, {c: 100.0 for c in config.ACTIONS}, TAUX)
    assert ok
