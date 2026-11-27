"""Structures de données partagées entre les modules de calcul."""

# Version de la structure `Analyse`. À augmenter dès qu'un champ est ajouté, retiré ou renommé :
# les analyses sont gardées en cache par Streamlit, et un objet mis en cache par une version
# précédente n'a pas les nouveaux champs. Sans ce numéro dans la clé du cache, l'écran plante
# sur un AttributeError au lieu de recalculer.
VERSION_ANALYSE = 2
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class Argument:
    """Un élément qui pousse la note d'un outil vers l'achat (+) ou la vente (−)."""
    texte: str      # phrase utilisée dans l'argumentation, ex. "un RSI à 28 (action survendue)"
    valeur: float   # contribution à la note de l'outil
    outil: str      # "graphique", "infos", "financier" ou "hasard"


@dataclass
class Analyse:
    """Résultat complet de l'analyse d'une action."""
    code: str
    nom: str
    cours: float
    date_cours: pd.Timestamp
    variation_jour: float
    notes: dict                 # {"graphique": .., "infos": .., "financier": .., "hasard": ..}
    score: float
    arguments: list
    potentiel: Optional[float] = None
    simulation: Optional[dict] = None
    ratios: dict = field(default_factory=dict)
    analystes: dict = field(default_factory=dict)   # objectif de cours + sa source et sa date (C6)


def limiter(x: float, bas: float = -2.0, haut: float = 2.0) -> float:
    """Ramène une note entre −2 et +2."""
    return float(max(bas, min(haut, x)))
