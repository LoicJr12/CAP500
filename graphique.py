"""
A1 – Analyse graphique : indicateurs techniques et note de −2 à +2.
"""
import numpy as np
import pandas as pd

from modele import Argument, limiter


def indicateurs(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute aux cours : MM20, MM50, RSI, MACD, bandes de Bollinger, support et résistance."""
    out = df.copy()
    c = out["cloture"]

    # Moyennes mobiles
    out["MM20"] = c.rolling(20).mean()
    out["MM50"] = c.rolling(50).mean()

    # RSI 14 jours (méthode de Wilder)
    variation = c.diff()
    hausses = variation.clip(lower=0)
    baisses = -variation.clip(upper=0)
    moy_hausses = hausses.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    moy_baisses = baisses.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rsi = 100 - 100 / (1 + moy_hausses / moy_baisses.replace(0, np.nan))
    out["RSI"] = rsi.where(moy_baisses != 0, 100.0)

    # MACD = moyenne exponentielle 12 jours − moyenne exponentielle 26 jours
    out["MACD"] = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    out["MACD_signal"] = out["MACD"].ewm(span=9, adjust=False).mean()

    # Bandes de Bollinger : MM20 ± 2 écarts-types
    ecart = c.rolling(20).std(ddof=0)
    out["BB_haut"] = out["MM20"] + 2 * ecart
    out["BB_bas"] = out["MM20"] - 2 * ecart

    # Support et résistance : plus bas et plus haut des 3 derniers mois
    bas = out["bas"].fillna(c) if "bas" in out.columns else c
    haut = out["haut"].fillna(c) if "haut" in out.columns else c
    out["support"] = bas.rolling(63, min_periods=20).min()
    out["resistance"] = haut.rolling(63, min_periods=20).max()
    return out


def note_graphique(ind: pd.DataFrame):
    """
    Algorithme A1. Renvoie (note, arguments).
    +1 / −1 pour : tendance des moyennes, RSI, croisement du MACD, bandes de Bollinger.
    """
    utiles = ["cloture", "MM20", "MM50", "RSI", "MACD", "MACD_signal", "BB_haut", "BB_bas"]
    if len(ind) < 51 or ind[utiles].iloc[-2:].isna().any().any():
        return 0.0, []

    jour, veille = ind.iloc[-1], ind.iloc[-2]
    arguments = []

    if jour["cloture"] > jour["MM20"] > jour["MM50"]:
        arguments.append(Argument("une tendance haussière (cours au-dessus des moyennes 20 et 50 jours)", 1, "graphique"))
    elif jour["cloture"] < jour["MM20"] < jour["MM50"]:
        arguments.append(Argument("une tendance baissière (cours sous les moyennes 20 et 50 jours)", -1, "graphique"))

    if jour["RSI"] < 30:
        arguments.append(Argument(f"un RSI à {jour['RSI']:.0f} (action survendue, rebond possible)", 1, "graphique"))
    elif jour["RSI"] > 70:
        arguments.append(Argument(f"un RSI à {jour['RSI']:.0f} (action surachetée, baisse possible)", -1, "graphique"))

    if veille["MACD"] <= veille["MACD_signal"] and jour["MACD"] > jour["MACD_signal"]:
        arguments.append(Argument("un croisement haussier du MACD", 1, "graphique"))
    elif veille["MACD"] >= veille["MACD_signal"] and jour["MACD"] < jour["MACD_signal"]:
        arguments.append(Argument("un croisement baissier du MACD", -1, "graphique"))

    if jour["cloture"] < jour["BB_bas"]:
        arguments.append(Argument("un cours sous la bande de Bollinger basse", 1, "graphique"))
    elif jour["cloture"] > jour["BB_haut"]:
        arguments.append(Argument("un cours au-dessus de la bande de Bollinger haute", -1, "graphique"))

    note = limiter(sum(a.valeur for a in arguments))
    return note, arguments
