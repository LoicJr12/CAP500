"""
Test de l'interface : chaque écran s'affiche sans erreur et les parcours principaux fonctionnent.
Les téléchargements sont remplacés par des cours fictifs (pas besoin d'internet).
"""
import time

import pytest
from streamlit.testing.v1 import AppTest

import auth
import base
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
    yield
    ecrans.tout_recalculer()


def nouvelle_appli() -> AppTest:
    return AppTest.from_file(str(RACINE / "app.py"), default_timeout=60)


def lancer(numero: int, page: str) -> AppTest:
    at = nouvelle_appli()
    at.session_state["connecte"] = True
    at.session_state["uid"] = numero
    at.session_state["identifiant"] = auth.identifiant(numero)
    at.session_state["derniere_activite"] = time.time()
    at.session_state["page"] = page
    at.run()
    return at


def bouton(at: AppTest, libelle: str):
    return next(b for b in list(at.button) + list(at.get("form_submit_button")) if b.label == libelle)


def test_page_de_connexion_propose_les_deux_choix(appli):
    at = nouvelle_appli().run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Se connecter", "Créer un compte"]


def test_creer_un_compte_depuis_la_page_de_connexion(appli):
    at = nouvelle_appli().run()
    at.text_input(key="creation_identifiant").set_value("nouveau.client")
    at.text_input(key="creation_mdp").set_value("MonMotDePasse")
    at.text_input(key="creation_confirmation").set_value("MonMotDePasse")
    bouton(at, "Créer mon compte").click().run()
    assert not at.exception
    assert at.session_state["connecte"] and at.session_state["page"] == "Mon profil"
    assert "code_a_noter" in at.session_state                # le code de récupération est affiché
    at.checkbox[0].check().run()
    bouton(at, "Commencer").click().run()
    assert not at.exception and "code_a_noter" not in at.session_state


def test_connexion_avec_un_compte_existant(appli, uid):
    at = nouvelle_appli().run()
    at.text_input(key="connexion_identifiant").set_value("client")
    at.text_input(key="connexion_mdp").set_value("MotDePasse2026")
    bouton(at, "Se connecter").click().run()
    assert not at.exception
    assert at.session_state["uid"] == uid


@pytest.mark.parametrize("page", PAGES)
def test_chaque_ecran_s_affiche(appli, uid, page):
    at = lancer(uid, page)
    assert not at.exception, at.exception


def test_ecrans_avec_portefeuille_rempli(appli, uid):
    ok, _ = portefeuille.repartir(uid, {"AI.PA": 100_000, "CAP.PA": 100_000}, donnees.cours_actuels(), 0.001)
    assert ok
    for page in PAGES:
        at = lancer(uid, page)
        assert not at.exception, (page, at.exception)
    assert "Investir mon capital" not in at.sidebar.radio[0].options   # étape terminée : retirée du menu


def test_parcours_profil_puis_investissement_avec_virgule(appli, uid):
    at = lancer(uid, "Mon profil")
    for i, reponse in enumerate(["J'attends que le marché remonte", "Une croissance régulière",
                                 "Quelques opérations", "Entre 5 et 8 %"]):
        at.radio(key=f"question_{i}").set_value(reponse)
    bouton(at, "Trouver mon profil").click().run()
    assert not at.exception
    assert any("Profil Équilibré choisi" in s.value for s in at.success)
    assert at.session_state["page"] == "Investir mon capital"

    at.text_input(key="montant_AI.PA").set_value("100 000,50").run()
    at.text_input(key="montant_TTE.PA").set_value("50 000").run()
    assert not at.exception
    bouton(at, "Valider ma répartition").click().run()
    bouton(at, "Oui, investir").click().run()
    assert not at.exception
    assert any("Portefeuille de départ enregistré" in s.value for s in at.success)
    assert set(portefeuille.positions(uid)) == {"AI.PA", "TTE.PA"}


def test_acheter_en_euros(appli, uid):
    base.choisir_profil(uid, "Équilibré")
    at = lancer(uid, "Acheter / vendre")
    at.text_input(key="montant_ordre").set_value("20 000").run()
    bouton(at, "Acheter").click().run()
    bouton(at, "Oui, confirmer").click().run()
    assert not at.exception
    assert any("Ordre enregistré" in s.value for s in at.success)
    assert portefeuille.liquidites(uid) == pytest.approx(500_000 - 20_000, abs=1_000)
