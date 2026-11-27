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


def jeton_de(at: AppTest) -> str:
    """Le jeton de session tel qu'il se trouve dans l'adresse de la page."""
    valeur = at.query_params[ecrans.CLE_JETON]
    return valeur[0] if isinstance(valeur, list) else valeur


def test_rafraichir_la_page_ne_deconnecte_plus(appli, uid):
    """Un F5 ouvre une session Streamlit vierge : seul le jeton de l'adresse subsiste."""
    at = nouvelle_appli().run()
    at.text_input(key="connexion_identifiant").set_value("client")
    at.text_input(key="connexion_mdp").set_value("MotDePasse2026")
    bouton(at, "Se connecter").click().run()
    assert at.session_state["connecte"]
    jeton = jeton_de(at)
    assert jeton

    rechargee = nouvelle_appli()
    rechargee.query_params[ecrans.CLE_JETON] = jeton
    rechargee.run()
    assert not rechargee.exception, rechargee.exception
    assert rechargee.session_state["connecte"]
    assert rechargee.session_state["uid"] == uid


def test_deconnexion_rend_le_jeton_inutilisable(appli, uid):
    """Une adresse copiée ailleurs ne doit plus donner accès au compte après déconnexion."""
    at = nouvelle_appli().run()
    at.text_input(key="connexion_identifiant").set_value("client")
    at.text_input(key="connexion_mdp").set_value("MotDePasse2026")
    bouton(at, "Se connecter").click().run()
    jeton = jeton_de(at)
    bouton(at, "Se déconnecter").click().run()
    assert "connecte" not in at.session_state

    rechargee = nouvelle_appli()
    rechargee.query_params[ecrans.CLE_JETON] = jeton
    rechargee.run()
    assert not rechargee.exception
    assert "connecte" not in rechargee.session_state
    assert [t.label for t in rechargee.tabs] == ["Se connecter", "Créer un compte"]


def test_jeton_inconnu_renvoie_a_la_connexion(appli):
    """Un jeton inventé ou expiré ne connecte personne et disparaît de l'adresse."""
    at = nouvelle_appli()
    at.query_params[ecrans.CLE_JETON] = "jeton-invente"
    at.run()
    assert not at.exception
    assert "connecte" not in at.session_state
    assert ecrans.CLE_JETON not in at.query_params


def test_fiche_action_resiste_a_une_analyse_mise_en_cache_avant_un_champ(appli, uid):
    """
    Les analyses sont gardées en cache : un objet enregistré par une version précédente de
    `modele.Analyse` n'a pas les champs ajoutés depuis. L'écran doit se dégrader, pas planter.
    """
    import pickle

    import donnees
    import financier
    import moteur
    import config as cfg

    df = donnees.lire_cours("AI.PA")
    ratios = financier.calculer_ratios(donnees.charger_comptes(), {"AI.PA": df})
    analyse = moteur.analyser("AI.PA", df, ratios, donnees.charger_analystes(), [],
                              dict(cfg.REGLAGES_DEFAUT), graine=1)
    ancienne = pickle.loads(pickle.dumps(analyse))
    del ancienne.__dict__["analystes"]
    assert ecrans.provenance_objectif(ancienne) == "de hausse attendue · source non renseignée"
    assert "Citi" in ecrans.provenance_objectif(analyse)


def test_la_version_de_la_structure_entre_dans_la_cle_du_cache():
    """Changer la forme de `Analyse` doit invalider les analyses déjà en cache."""
    import inspect

    import modele
    assert "version" in inspect.signature(ecrans.calculer_analyses.__wrapped__).parameters
    assert isinstance(modele.VERSION_ANALYSE, int)


def test_changer_la_periode_du_graphique(appli, uid):
    """Le choix de la période est un radio horizontal : chaque période doit s'afficher sans erreur."""
    at = lancer(uid, "Les actions")
    for periode in ["1 mois", "1 an", "6 mois"]:
        at.radio(key="periode_fiche").set_value(periode).run()
        assert not at.exception, (periode, at.exception)
        assert at.session_state["periode_fiche"] == periode


def test_vendre_en_choisissant_l_operation(appli, uid):
    """Le choix achat / vente est un radio horizontal : la bascule doit mener jusqu'à l'ordre."""
    base.choisir_profil(uid, "Équilibré")
    ok, _ = portefeuille.repartir(uid, {"AI.PA": 100_000}, donnees.cours_actuels(), 0.001)
    assert ok
    detenus = portefeuille.positions(uid)["AI.PA"]["quantite"]

    at = lancer(uid, "Acheter / vendre")
    at.selectbox(key="action_choisie").set_value("AI.PA").run()
    at.radio(key="sens_ordre").set_value("Vendre").run()
    assert not at.exception
    at.radio(key="mode_saisie").set_value("En nombre d'actions").run()
    at.text_input(key="quantite_ordre").set_value("10").run()
    bouton(at, "Vendre").click().run()
    bouton(at, "Oui, confirmer").click().run()
    assert not at.exception
    assert any("Ordre enregistré" in s.value for s in at.success)
    assert portefeuille.positions(uid)["AI.PA"]["quantite"] == detenus - 10


def test_acheter_en_euros(appli, uid):
    base.choisir_profil(uid, "Équilibré")
    at = lancer(uid, "Acheter / vendre")
    at.text_input(key="montant_ordre").set_value("20 000").run()
    bouton(at, "Acheter").click().run()
    bouton(at, "Oui, confirmer").click().run()
    assert not at.exception
    assert any("Ordre enregistré" in s.value for s in at.success)
    assert portefeuille.liquidites(uid) == pytest.approx(500_000 - 20_000, abs=1_000)
