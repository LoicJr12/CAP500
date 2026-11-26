"""
Gestion du portefeuille : ordres (A7), valeur, protection contre les pertes (A8),
répartition de départ, historique.
"""
import math
from datetime import date, datetime

import pandas as pd

import base
import config
import donnees
from affichage import euros, nombre, pourcent


# =====================================================================
# Lecture de l'état du portefeuille
# =====================================================================
def lire_ordres(uid: int) -> pd.DataFrame:
    """Ordres du portefeuille en cours du compte."""
    with base.ouvrir() as con:
        return pd.read_sql_query("SELECT * FROM ordres WHERE utilisateur_id = ? AND portefeuille = ? ORDER BY id",
                                 con, params=(uid, base.portefeuille_courant(uid)))


def positions(uid: int) -> dict:
    """{code: {"quantite": .., "prix_revient": ..}} pour les actions détenues."""
    suivi = {}
    for o in lire_ordres(uid).itertuples():
        p = suivi.setdefault(o.code, {"quantite": 0, "cout": 0.0})
        if o.sens == "achat":
            p["cout"] += o.quantite * o.prix + o.frais
            p["quantite"] += o.quantite
        else:
            if p["quantite"] > 0:
                p["cout"] -= p["cout"] * o.quantite / p["quantite"]
            p["quantite"] -= o.quantite
    return {
        code: {"quantite": p["quantite"], "prix_revient": p["cout"] / p["quantite"]}
        for code, p in suivi.items() if p["quantite"] > 0
    }


def liquidites(uid: int) -> float:
    with base.ouvrir() as con:
        mouvement = con.execute(
            "SELECT SUM(CASE sens WHEN 'achat' THEN -(quantite * prix + frais) "
            "ELSE quantite * prix - frais END) FROM ordres WHERE utilisateur_id = ? AND portefeuille = ?",
            (uid, base.portefeuille_courant(uid)),
        ).fetchone()[0]
    return config.CAPITAL + (mouvement or 0.0)


def valeur(uid: int, prix: dict) -> dict:
    """Valeur totale = liquidités + Σ (quantité × dernier cours)."""
    pos = positions(uid)
    titres = sum(p["quantite"] * prix.get(code, p["prix_revient"]) for code, p in pos.items())
    liq = liquidites(uid)
    total = liq + titres
    return {"valeur": total, "liquidites": liq, "titres": titres,
            "perte": (total - config.CAPITAL) / config.CAPITAL}


def depart_fait(uid: int) -> bool:
    return bool(base.lire_reglages(uid).get("depart_fait")) or not lire_ordres(uid).empty


def limite_atteinte(uid: int) -> bool:
    return bool(base.lire_reglages(uid).get("limite_atteinte"))


# =====================================================================
# A7 – Passer un ordre
# =====================================================================
def calculer_frais(montant: float, taux: float) -> float:
    return round(montant * taux, 2)


def verifier_ordre(uid: int, code: str, sens: str, quantite, prix, taux: float, automatique: bool = False,
                   controle_profil: bool = True):
    """Contrôles avant un ordre (règles RG2 à RG5 et limites du profil de risque). Renvoie (ok, message)."""
    if code not in config.ACTIONS:
        return False, "Seules les 5 actions du portefeuille peuvent être achetées."
    if sens not in ("achat", "vente"):
        return False, "Choisissez achat ou vente."
    if isinstance(quantite, bool) or not isinstance(quantite, int) or quantite <= 0:
        return False, "Saisissez un nombre entier supérieur à 0."
    if prix is None or not prix > 0 or math.isnan(prix):
        return False, "Cours indisponible pour le moment."

    montant = quantite * prix
    frais = calculer_frais(montant, taux)
    if sens == "achat":
        if limite_atteinte(uid) and not automatique:
            return False, "Limite de perte atteinte : les achats sont bloqués."
        manque = montant + frais - liquidites(uid)
        if manque > 1e-6:
            return False, f"Liquidités insuffisantes : il vous manque {euros(manque)}."
        if controle_profil and not automatique:
            message = controler_profil(uid, code, quantite, prix, montant + frais)
            if message:
                return False, message
    else:
        detenus = positions(uid).get(code, {}).get("quantite", 0)
        if quantite > detenus:
            return False, f"Vous détenez seulement {nombre(detenus, 0)} titre{'s' if detenus > 1 else ''}."
    return True, ""


def controler_profil(uid: int, code: str, quantite: int, prix: float, cout: float):
    """Limites du profil de risque pour un achat : part maximale par action et réserve de liquidités."""
    r = base.lire_reglages(uid)
    etat = valeur(uid, {**donnees.cours_actuels(), code: prix})
    total = etat["valeur"]
    detenus = positions(uid).get(code, {}).get("quantite", 0)
    part = (detenus + quantite) * prix / total
    if part > r["max_par_action"] + 1e-9:
        maximum = max(int(r["max_par_action"] * total / prix) - detenus, 0)
        return (f"Profil {r['profil']} : une action ne doit pas dépasser {pourcent(r['max_par_action'], 0)} "
                f"du portefeuille (ici {pourcent(part, 0)}). Vous pouvez acheter au plus "
                f"{nombre(maximum, 0)} titre{'s' if maximum > 1 else ''}.")
    if etat["liquidites"] - cout < r["reserve_min"] * total - 0.01:
        return (f"Profil {r['profil']} : gardez au moins {pourcent(r['reserve_min'], 0)} en liquidités "
                f"({euros(r['reserve_min'] * total)}).")
    return None


def passer_ordre(uid: int, code: str, sens: str, quantite, prix: float, taux: float, automatique: bool = False,
                 controle_profil: bool = True):
    """Algorithme A7 : contrôle puis enregistre l'ordre. Renvoie (ok, message)."""
    ok, message = verifier_ordre(uid, code, sens, quantite, prix, taux, automatique, controle_profil)
    if not ok:
        return False, message
    frais = calculer_frais(quantite * prix, taux)
    with base.ouvrir() as con:
        con.execute(
            "INSERT INTO ordres (utilisateur_id, portefeuille, date, code, sens, quantite, prix, frais, automatique) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, base.portefeuille_courant(uid), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), code, sens,
             quantite, prix, frais, int(automatique)),
        )
    return True, (f"Ordre enregistré : {sens} de {nombre(quantite, 0)} {config.ACTIONS[code]} "
                  f"à {euros(prix)}.")


# =====================================================================
# A8 – Protection contre les pertes
# =====================================================================
def controler_perte(uid: int, prix: dict, taux: float):
    """
    Renvoie (niveau, message) :
      "vente"  : perte ≤ limite du profil (−10 % au plus) → toutes les actions viennent d'être vendues
      "limite" : la limite a déjà été atteinte (portefeuille en liquidités)
      "alerte" : perte ≤ seuil d'alerte du profil (−8 % pour Équilibré)
      None     : pas d'alerte
    """
    r = base.lire_reglages(uid)
    limite = pourcent(-r["seuil_vente_auto"], 0)
    etat = valeur(uid, prix)
    perte = etat["perte"]
    pos = positions(uid)

    if perte <= r["seuil_vente_auto"]:
        vendues = 0
        for code, p in pos.items():
            if code in prix:
                ok, _ = passer_ordre(uid, code, "vente", p["quantite"], prix[code], taux, automatique=True)
                vendues += ok
        base.ecrire_reglage(uid, "limite_atteinte", True)
        if vendues:
            return "vente", f"Limite de {limite} atteinte : toutes vos actions ont été vendues automatiquement."
        return "limite", (f"Limite de {limite} atteinte (perte de {pourcent(-perte)}) : "
                          "votre portefeuille est en liquidités et les achats sont bloqués.")

    if perte <= r["seuil_alerte"]:
        return "alerte", (f"Attention : votre portefeuille a perdu {pourcent(-perte)}. "
                          f"Vente automatique à −{limite}.")
    return None, None


# =====================================================================
# Répartition de départ
# =====================================================================
def quantite_possible(montant: float, prix: float, taux: float) -> int:
    """Nombre de titres achetables avec un montant, frais compris (arrondi vers le bas)."""
    if not montant or not prix:
        return 0
    return int(montant // (prix * (1 + taux)))


def repartir(uid: int, montants: dict, prix: dict, taux: float):
    """Achète les titres de la répartition de départ. Renvoie (ok, message)."""
    if depart_fait(uid):
        return False, "La répartition de départ a déjà été faite."
    total = sum(montants.values())
    if total > config.CAPITAL:
        return False, f"Le total dépasse votre capital de {euros(total - config.CAPITAL)}."
    if total <= 0:
        return False, "Saisissez au moins un montant."
    r = base.lire_reglages(uid)
    for code, montant in montants.items():
        if montant > 0 and code not in prix:
            return False, f"Cours indisponible pour {config.ACTIONS[code]} : réessayez plus tard."
        if montant > r["max_par_action"] * config.CAPITAL + 0.01:
            return False, (f"Profil {r['profil']} : {config.ACTIONS[code]} ne doit pas dépasser "
                           f"{euros(r['max_par_action'] * config.CAPITAL, 0)} "
                           f"({pourcent(r['max_par_action'], 0)} du capital).")
    if config.CAPITAL - total < r["reserve_min"] * config.CAPITAL - 0.01:
        return False, (f"Profil {r['profil']} : gardez au moins {euros(r['reserve_min'] * config.CAPITAL, 0)} "
                       f"en liquidités ({pourcent(r['reserve_min'], 0)} du capital).")

    lignes = 0
    for code, montant in montants.items():
        quantite = quantite_possible(montant, prix.get(code), taux)
        if quantite > 0:
            ok, message = passer_ordre(uid, code, "achat", quantite, prix[code], taux, controle_profil=False)
            if not ok:
                return False, message
            lignes += 1
    base.ecrire_reglage(uid, "depart_fait", True)
    s = "s" if lignes > 1 else ""
    return True, (f"Portefeuille de départ enregistré : {lignes} action{s} achetée{s}, "
                  f"{euros(liquidites(uid))} en liquidités.")


def repartition_conseillee(scores: dict, reglages: dict) -> dict:
    """
    Répartition proposée selon le profil : plus le score est élevé, plus le montant est grand.
    Les actions à vendre sont exclues, chaque action est plafonnée et la réserve est respectée.
    """
    budget = config.CAPITAL * (1 - reglages["reserve_min"] - 0.01)   # 1 % de marge pour les frais
    plafond = reglages["max_par_action"] * config.CAPITAL
    poids = {c: s - reglages["seuil_vente"] for c, s in scores.items() if s > reglages["seuil_vente"]}
    montants = {c: 0.0 for c in scores}
    while poids and budget > 1:
        total = sum(poids.values())
        parts = {c: budget * p / total for c, p in poids.items()}
        depasse = {c for c, m in parts.items() if montants[c] + m >= plafond}
        if not depasse:
            for c, m in parts.items():
                montants[c] += m
            break
        for c in depasse:
            budget -= plafond - montants[c]
            montants[c] = plafond
            del poids[c]
    return {c: math.floor(m / 100) * 100 for c, m in montants.items()}


# =====================================================================
# Historique
# =====================================================================
def enregistrer_historique(uid: int, valeur_totale: float, liquidites_: float, cac40) -> None:
    """Une ligne par jour (la dernière valeur de la journée remplace la précédente)."""
    with base.ouvrir() as con:
        con.execute(
            "INSERT OR REPLACE INTO historique (utilisateur_id, portefeuille, date, valeur, liquidites, cac40) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uid, base.portefeuille_courant(uid), date.today().isoformat(), valeur_totale, liquidites_, cac40),
        )


def lire_historique(uid: int) -> pd.DataFrame:
    with base.ouvrir() as con:
        df = pd.read_sql_query(
            "SELECT date, valeur, liquidites, cac40 FROM historique "
            "WHERE utilisateur_id = ? AND portefeuille = ? ORDER BY date",
            con, params=(uid, base.portefeuille_courant(uid)))
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df
