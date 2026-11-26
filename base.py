"""
Base de données SQLite : création des tables, réglages, sauvegardes.
Toutes les données sont dans un seul fichier : data/portefeuille.db
"""
import json
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from datetime import date, datetime
from pathlib import Path

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS utilisateur (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    identifiant     TEXT NOT NULL,
    sel             TEXT NOT NULL,
    hash            TEXT NOT NULL,
    code_hash       TEXT,               -- code de récupération (haché)
    essais          INTEGER NOT NULL DEFAULT 0,
    bloque_jusqua   TEXT
);

CREATE TABLE IF NOT EXISTS cours (
    date        TEXT NOT NULL,
    code        TEXT NOT NULL,
    ouverture   REAL,
    haut        REAL,
    bas         REAL,
    cloture     REAL NOT NULL,
    volume      REAL,
    PRIMARY KEY (date, code)
);

CREATE TABLE IF NOT EXISTS actualites (
    lien        TEXT PRIMARY KEY,
    date        TEXT,
    code        TEXT NOT NULL,
    titre       TEXT NOT NULL,
    source      TEXT,
    tonalite    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ordres (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    code        TEXT NOT NULL,
    sens        TEXT NOT NULL CHECK (sens IN ('achat', 'vente')),
    quantite    INTEGER NOT NULL CHECK (quantite > 0),
    prix        REAL NOT NULL CHECK (prix > 0),
    frais       REAL NOT NULL,
    automatique INTEGER NOT NULL DEFAULT 0
);

-- Un ordre enregistré ne peut être ni modifié ni supprimé (traçabilité).
CREATE TRIGGER IF NOT EXISTS ordres_non_modifiables BEFORE UPDATE ON ordres
BEGIN SELECT RAISE(ABORT, 'Un ordre enregistré ne peut pas être modifié.'); END;
CREATE TRIGGER IF NOT EXISTS ordres_non_supprimables BEFORE DELETE ON ordres
BEGIN SELECT RAISE(ABORT, 'Un ordre enregistré ne peut pas être supprimé.'); END;

CREATE TABLE IF NOT EXISTS historique (
    date        TEXT PRIMARY KEY,
    valeur      REAL NOT NULL,
    liquidites  REAL NOT NULL,
    cac40       REAL
);

CREATE TABLE IF NOT EXISTS reglages (
    cle         TEXT PRIMARY KEY,
    valeur      TEXT NOT NULL
);
"""


def connexion() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def ouvrir():
    """À utiliser avec `with base.ouvrir() as con:` : enregistre puis ferme la connexion."""
    con = connexion()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def initialiser() -> None:
    """Crée les tables si elles n'existent pas encore."""
    with ouvrir() as con:
        con.executescript(SCHEMA)
        colonnes = [c["name"] for c in con.execute("PRAGMA table_info(utilisateur)")]
        if "code_hash" not in colonnes:   # base créée avec une version précédente
            con.execute("ALTER TABLE utilisateur ADD COLUMN code_hash TEXT")


# ---------- Réglages ----------
def lire_reglages() -> dict:
    """Réglages par défaut, complétés par ceux du profil de risque puis par ceux enregistrés."""
    with ouvrir() as con:
        stockes = {l["cle"]: json.loads(l["valeur"]) for l in con.execute("SELECT cle, valeur FROM reglages")}
    profil = stockes.get("profil")
    if profil not in config.PROFILS:
        profil = config.PROFIL_DEFAUT
    reglages = dict(config.REGLAGES_DEFAUT)
    reglages.update(config.PROFILS[profil])
    reglages.update(stockes)
    reglages["profil"] = profil
    return reglages


def choisir_profil(profil: str) -> None:
    """Applique un profil de risque : ses seuils remplacent ceux réglés à la main."""
    if profil not in config.PROFILS:
        raise ValueError(f"Profil inconnu : {profil}")
    with ouvrir() as con:
        con.execute("DELETE FROM reglages WHERE cle IN ('seuil_achat', 'seuil_vente')")
    ecrire_reglage("profil", profil)
    ecrire_reglage("profil_defini", True)


def ecrire_reglage(cle: str, valeur) -> None:
    with ouvrir() as con:
        con.execute(
            "INSERT OR REPLACE INTO reglages (cle, valeur) VALUES (?, ?)",
            (cle, json.dumps(valeur)),
        )


# ---------- Sauvegardes ----------
def sauvegarder():
    """Copie la base une fois par jour et garde les 7 dernières copies."""
    if not config.DB_PATH.exists():
        return None
    config.DOSSIER_SAUVEGARDES.mkdir(parents=True, exist_ok=True)
    cible = config.DOSSIER_SAUVEGARDES / f"portefeuille_{date.today():%Y-%m-%d}.db"
    if not cible.exists():
        with closing(sqlite3.connect(config.DB_PATH)) as source, closing(sqlite3.connect(cible)) as copie:
            source.backup(copie)
    copies = sorted(config.DOSSIER_SAUVEGARDES.glob("portefeuille_*.db"))
    for ancienne in copies[: -config.NB_SAUVEGARDES]:
        ancienne.unlink()
    return cible


def copie_securite(motif: str) -> Path:
    """Copie datée de la base avant une opération importante (jamais supprimée automatiquement)."""
    config.DOSSIER_SAUVEGARDES.mkdir(parents=True, exist_ok=True)
    cible = config.DOSSIER_SAUVEGARDES / f"{motif}_{datetime.now():%Y-%m-%d_%H%M%S}.db"
    with closing(sqlite3.connect(config.DB_PATH)) as source, closing(sqlite3.connect(cible)) as copie:
        source.backup(copie)
    return cible


def exporter_base() -> bytes:
    """Contenu complet de la base, pour le télécharger (utile quand l'appli est en ligne)."""
    with tempfile.TemporaryDirectory() as dossier:
        chemin = Path(dossier) / "export.db"
        with closing(sqlite3.connect(config.DB_PATH)) as source, closing(sqlite3.connect(chemin)) as copie:
            source.backup(copie)
        return chemin.read_bytes()


def restaurer_base(contenu: bytes):
    """Remplace la base par un fichier téléchargé auparavant. Renvoie (ok, message)."""
    with tempfile.TemporaryDirectory() as dossier:
        chemin = Path(dossier) / "import.db"
        chemin.write_bytes(contenu)
        try:
            with closing(sqlite3.connect(chemin)) as con:
                tables = {l[0] for l in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        except sqlite3.DatabaseError:
            return False, "Ce fichier n'est pas une sauvegarde de l'application."
        if not {"utilisateur", "ordres", "reglages", "cours"} <= tables:
            return False, "Ce fichier n'est pas une sauvegarde de l'application."
        copie_securite("avant_restauration")
        with closing(sqlite3.connect(chemin)) as source, closing(sqlite3.connect(config.DB_PATH)) as cible:
            source.backup(cible)
    initialiser()
    return True, "Sauvegarde restaurée."


def reinitialiser_portefeuille() -> None:
    """Repart de zéro : supprime les ordres et l'historique (le compte et les cours sont gardés)."""
    with ouvrir() as con:
        con.executescript(
            """
            DROP TABLE IF EXISTS ordres;
            DROP TABLE IF EXISTS historique;
            DELETE FROM reglages WHERE cle IN ('depart_fait', 'limite_atteinte');
            """
        )
    initialiser()
