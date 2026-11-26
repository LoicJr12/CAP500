"""
A4 – Prise en compte du hasard : simulation Monte-Carlo sur une semaine.
"""
import numpy as np
import pandas as pd

import config
from affichage import pourcent
from modele import Argument, limiter


def simuler(cloture: pd.Series, nb: int = config.NB_SIMULATIONS, jours: int = config.HORIZON_JOURS,
            graine=None):
    """
    Simule `nb` trajectoires de `jours` jours avec un mouvement brownien géométrique :
        S(t+1) = S(t) × exp((μ − σ²/2) + σ × Z),  Z tiré au hasard (loi normale)
    μ et σ sont calculés sur la dernière année de cours.
    Renvoie un dictionnaire de résultats, ou None si l'historique est trop court.
    """
    c = cloture.dropna()
    if len(c) < 30:
        return None
    rendements_log = np.log(c).diff().dropna().tail(252)
    sigma = float(rendements_log.std())
    mu = float(rendements_log.mean()) + sigma ** 2 / 2   # hausse moyenne par jour
    depart = float(c.iloc[-1])

    tirage = np.random.default_rng(graine)
    z = tirage.standard_normal((nb, jours))               # 10 000 scénarios × 5 jours
    pas = (mu - sigma ** 2 / 2) + sigma * z
    trajectoires = depart * np.exp(np.cumsum(pas, axis=1))
    final = trajectoires[:, -1]
    rendements = final / depart - 1

    return {
        "proba_hausse": float((final > depart).mean()),
        "perte_95": float(max(0.0, -np.percentile(rendements, 5))),   # perte dépassée dans 5 % des cas
        "rendement_median": float(np.median(rendements)),
        "volatilite_annuelle": sigma * float(np.sqrt(252)),
        "rendements": rendements,
        "trajectoires": trajectoires[:100],
        "depart": depart,
    }


def note_hasard(resultat, var_max: float = None):
    """
    Algorithme A4. Renvoie (note, arguments).
    note = 4 × (probabilité de hausse − 0,5), ou −2 si la perte à 95 % dépasse le seuil du profil (10 % par défaut).
    """
    if resultat is None:
        return 0.0, []
    var_max = config.PERTE_MAX_SIMULATION if var_max is None else var_max
    proba = resultat["proba_hausse"]
    if resultat["perte_95"] > var_max:
        return -2.0, [Argument(
            f"un risque de perte de {pourcent(resultat['perte_95'], 0)} sur une semaine (trop élevé)", -2, "hasard")]
    note = limiter(4 * (proba - 0.5))
    return note, [Argument(f"une probabilité de hausse de {pourcent(proba, 0)} sur une semaine", note, "hasard")]
