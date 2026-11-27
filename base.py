"""
Base de données SQLite : création des tables, réglages, sauvegardes.
Toutes les données sont dans un seul fichier : data/portefeuille.db
"""
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path

import config
import horloge

SCHEMA = """
CREATE TABLE IF NOT EXISTS utilisateurs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    identifiant     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    sel             TEXT NOT NULL,
    hash            TEXT NOT NULL,      -- mot de passe haché (jamais en clair)
    code_hash       TEXT,               -- code de récupération haché
    essais          INTEGER NOT NULL DEFAULT 0,
    bloque_jusqua   TEXT,
    portefeuille    INTEGER NOT NULL DEFAULT 1,   -- n° du portefeuille en cours (+1 à chaque remise à zéro)
    cree_le         TEXT NOT NULL
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
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur_id  INTEGER NOT NULL REFERENCES utilisateurs (id),
    portefeuille    INTEGER NOT NULL DEFAULT 1,
    date            TEXT NOT NULL,
    code            TEXT NOT NULL,
    sens            TEXT NOT NULL CHECK (sens IN ('achat', 'vente')),
    quantite        INTEGER NOT NULL CHECK (quantite > 0),
    prix            REAL NOT NULL CHECK (prix > 0),
    frais           REAL NOT NULL,
    automatique     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ordres_par_compte ON ordres (utilisateur_id, portefeuille);

-- Un ordre enregistré ne peut être ni modifié ni supprimé (traçabilité).
-- Remettre un portefeuille à zéro ouvre un nouveau portefeuille : les anciens ordres restent archivés.
CREATE TRIGGER IF NOT EXISTS ordres_non_modifiables BEFORE UPDATE ON ordres
BEGIN SELECT RAISE(ABORT, 'Un ordre enregistré ne peut pas être modifié.'); END;
CREATE TRIGGER IF NOT EXISTS ordres_non_supprimables BEFORE DELETE ON ordres
BEGIN SELECT RAISE(ABORT, 'Un ordre enregistré ne peut pas être supprimé.'); END;

CREATE TABLE IF NOT EXISTS historique (
    utilisateur_id  INTEGER NOT NULL,
    portefeuille    INTEGER NOT NULL,
    date            TEXT NOT NULL,
    valeur          REAL NOT NULL,
    liquidites      REAL NOT NULL,
    cac40           REAL,
    PRIMARY KEY (utilisateur_id, portefeuille, date)
);

-- Sessions ouvertes : permettent de retrouver son compte après un rafraîchissement de la page
-- (Streamlit perd st.session_state à chaque rechargement). Le jeton n'est jamais stocké en clair.
CREATE TABLE IF NOT EXISTS sessions (
    jeton_hash      TEXT PRIMARY KEY,
    utilisateur_id  INTEGER NOT NULL REFERENCES utilisateurs (id) ON DELETE CASCADE,
    expire_le       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reglages (
    utilisateur_id  INTEGER NOT NULL,
    cle             TEXT NOT NULL,
    valeur          TEXT NOT NULL,
    PRIMARY KEY (utilisateur_id, cle)
);
"""

# Réglages qu'un fichier de sauvegarde peut contenir
CLES_REGLAGES = {*config.REGLAGES_DEFAUT, "profil", "profil_defini", "depart_fait", "limite_atteinte"}

# Réglages conservés depuis le compte quand le fichier restauré ne les contient pas
CLES_PROFIL = {"profil", "profil_defini"}


def connexion(contraintes: bool = True) -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=config.ATTENTE_BASE_S)
    con.row_factory = sqlite3.Row
    # Journal WAL : plusieurs personnes peuvent lire pendant qu'une autre écrit (démo à plusieurs,
    # application en ligne). Sans lui, un simple affichage de page peut échouer sur « database is locked ».
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute(f"PRAGMA foreign_keys = {'ON' if contraintes else 'OFF'}")
    return con


@contextmanager
def ouvrir(contraintes: bool = True):
    """À utiliser avec `with base.ouvrir() as con:` : enregistre puis ferme la connexion."""
    con = connexion(contraintes)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def initialiser() -> None:
    """Crée les tables si elles n'existent pas encore (et convertit une base de l'ancienne version)."""
    with ouvrir() as con:
        tables = {l[0] for l in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "utilisateur" in tables:
        _convertir_ancienne_base()
    with ouvrir() as con:
        con.executescript(SCHEMA)


def _convertir_ancienne_base() -> None:
    """Ancienne version (un seul compte) : le compte et son portefeuille deviennent le compte n° 1."""
    copie_securite("avant_conversion")
    with ouvrir(contraintes=False) as con:   # les tables sont renommées puis supprimées : clés étrangères levées
        con.executescript("""
            DROP TRIGGER IF EXISTS ordres_non_modifiables;
            DROP TRIGGER IF EXISTS ordres_non_supprimables;
            ALTER TABLE ordres RENAME TO ancien_ordres;
            ALTER TABLE historique RENAME TO ancien_historique;
            ALTER TABLE reglages RENAME TO ancien_reglages;
        """)
        con.executescript(SCHEMA)
        colonnes = {c["name"] for c in con.execute("PRAGMA table_info(utilisateur)")}
        code = "code_hash" if "code_hash" in colonnes else "NULL"
        con.execute(f"""INSERT INTO utilisateurs (id, identifiant, sel, hash, code_hash, essais, bloque_jusqua, cree_le)
                        SELECT 1, identifiant, sel, hash, {code}, 0, NULL, datetime('now') FROM utilisateur""")
        if con.execute("SELECT COUNT(*) FROM utilisateurs").fetchone()[0]:
            con.executescript("""
                INSERT INTO ordres (utilisateur_id, portefeuille, date, code, sens, quantite, prix, frais, automatique)
                    SELECT 1, 1, date, code, sens, quantite, prix, frais, automatique FROM ancien_ordres ORDER BY id;
                INSERT INTO historique SELECT 1, 1, date, valeur, liquidites, cac40 FROM ancien_historique;
                INSERT INTO reglages SELECT 1, cle, valeur FROM ancien_reglages;
            """)
        con.executescript("""
            DROP TABLE ancien_ordres; DROP TABLE ancien_historique; DROP TABLE ancien_reglages;
            DROP TABLE utilisateur;
        """)


def est_administrateur(uid: int) -> bool:
    """
    Les cours et les actualités sont communs à tous les comptes : les modifier change la valeur des
    portefeuilles et les conseils de tout le monde. Seul le compte principal (le premier créé,
    celui de la personne qui installe l'application) peut donc importer des cours.
    """
    with ouvrir() as con:
        premier = con.execute("SELECT MIN(id) FROM utilisateurs").fetchone()[0]
    return premier is not None and uid == premier


def portefeuille_courant(uid: int) -> int:
    with ouvrir() as con:
        ligne = con.execute("SELECT portefeuille FROM utilisateurs WHERE id = ?", (uid,)).fetchone()
    return ligne["portefeuille"] if ligne else 1


# ---------- Réglages (propres à chaque compte) ----------
def lire_reglages(uid: int) -> dict:
    """Réglages par défaut, complétés par ceux du profil de risque puis par ceux du compte."""
    with ouvrir() as con:
        stockes = {l["cle"]: json.loads(l["valeur"])
                   for l in con.execute("SELECT cle, valeur FROM reglages WHERE utilisateur_id = ?", (uid,))}
    profil = stockes.get("profil")
    if profil not in config.PROFILS:
        profil = config.PROFIL_DEFAUT
    reglages = dict(config.REGLAGES_DEFAUT)
    reglages.update(config.PROFILS[profil])
    reglages.update(stockes)
    reglages["profil"] = profil
    return reglages


def ecrire_reglage(uid: int, cle: str, valeur) -> None:
    with ouvrir() as con:
        con.execute("INSERT OR REPLACE INTO reglages (utilisateur_id, cle, valeur) VALUES (?, ?, ?)",
                    (uid, cle, json.dumps(valeur)))


def supprimer_reglages(uid: int, cles) -> None:
    with ouvrir() as con:
        con.executemany("DELETE FROM reglages WHERE utilisateur_id = ? AND cle = ?", [(uid, c) for c in cles])


def choisir_profil(uid: int, profil: str) -> None:
    """Applique un profil de risque : ses seuils remplacent ceux réglés à la main."""
    if profil not in config.PROFILS:
        raise ValueError(f"Profil inconnu : {profil}")
    supprimer_reglages(uid, ["seuil_achat", "seuil_vente"])
    ecrire_reglage(uid, "profil", profil)
    ecrire_reglage(uid, "profil_defini", True)


# ---------- Sauvegardes ----------
def sauvegarder():
    """Copie la base une fois par jour et garde les 7 dernières copies."""
    if not config.DB_PATH.exists():
        return None
    config.DOSSIER_SAUVEGARDES.mkdir(parents=True, exist_ok=True)
    cible = config.DOSSIER_SAUVEGARDES / f"portefeuille_{horloge.aujourdhui():%Y-%m-%d}.db"
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
    cible = config.DOSSIER_SAUVEGARDES / f"{motif}_{horloge.maintenant():%Y-%m-%d_%H%M%S}.db"
    with closing(sqlite3.connect(config.DB_PATH)) as source, closing(sqlite3.connect(cible)) as copie:
        source.backup(copie)
    return cible


def exporter_compte(uid: int) -> bytes:
    """Le portefeuille en cours du compte (ordres, historique, réglages) dans un fichier JSON."""
    pf = portefeuille_courant(uid)
    with ouvrir() as con:
        identifiant = con.execute("SELECT identifiant FROM utilisateurs WHERE id = ?", (uid,)).fetchone()[0]
        ordres = [dict(l) for l in con.execute(
            "SELECT date, code, sens, quantite, prix, frais, automatique FROM ordres "
            "WHERE utilisateur_id = ? AND portefeuille = ? ORDER BY id", (uid, pf))]
        historique = [dict(l) for l in con.execute(
            "SELECT date, valeur, liquidites, cac40 FROM historique "
            "WHERE utilisateur_id = ? AND portefeuille = ? ORDER BY date", (uid, pf))]
        reglages = {l["cle"]: json.loads(l["valeur"]) for l in con.execute(
            "SELECT cle, valeur FROM reglages WHERE utilisateur_id = ?", (uid,))}
    contenu = {"application": config.NOM_APPLI, "version": 2, "identifiant": identifiant,
               "exporte_le": horloge.maintenant().isoformat(timespec="seconds"),
               "reglages": reglages, "ordres": ordres, "historique": historique}
    return json.dumps(contenu, ensure_ascii=False, indent=1).encode("utf-8")


def _ordre_valide(o) -> bool:
    try:
        datetime.fromisoformat(str(o["date"]))
        return (o["code"] in config.ACTIONS and o["sens"] in ("achat", "vente")
                and isinstance(o["quantite"], int) and not isinstance(o["quantite"], bool) and o["quantite"] > 0
                and float(o["prix"]) > 0 and float(o["frais"]) >= 0)
    except (KeyError, TypeError, ValueError):
        return False


def _coherence_ordres(ordres: list):
    """
    Rejoue les ordres du fichier dans l'ordre pour vérifier qu'ils décrivent un portefeuille possible :
    on ne peut pas dépenser plus que son argent, ni vendre des actions qu'on ne détient pas.
    Renvoie un message d'erreur, ou None si tout est cohérent.
    """
    liquide = config.CAPITAL
    detenus = {}
    for o in ordres:
        montant = o["quantite"] * float(o["prix"])
        frais = float(o["frais"])
        if o["sens"] == "achat":
            if montant + frais > liquide + 0.01:
                return ("Le fichier décrit un achat de "
                        f"{o['quantite']} {config.ACTIONS[o['code']]} sans l'argent nécessaire : "
                        "rien n'a été modifié.")
            liquide -= montant + frais
            detenus[o["code"]] = detenus.get(o["code"], 0) + o["quantite"]
        else:
            if o["quantite"] > detenus.get(o["code"], 0):
                return (f"Le fichier décrit une vente de {o['quantite']} {config.ACTIONS[o['code']]} "
                        "qui n'étaient pas détenues : rien n'a été modifié.")
            detenus[o["code"]] -= o["quantite"]
            liquide += montant - frais
        if liquide < -0.01:        # des frais aberrants ne doivent pas non plus créer un découvert
            return (f"Le fichier décrit un portefeuille à découvert après l'opération du {o['date']} : "
                    "rien n'a été modifié.")
    return None


def importer_compte(uid: int, contenu: bytes):
    """
    Restaure un fichier créé par exporter_compte dans un nouveau portefeuille du compte
    (le portefeuille actuel reste archivé). Renvoie (ok, message).
    """
    try:
        donnees = json.loads(contenu.decode("utf-8"))
        ordres, historique, reglages = donnees["ordres"], donnees["historique"], donnees["reglages"]
        if not (isinstance(ordres, list) and isinstance(historique, list) and isinstance(reglages, dict)):
            raise ValueError
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return False, "Ce fichier n'est pas une sauvegarde de l'application."
    if not all(isinstance(o, dict) and _ordre_valide(o) for o in ordres):
        return False, "Le fichier contient des ordres invalides : rien n'a été modifié."
    impossible = _coherence_ordres(ordres)
    if impossible:
        return False, impossible

    # Un fichier sans profil de risque ne doit pas renvoyer la personne au questionnaire :
    # on garde le profil déjà choisi sur ce compte pour les clés absentes du fichier.
    reglages = {**{c: v for c, v in lire_reglages(uid).items() if c in CLES_PROFIL}, **reglages}

    nouveau = portefeuille_courant(uid) + 1
    with ouvrir() as con:
        con.execute("UPDATE utilisateurs SET portefeuille = ? WHERE id = ?", (nouveau, uid))
        con.executemany(
            "INSERT INTO ordres (utilisateur_id, portefeuille, date, code, sens, quantite, prix, frais, automatique) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(uid, nouveau, o["date"], o["code"], o["sens"], o["quantite"], float(o["prix"]), float(o["frais"]),
              int(bool(o.get("automatique")))) for o in ordres])
        for h in historique:
            try:
                con.execute("INSERT OR REPLACE INTO historique VALUES (?, ?, ?, ?, ?, ?)",
                            (uid, nouveau, str(h["date"])[:10], float(h["valeur"]), float(h["liquidites"]),
                             None if h.get("cac40") is None else float(h["cac40"])))
            except (KeyError, TypeError, ValueError):
                continue
        con.execute("DELETE FROM reglages WHERE utilisateur_id = ?", (uid,))
        for cle, valeur in reglages.items():
            if cle in CLES_REGLAGES and isinstance(valeur, (int, float, str, bool)):
                if cle == "profil" and valeur not in config.PROFILS:
                    continue
                con.execute("INSERT INTO reglages VALUES (?, ?, ?)", (uid, cle, json.dumps(valeur)))
    return True, f"Sauvegarde restaurée : {len(ordres)} ordre{'s' if len(ordres) > 1 else ''} récupéré{'s' if len(ordres) > 1 else ''}."


def reinitialiser_portefeuille(uid: int) -> None:
    """Repart de 500 000 € : ouvre un nouveau portefeuille (les anciens ordres restent archivés)."""
    with ouvrir() as con:
        con.execute("UPDATE utilisateurs SET portefeuille = portefeuille + 1 WHERE id = ?", (uid,))
    supprimer_reglages(uid, ["depart_fait", "limite_atteinte"])
