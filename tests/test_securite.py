"""Tests de la connexion (logigramme 2) et des sauvegardes."""
from datetime import datetime, timedelta

import auth
import base
import config
import portefeuille


def test_mot_de_passe_trop_court():
    ok, message = auth.creer_compte("client", "court", "court")
    assert not ok and "8 caractères" in message


def test_mot_de_passe_jamais_enregistre_en_clair():
    auth.creer_compte("client", "MotDePasse2026", "MotDePasse2026")
    with base.ouvrir() as con:
        compte = con.execute("SELECT * FROM utilisateur").fetchone()
    assert "MotDePasse2026" not in compte["hash"]


def test_connexion_reussie():
    auth.creer_compte("client", "MotDePasse2026", "MotDePasse2026")
    assert auth.verifier("client", "MotDePasse2026") == (True, "Connexion réussie.")


def test_blocage_apres_5_essais_rates():
    auth.creer_compte("client", "MotDePasse2026", "MotDePasse2026")
    maintenant = datetime(2026, 11, 25, 10, 0)
    for _ in range(4):
        assert auth.verifier("client", "faux", maintenant) == (False, "Identifiant ou mot de passe incorrect.")
    ok, message = auth.verifier("client", "faux", maintenant)
    assert not ok and "bloqué 15 minutes" in message

    # Même le bon mot de passe est refusé pendant le blocage
    ok, message = auth.verifier("client", "MotDePasse2026", maintenant + timedelta(minutes=5))
    assert not ok and "réessayez dans 10 min" in message

    # Après 15 minutes, la connexion fonctionne à nouveau
    ok, _ = auth.verifier("client", "MotDePasse2026", maintenant + timedelta(minutes=16))
    assert ok


def test_sauvegarde_quotidienne():
    copie = base.sauvegarder()
    assert copie.exists()
    assert copie.parent == config.DOSSIER_SAUVEGARDES


def test_recreer_compte_avec_code_de_recuperation():
    auth.creer_compte("client", "MotDePasse2026", "MotDePasse2026")
    code = auth.nouveau_code_recuperation()
    portefeuille.passer_ordre("AI.PA", "achat", 10, 200.0, 0.001)
    ok, message = auth.recreer_compte("FAUX-CODE-0000", "nouveau", "Nouveau2026!", "Nouveau2026!", True)
    assert not ok and message == "Code de récupération incorrect."
    ok, _ = auth.recreer_compte(code.lower().replace("-", " "), "nouveau", "Nouveau2026!", "Nouveau2026!", True)
    assert ok
    assert auth.verifier("nouveau", "Nouveau2026!")[0]
    assert not portefeuille.lire_ordres().empty                      # portefeuille conservé
    assert list(config.DOSSIER_SAUVEGARDES.glob("avant_recreation_*.db"))
    ok, _ = auth.recreer_compte(code, "autre", "Autre2026!!", "Autre2026!!", True)
    assert not ok                                                     # le code ne sert qu'une fois


def test_recreer_compte_et_repartir_de_zero():
    auth.creer_compte("client", "MotDePasse2026", "MotDePasse2026")
    code = auth.nouveau_code_recuperation()
    base.choisir_profil("Dynamique")
    portefeuille.passer_ordre("AI.PA", "achat", 10, 200.0, 0.001)
    ok, message = auth.recreer_compte(code, "neuf", "Nouveau2026!", "Nouveau2026!", False)
    assert ok and "500 000" in message
    assert portefeuille.lire_ordres().empty
    assert base.lire_reglages()["profil"] == config.PROFIL_DEFAUT


def test_sauvegarde_et_restauration():
    auth.creer_compte("client", "MotDePasse2026", "MotDePasse2026")
    portefeuille.passer_ordre("AI.PA", "achat", 10, 200.0, 0.001)
    sauvegarde = base.exporter_base()
    base.reinitialiser_portefeuille()
    assert portefeuille.lire_ordres().empty
    assert base.restaurer_base(sauvegarde) == (True, "Sauvegarde restaurée.")
    assert len(portefeuille.lire_ordres()) == 1
    assert base.restaurer_base(b"pas une base")[0] is False
