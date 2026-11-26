"""Mise en forme des nombres, montants et dates à la française."""
import math

import pandas as pd

VOYELLES = "aeiouyéèêàâîïôû"


def _vide(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


# Espaces insécables : « 500 000 € » ne sera jamais coupé en fin de ligne.
ESPACE_MILLIERS = "\u202f"   # espace fine insécable (norme française)
ESPACE = "\u00a0"            # espace insécable avant € et %


def nombre(x, decimales: int = 2) -> str:
    """1234567.891 -> '1 234 567,89'"""
    if _vide(x):
        return "—"
    return f"{x:,.{decimales}f}".replace(",", ESPACE_MILLIERS).replace(".", ",").replace("-", "−")


def euros(x, decimales: int = 2) -> str:
    """1234.5 -> '1 234,50 €'"""
    return "—" if _vide(x) else f"{nombre(x, decimales)}{ESPACE}€"


def pourcent(x, decimales: int = 1, signe: bool = False) -> str:
    """0.0523 -> '5,2 %' (ou '+5,2 %' avec signe=True)"""
    if _vide(x):
        return "—"
    texte = f"{x * 100:+.{decimales}f}" if signe else f"{x * 100:.{decimales}f}"
    return texte.replace(".", ",").replace("-", "−") + ESPACE + "%"


def ecart(x, decimales: int = 1):
    """Variation pour st.metric : garde le signe « - » simple pour que Streamlit colore en rouge."""
    if _vide(x):
        return None
    return f"{x * 100:+.{decimales}f} %".replace(".", ",")


def date_fr(d) -> str:
    """Timestamp ou texte ISO -> '25/11/2026'"""
    if d is None or (isinstance(d, float) and math.isnan(d)):
        return "—"
    return pd.Timestamp(d).strftime("%d/%m/%Y")


def de(texte: str) -> str:
    """Ajoute 'de' avec élision : 'une tendance' -> "d'une tendance", '2 actualités' -> 'de 2 actualités'."""
    return ("d'" + texte) if texte[:1].lower() in VOYELLES else ("de " + texte)


def lire_nombre(texte):
    """Lit un nombre saisi à la française : '12 500,50' -> 12500.5 ; '1.234,5' -> 1234.5. None si invalide."""
    if texte is None:
        return None
    if isinstance(texte, (int, float)):
        return float(texte)
    t = str(texte).strip()
    for c in (" ", "\u00a0", "\u202f", "€", "%"):
        t = t.replace(c, "")
    t = t.replace("−", "-")
    if not t:
        return None
    if "," in t and "." in t:   # 1.234,56 : le point sépare les milliers
        t = t.replace(".", "")
    try:
        x = float(t.replace(",", "."))
    except ValueError:
        return None
    return None if math.isnan(x) or math.isinf(x) else x


def texte_nombre(x, decimales: int = 2) -> str:
    """Valeur par défaut d'un champ de saisie : 1500.0 -> '1 500' ; 0.25 -> '0,25'."""
    if _vide(x):
        return ""
    texte = nombre(x, decimales).replace("−", "-")
    if "," in texte:
        texte = texte.rstrip("0").rstrip(",")
    return texte


JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def date_longue(d) -> str:
    """'mercredi 25 novembre 2026'"""
    d = pd.Timestamp(d)
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"
