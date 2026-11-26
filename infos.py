"""
A2 – Informations : objectif des analystes et actualités de la semaine.
"""
import math

from affichage import pourcent
from modele import Argument, limiter


def note_potentiel(potentiel: float) -> int:
    """Transforme l'écart objectif / cours en note de −2 à +2."""
    if potentiel > 0.15:
        return 2
    if potentiel > 0.05:
        return 1
    if potentiel > -0.05:
        return 0
    if potentiel > -0.15:
        return -1
    return -2


def note_infos(cours: float, objectif, actualites: list):
    """
    Algorithme A2. Renvoie (note, arguments, potentiel).
    - potentiel = objectif des analystes ÷ cours − 1
    - +0,5 par actualité positive, −0,5 par actualité négative (7 derniers jours)
    """
    note = 0.0
    arguments = []
    potentiel = None

    if objectif is not None and not math.isnan(objectif) and cours:
        potentiel = objectif / cours - 1
        n = note_potentiel(potentiel)
        note += n
        if n != 0:
            sens = "au-dessus" if potentiel > 0 else "en dessous"
            arguments.append(Argument(
                f"un objectif des analystes {pourcent(abs(potentiel), 0)} {sens} du cours", n, "infos"))

    positives = sum(1 for a in actualites if a["tonalite"] > 0)
    negatives = sum(1 for a in actualites if a["tonalite"] < 0)
    note += 0.5 * positives - 0.5 * negatives
    if positives:
        arguments.append(Argument(
            f"{positives} actualité{'s' if positives > 1 else ''} positive{'s' if positives > 1 else ''} cette semaine",
            0.5 * positives, "infos"))
    if negatives:
        arguments.append(Argument(
            f"{negatives} actualité{'s' if negatives > 1 else ''} négative{'s' if negatives > 1 else ''} cette semaine",
            -0.5 * negatives, "infos"))

    return limiter(note), arguments, potentiel
