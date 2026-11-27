"""
Chargement des données : cours (yfinance), comptes annuels et objectifs des
analystes (fichiers CSV à remplir à la main), actualités (Google Actualités).
"""
import unicodedata
import urllib.parse
import urllib.request
from datetime import timedelta

import pandas as pd

import base
import config
import horloge

COLONNES_YF = {"Open": "ouverture", "High": "haut", "Low": "bas", "Close": "cloture", "Volume": "volume"}

MOTS_POSITIFS = [
    "relève", "releve", "rehausse", "hausse", "achat", "record", "bondit", "grimpe", "progresse",
    "surperform", "dépasse", "depasse", "rebond", "contrat", "succès", "accélère", "accelere",
    "augmente", "en tête", "solide", "optimis",
]
MOTS_NEGATIFS = [
    "abaisse", "baisse", "chute", "recul", "dégrade", "degrade", "sous-perform", "avertissement",
    "perte", "plonge", "décroche", "decroche", "déçoit", "decoit", "décevant", "decevant", "réduit",
    "reduit", "sanction", "enquête", "lanterne rouge", "prudent", "inquiét", "inquiet",
]


# =====================================================================
# Cours de bourse
# =====================================================================
def telecharger_cours(code: str, periode: str = "1y") -> bool:
    """Télécharge les cours quotidiens et les enregistre. Renvoie False si échec."""
    try:
        import yfinance as yf
        df = yf.download(code, period=periode, interval="1d", progress=False,
                         auto_adjust=False, threads=False, timeout=10)
    except Exception:
        return False
    if df is None or df.empty:
        return False
    if isinstance(df.columns, pd.MultiIndex):  # yfinance renvoie parfois 2 niveaux de colonnes
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=COLONNES_YF)
    if "cloture" not in df.columns:
        return False
    df = df.dropna(subset=["cloture"])
    lignes = [
        (pd.Timestamp(jour).strftime("%Y-%m-%d"), code,
         _nombre(l.get("ouverture")), _nombre(l.get("haut")), _nombre(l.get("bas")),
         float(l["cloture"]), _nombre(l.get("volume")))
        for jour, l in df.iterrows()
    ]
    enregistrer_cours(lignes)
    return True


def _nombre(x):
    return None if x is None or pd.isna(x) else float(x)


def enregistrer_cours(lignes: list) -> None:
    with base.ouvrir() as con:
        con.executemany(
            "INSERT OR REPLACE INTO cours (date, code, ouverture, haut, bas, cloture, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            lignes,
        )


def mettre_a_jour_cours() -> dict:
    """Télécharge les 5 actions et le CAC 40. Renvoie {code: True/False}."""
    return {code: telecharger_cours(code) for code in [*config.ACTIONS, config.INDICE]}


def lire_cours(code: str, nb_jours: int = 600) -> pd.DataFrame:
    """Cours enregistrés d'une action, du plus ancien au plus récent (index = date)."""
    with base.ouvrir() as con:
        df = pd.read_sql_query(
            "SELECT date, ouverture, haut, bas, cloture, volume FROM cours WHERE code = ? ORDER BY date",
            con, params=(code,),
        )
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").tail(nb_jours)


def dernier_cours(code: str):
    """Renvoie (prix, date) du dernier cours connu, ou (None, None)."""
    with base.ouvrir() as con:
        ligne = con.execute(
            "SELECT date, cloture FROM cours WHERE code = ? ORDER BY date DESC LIMIT 1", (code,)
        ).fetchone()
    return (ligne["cloture"], pd.Timestamp(ligne["date"])) if ligne else (None, None)


def cours_actuels() -> dict:
    """{code: dernier prix connu} pour les 5 actions."""
    prix = {}
    for code in config.ACTIONS:
        valeur, _ = dernier_cours(code)
        if valeur is not None:
            prix[code] = valeur
    return prix


def _sans_accents(texte: str) -> str:
    texte = unicodedata.normalize("NFD", str(texte).strip().lower())
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


def importer_csv_cours(fichier, code: str) -> int:
    """
    Importe un fichier CSV de cours (ex. export ABC Bourse) en secours de yfinance.
    Il faut au minimum une colonne contenant « date » et une colonne « clôture » / « close » / « dernier ».
    Renvoie le nombre de lignes importées.
    """
    df = pd.read_csv(fichier, sep=None, engine="python")
    noms = {col: _sans_accents(col) for col in df.columns}
    col_date = next((c for c, n in noms.items() if "date" in n), None)
    col_clo = next((c for c, n in noms.items() if n.startswith(("clot", "close", "dernier"))), None)
    if col_date is None or col_clo is None:
        raise ValueError("Colonnes « date » et « clôture » introuvables dans le fichier.")

    def colonne(debuts):
        c = next((c for c, n in noms.items() if n.startswith(debuts)), None)
        return None if c is None else pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")

    propre = pd.DataFrame({
        "date": pd.to_datetime(df[col_date], dayfirst=True, errors="coerce"),
        "ouverture": colonne(("ouv", "open")),
        "haut": colonne(("haut", "high", "plus haut")),
        "bas": colonne(("bas", "low", "plus bas")),
        "cloture": pd.to_numeric(df[col_clo].astype(str).str.replace(",", "."), errors="coerce"),
        "volume": colonne(("vol",)),
    }).dropna(subset=["date", "cloture"])
    lignes = [
        (l.date.strftime("%Y-%m-%d"), code, _nombre(l.ouverture), _nombre(l.haut),
         _nombre(l.bas), float(l.cloture), _nombre(l.volume))
        for l in propre.itertuples()
    ]
    enregistrer_cours(lignes)
    return len(lignes)


# =====================================================================
# Comptes annuels et objectifs des analystes (fichiers CSV)
# =====================================================================
def _lire_csv(chemin) -> pd.DataFrame:
    if not chemin.exists():
        return pd.DataFrame()
    return pd.read_csv(chemin, sep=";", decimal=",", comment="#", encoding="utf-8")


def charger_comptes() -> pd.DataFrame:
    return _lire_csv(config.FICHIER_COMPTES)


def charger_analystes() -> pd.DataFrame:
    return _lire_csv(config.FICHIER_ANALYSTES)


def objectif_analystes(analystes: pd.DataFrame, code: str):
    """Objectif de cours médian des analystes pour une action, ou None."""
    if analystes.empty or "objectif" not in analystes.columns:
        return None
    ligne = analystes[analystes["code"] == code]
    if ligne.empty or pd.isna(ligne["objectif"].iloc[0]):
        return None
    return float(ligne["objectif"].iloc[0])


# =====================================================================
# Actualités
# =====================================================================
def tonalite(titre: str) -> int:
    """+1 actualité positive, −1 négative, 0 neutre (repérage par mots-clés)."""
    t = titre.lower()
    positifs = sum(mot in t for mot in MOTS_POSITIFS)
    negatifs = sum(mot in t for mot in MOTS_NEGATIFS)
    return 1 if positifs > negatifs else -1 if negatifs > positifs else 0


def url_flux(nom: str) -> str:
    requete = urllib.parse.quote(f'"{nom}" bourse')
    return f"https://news.google.com/rss/search?q={requete}&hl=fr&gl=FR&ceid=FR:fr"


def telecharger_actualites(code: str) -> bool:
    """Récupère les dernières actualités d'une action et les enregistre."""
    try:
        import feedparser
        requete = urllib.request.Request(url_flux(config.ACTIONS[code]), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(requete, timeout=10) as reponse:
            flux = feedparser.parse(reponse.read())
    except Exception:
        return False
    if not flux.entries:
        return False

    lignes = []
    for entree in flux.entries[:20]:
        titre = entree.get("title", "").strip()
        lien = entree.get("link")
        if not titre or not lien:
            continue
        source = entree.get("source", {}).get("title", "") if isinstance(entree.get("source"), dict) else ""
        if source and titre.endswith(f" - {source}"):
            titre = titre[: -len(f" - {source}")]
        publie = entree.get("published_parsed")
        quand = (horloge.de_utc(*publie[:6]) if publie else horloge.maintenant()).strftime("%Y-%m-%d %H:%M")
        lignes.append((lien, quand, code, titre, source, tonalite(titre)))

    with base.ouvrir() as con:
        con.executemany(
            "INSERT OR IGNORE INTO actualites (lien, date, code, titre, source, tonalite) VALUES (?, ?, ?, ?, ?, ?)",
            lignes,
        )
    return True


def lire_actualites(code: str, nombre: int = 5) -> list:
    with base.ouvrir() as con:
        lignes = con.execute(
            "SELECT date, titre, source, lien, tonalite FROM actualites WHERE code = ? ORDER BY date DESC LIMIT ?",
            (code, nombre),
        ).fetchall()
    return [dict(l) for l in lignes]


def actualites_semaine(code: str) -> list:
    """Actualités des 7 derniers jours (utilisées par l'algorithme A2)."""
    depuis = (horloge.maintenant() - timedelta(days=7)).strftime("%Y-%m-%d")
    with base.ouvrir() as con:
        lignes = con.execute(
            "SELECT date, titre, tonalite FROM actualites WHERE code = ? AND date >= ? ORDER BY date DESC",
            (code, depuis),
        ).fetchall()
    return [dict(l) for l in lignes]
