"""Tests des comptes, de la connexion (logigramme 2) et des sauvegardes."""
import json
import sqlite3
from datetime import datetime, timedelta

import auth
import base
import config
import portefeuille

MDP = "MotDePasse2026"


def test_mot_de_passe_trop_court():
    ok, message, _ = auth.creer_compte("client", "court", "court")
    assert not ok and "8 caractères" in message


def test_identifiant_deja_utilise():
    auth.creer_compte("client", MDP, MDP)
    ok, message, _ = auth.creer_compte("Client", MDP, MDP)          # majuscules ignorées
    assert not ok and "déjà utilisé" in message


def test_plusieurs_comptes():
    _, _, a = auth.creer_compte("alice", MDP, MDP)
    _, _, b = auth.creer_compte("bruno", "UnAutreMotDePasse", "UnAutreMotDePasse")
    assert a != b
    assert auth.verifier("alice", MDP)[2] == a
    assert auth.verifier("bruno", "UnAutreMotDePasse")[2] == b
    assert auth.verifier("bruno", MDP)[0] is False


def test_mot_de_passe_jamais_enregistre_en_clair():
    auth.creer_compte("client", MDP, MDP)
    with base.ouvrir() as con:
        compte = con.execute("SELECT * FROM utilisateurs").fetchone()
    assert MDP not in compte["hash"]


def test_connexion_reussie(uid):
    assert auth.verifier("client", MDP) == (True, "Connexion réussie.", uid)


def test_identifiant_inconnu():
    assert auth.verifier("personne", MDP) == (False, auth.ERREUR_CONNEXION, None)


def test_blocage_apres_5_essais_rates(uid):
    maintenant = datetime(2026, 11, 25, 10, 0)
    for _ in range(4):
        assert auth.verifier("client", "faux", maintenant) == (False, auth.ERREUR_CONNEXION, None)
    ok, message, _ = auth.verifier("client", "faux", maintenant)
    assert not ok and "bloqué 15 minutes" in message

    # Même le bon mot de passe est refusé pendant le blocage
    ok, message, _ = auth.verifier("client", MDP, maintenant + timedelta(minutes=5))
    assert not ok and "réessayez dans 10 min" in message

    # Après 15 minutes, la connexion fonctionne à nouveau
    assert auth.verifier("client", MDP, maintenant + timedelta(minutes=16))[0]


def test_mot_de_passe_oublie(uid):
    code = auth.nouveau_code_recuperation(uid)
    portefeuille.passer_ordre(uid, "AI.PA", "achat", 10, 200.0, 0.001)
    ok, message, _ = auth.mot_de_passe_oublie("client", "FAUX-CODE-0000", "Nouveau2026!", "Nouveau2026!")
    assert not ok and "code de récupération incorrect" in message
    ok, _, numero = auth.mot_de_passe_oublie("client", code.lower().replace("-", " "), "Nouveau2026!", "Nouveau2026!")
    assert ok and numero == uid
    assert auth.verifier("client", "Nouveau2026!")[0]
    assert not portefeuille.lire_ordres(uid).empty                  # portefeuille conservé
    ok, _, _ = auth.mot_de_passe_oublie("client", code, "Autre2026!!", "Autre2026!!")
    assert not ok                                                    # le code ne sert qu'une fois


def test_changer_mot_de_passe(uid):
    assert auth.changer_mot_de_passe(uid, "faux", "Nouveau2026!", "Nouveau2026!")[0] is False
    assert auth.changer_mot_de_passe(uid, MDP, "Nouveau2026!", "Nouveau2026!") == (True, "Mot de passe modifié.")
    assert auth.verifier("client", "Nouveau2026!")[0]


def test_sauvegarde_quotidienne():
    copie = base.sauvegarder()
    assert copie.exists()
    assert copie.parent == config.DOSSIER_SAUVEGARDES


def test_export_et_restauration_d_un_compte(uid):
    base.choisir_profil(uid, "Dynamique")
    portefeuille.passer_ordre(uid, "AI.PA", "achat", 10, 200.0, 0.001)
    fichier = base.exporter_compte(uid)
    assert json.loads(fichier)["identifiant"] == "client"

    # Sur un autre serveur (base vide), on recrée un compte puis on restaure le fichier
    _, _, nouveau = auth.creer_compte("client2", MDP, MDP)
    ok, message = base.importer_compte(nouveau, fichier)
    assert ok and "1 ordre récupéré" in message
    assert portefeuille.positions(nouveau)["AI.PA"]["quantite"] == 10
    assert base.lire_reglages(nouveau)["profil"] == "Dynamique"
    assert base.importer_compte(nouveau, b"pas une sauvegarde")[0] is False


def test_restauration_refuse_un_ordre_invalide(uid):
    contenu = {"ordres": [{"date": "2026-11-20 10:00:00", "code": "MC.PA", "sens": "achat", "quantite": 1,
                           "prix": 400, "frais": 0.4}], "historique": [], "reglages": {}}
    ok, message = base.importer_compte(uid, json.dumps(contenu).encode())
    assert not ok and "invalides" in message
    assert portefeuille.lire_ordres(uid).empty


def test_conversion_d_une_base_de_l_ancienne_version(tmp_path, monkeypatch):
    """Une base à un seul compte (version précédente) est convertie sans perte."""
    ancienne = tmp_path / "ancienne.db"
    monkeypatch.setattr(config, "DB_PATH", ancienne)
    with sqlite3.connect(ancienne) as con:
        con.executescript("""
            CREATE TABLE utilisateur (id INTEGER PRIMARY KEY CHECK (id = 1), identifiant TEXT NOT NULL,
                sel TEXT NOT NULL, hash TEXT NOT NULL, essais INTEGER NOT NULL DEFAULT 0, bloque_jusqua TEXT);
            CREATE TABLE ordres (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, code TEXT NOT NULL,
                sens TEXT NOT NULL, quantite INTEGER NOT NULL, prix REAL NOT NULL, frais REAL NOT NULL,
                automatique INTEGER NOT NULL DEFAULT 0);
            CREATE TRIGGER ordres_non_supprimables BEFORE DELETE ON ordres
                BEGIN SELECT RAISE(ABORT, 'non'); END;
            CREATE TABLE historique (date TEXT PRIMARY KEY, valeur REAL NOT NULL, liquidites REAL NOT NULL, cac40 REAL);
            CREATE TABLE reglages (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);
            INSERT INTO ordres (date, code, sens, quantite, prix, frais) VALUES ('2026-11-20 10:00:00', 'AI.PA', 'achat', 5, 200, 1);
            INSERT INTO reglages VALUES ('profil', '"Prudent"');
        """)
        sel = "00" * 16
        con.execute("INSERT INTO utilisateur VALUES (1, 'ancien', ?, ?, 0, NULL)", (sel, auth._hacher(MDP, sel)))
    base.initialiser()
    ok, _, numero = auth.verifier("ancien", MDP)
    assert ok and numero == 1
    assert portefeuille.positions(1)["AI.PA"]["quantite"] == 5
    assert base.lire_reglages(1)["profil"] == "Prudent"
    assert list(config.DOSSIER_SAUVEGARDES.glob("avant_conversion_*.db"))
