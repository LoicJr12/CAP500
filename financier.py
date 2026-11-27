"""
A3 – Analyse financière : 5 ratios comparés à la moyenne des 5 entreprises.
"""
import math

import pandas as pd

import config
from modele import Argument, limiter

# clé : (plus haut = meilleur ?, texte si meilleur, texte si moins bon)
RATIOS = {
    "croissance_ca": (True, "une croissance du chiffre d'affaires supérieure à la moyenne",
                      "une croissance du chiffre d'affaires inférieure à la moyenne"),
    "marge_nette": (True, "une marge nette supérieure à la moyenne",
                    "une marge nette inférieure à la moyenne"),
    "per": (False, "un PER plus bas que la moyenne (action moins chère)",
            "un PER plus élevé que la moyenne (action plus chère)"),
    "dette_ebitda": (False, "un endettement plus faible que la moyenne",
                     "un endettement plus élevé que la moyenne"),
    "rendement_total": (True, "un rendement sur 1 an supérieur à la moyenne",
                        "un rendement sur 1 an inférieur à la moyenne"),
}

LIBELLES = {
    "croissance_ca": "Croissance du CA",
    "marge_nette": "Marge nette",
    "per": "PER",
    "dette_ebitda": "Dette nette ÷ EBITDA",
    "rendement_total": "Rendement total 1 an",
}


def _division(a, b):
    try:
        if a is None or b is None or pd.isna(a) or pd.isna(b) or b == 0:
            return math.nan
        return float(a) / float(b)
    except (TypeError, ValueError):
        return math.nan


COLONNES_COMPTES = ["chiffre_affaires", "resultat_net", "bpa", "dette_nette", "ebitda", "dividende"]


def _dernieres_valeurs(comptes_action: pd.DataFrame) -> pd.Series:
    """
    Pour chaque donnée, la valeur de l'exercice le plus récent où elle est renseignée.
    Les comptes se remplissent souvent en plusieurs fois (le chiffre d'affaires est connu avant
    l'EBITDA) : sans ce report, une seule case vide dans le dernier exercice ferait disparaître
    le ratio correspondant au lieu d'utiliser la dernière valeur connue.
    """
    return comptes_action.ffill().iloc[-1]


def exercices_incomplets(comptes: pd.DataFrame) -> dict:
    """
    {code: [données manquantes]} pour le dernier exercice de chaque action, et {} si tout est
    renseigné. Sert à prévenir dans l'écran Données que les ratios reposent sur des comptes
    partiels (voir `_dernieres_valeurs`).
    """
    if comptes.empty:
        return {}
    manquants = {}
    for code in config.ACTIONS:
        c = comptes[comptes["code"] == code].sort_values("annee")
        if c.empty:
            continue
        dernier = c.iloc[-1]
        vides = [col for col in COLONNES_COMPTES if col in c.columns and pd.isna(dernier[col])]
        if vides:
            manquants[code] = vides
    return manquants


def dernier_exercice(comptes: pd.DataFrame):
    """Année du dernier exercice renseigné, ou None."""
    if comptes.empty or "annee" not in comptes.columns:
        return None
    return int(comptes["annee"].max())


def calculer_ratios(comptes: pd.DataFrame, cours: dict) -> pd.DataFrame:
    """
    Calcule les 5 ratios de chaque action.
    comptes : contenu de data/comptes.csv ; cours : {code: DataFrame des cours}
    """
    lignes = {}
    for code in config.ACTIONS:
        r = dict.fromkeys(RATIOS, math.nan)
        c = comptes[comptes["code"] == code].sort_values("annee") if not comptes.empty else pd.DataFrame()
        df = cours.get(code)
        dernier = float(df["cloture"].iloc[-1]) if df is not None and not df.empty else math.nan

        if not c.empty:
            n = _dernieres_valeurs(c)
            ca = c["chiffre_affaires"].dropna()
            if len(ca) >= 2:
                r["croissance_ca"] = _division(ca.iloc[-1], ca.iloc[-2]) - 1
            r["marge_nette"] = _division(n["resultat_net"], n["chiffre_affaires"])
            if n["bpa"] > 0:
                r["per"] = _division(dernier, n["bpa"])
            if n["ebitda"] > 0:
                r["dette_ebitda"] = _division(n["dette_nette"], n["ebitda"])
            dividende = n["dividende"] if not pd.isna(n["dividende"]) else 0.0
        else:
            dividende = 0.0

        # Rendement total sur 1 an = (cours − cours il y a 1 an + dividende) ÷ cours il y a 1 an
        if df is not None and len(df) > 200:
            il_y_a_un_an = df.index[-1] - pd.Timedelta(days=365)
            anciens = df[df.index >= il_y_a_un_an]["cloture"]
            if not anciens.empty:
                r["rendement_total"] = _division(dernier - anciens.iloc[0] + dividende, anciens.iloc[0])
        lignes[code] = r
    return pd.DataFrame.from_dict(lignes, orient="index")


def note_financiere(code: str, ratios: pd.DataFrame):
    """
    Algorithme A3. Renvoie (note, arguments).
    Chaque ratio meilleur que la moyenne des 5 = +1, moins bon = −1 ; note = total ÷ 5 × 2.
    """
    if ratios.empty or code not in ratios.index:
        return 0.0, []
    total = 0
    arguments = []
    for cle, (plus_haut_meilleur, texte_bon, texte_mauvais) in RATIOS.items():
        valeur = ratios.loc[code, cle]
        moyenne = ratios[cle].mean(skipna=True)
        if pd.isna(valeur) or pd.isna(moyenne) or valeur == moyenne:
            continue
        meilleur = valeur > moyenne if plus_haut_meilleur else valeur < moyenne
        point = 1 if meilleur else -1
        total += point
        arguments.append(Argument(texte_bon if meilleur else texte_mauvais, point * 2 / 5, "financier"))
    return limiter(total / 5 * 2), arguments
