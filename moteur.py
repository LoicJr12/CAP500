"""
A5 – Score et recommandation ; A6 – Phrase d'argumentation.
"""
import pandas as pd

import config
import donnees
import financier
import graphique
import hasard
import infos
from affichage import de
from modele import Analyse

CLES_POIDS = {
    "graphique": "poids_graphique",
    "infos": "poids_infos",
    "financier": "poids_financier",
    "hasard": "poids_hasard",
}

FINS_DE_PHRASE = {
    "Acheter": "nous vous conseillons l'achat",
    "Vendre": "nous vous conseillons la vente",
    "Ne rien faire": "nous vous conseillons d'attendre",
}


def calculer_score(notes: dict, reglages: dict) -> float:
    """score = 0,40 × graphique + 0,25 × infos + 0,20 × financière + 0,15 × hasard"""
    return sum(reglages[CLES_POIDS[outil]] * note for outil, note in notes.items())


def recommander(score: float, detenue: bool, reglages: dict) -> str:
    """Algorithme A5 : « Vendre » seulement si le client détient l'action (règle RG9)."""
    if score >= reglages["seuil_achat"]:
        return "Acheter"
    if score <= reglages["seuil_vente"] and detenue:
        return "Vendre"
    return "Ne rien faire"


def raisons(conseil: str, arguments: list, reglages: dict, nombre: int = 3) -> list:
    """
    Les arguments qui pèsent le plus dans le conseil, du plus lourd au plus léger.
    Sert à la fois à l'argumentation (A6) et à l'affichage de la raison à côté du conseil :
    les deux doivent montrer les mêmes signaux, sinon l'explication ne correspondrait pas.
    """
    ponderes = [(a, a.valeur * reglages[CLES_POIDS[a.outil]]) for a in arguments]
    if conseil == "Acheter":
        choisis = sorted([p for p in ponderes if p[1] > 0], key=lambda p: -p[1])
    elif conseil == "Vendre":
        choisis = sorted([p for p in ponderes if p[1] < 0], key=lambda p: p[1])
    else:
        choisis = sorted(ponderes, key=lambda p: -abs(p[1]))
    return [a for a, _ in choisis[:nombre]]


def construire_phrase(conseil: str, arguments: list, reglages: dict, nombre: int = 3) -> str:
    """Algorithme A6 : garde les 3 arguments qui pèsent le plus dans le score."""
    textes = [de(a.texte) for a in raisons(conseil, arguments, reglages, nombre)]

    fin = FINS_DE_PHRASE[conseil]
    if not textes:
        return f"Aucun signal marqué pour le moment : {fin}."
    liste = textes[0] if len(textes) == 1 else ", ".join(textes[:-1]) + " et " + textes[-1]
    return f"Compte tenu {liste}, {fin}."


def analyser(code: str, cours: pd.DataFrame, ratios: pd.DataFrame, analystes: pd.DataFrame,
             actualites: list, reglages: dict, graine=None) -> Analyse:
    """Calcule les 4 notes (A1 à A4) et le score d'une action."""
    dernier = float(cours["cloture"].iloc[-1])
    veille = float(cours["cloture"].iloc[-2]) if len(cours) > 1 else dernier

    note_g, args_g = graphique.note_graphique(graphique.indicateurs(cours))
    note_i, args_i, potentiel = infos.note_infos(dernier, donnees.objectif_analystes(analystes, code), actualites)
    note_f, args_f = financier.note_financiere(code, ratios)
    simulation = hasard.simuler(cours["cloture"], graine=graine)
    note_h, args_h = hasard.note_hasard(simulation, reglages.get("var_max"))

    notes = {"graphique": note_g, "infos": note_i, "financier": note_f, "hasard": note_h}
    return Analyse(
        code=code,
        nom=config.ACTIONS[code],
        cours=dernier,
        date_cours=cours.index[-1],
        variation_jour=dernier / veille - 1,
        notes=notes,
        score=calculer_score(notes, reglages),
        arguments=args_g + args_i + args_f + args_h,
        potentiel=potentiel,
        simulation=simulation,
        ratios=ratios.loc[code].to_dict() if code in ratios.index else {},
        analystes=donnees.avis_analystes(analystes, code),
    )


def conseiller(analyse: Analyse, detenue: bool, reglages: dict):
    """Renvoie (conseil, phrase) pour une analyse, selon que le client détient l'action ou non."""
    conseil = recommander(analyse.score, detenue, reglages)
    return conseil, construire_phrase(conseil, analyse.arguments, reglages)
