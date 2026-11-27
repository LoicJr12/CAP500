"""
Paramètres généraux de l'application.
Modifier ce fichier pour changer les actions, le capital ou les règles de sécurité.
"""
from pathlib import Path

# ---------- Dossiers et fichiers ----------
DOSSIER_PROJET = Path(__file__).resolve().parent
DOSSIER_DONNEES = DOSSIER_PROJET / "data"
DB_PATH = DOSSIER_DONNEES / "portefeuille.db"
DOSSIER_SAUVEGARDES = DOSSIER_DONNEES / "sauvegardes"
FICHIER_COMPTES = DOSSIER_DONNEES / "comptes.csv"
FICHIER_ANALYSTES = DOSSIER_DONNEES / "analystes.csv"

# ---------- Les 5 actions autorisées (code Yahoo Finance -> nom) ----------
ACTIONS = {
    "RMS.PA": "Hermès",
    "AI.PA": "Air Liquide",
    "TTE.PA": "TotalEnergies",
    "DSY.PA": "Dassault Systèmes",
    "CAP.PA": "Capgemini",
}
INDICE = "^FCHI"
NOM_INDICE = "CAC 40"

# ---------- Marque ----------
NOM_APPLI = "CAP 500"
DOSSIER_ASSETS = DOSSIER_PROJET / "assets"

# ---------- Capital ----------
CAPITAL = 500_000.0

# ---------- Réglages du moteur (modifiables dans l'écran Réglages) ----------
REGLAGES_DEFAUT = {
    "poids_graphique": 0.40,
    "poids_infos": 0.25,
    "poids_financier": 0.20,
    "poids_hasard": 0.15,
    "seuil_achat": 0.5,
    "seuil_vente": -0.5,
    "taux_frais": 0.001,  # 0,1 % du montant de l'ordre
}

# ---------- Profils de risque ----------
# La perte maximale ne dépasse jamais 10 % (exigence du client).
PROFIL_DEFAUT = "Équilibré"
PROFILS = {
    "Prudent": {
        "seuil_achat": 0.8,         # achat conseillé seulement si les signaux sont très nets
        "seuil_vente": -0.3,        # vente conseillée plus tôt
        "max_par_action": 0.25,     # 25 % du portefeuille au plus sur une même action
        "reserve_min": 0.20,        # 20 % du portefeuille toujours en liquidités
        "var_max": 0.06,            # risque de perte sur 1 semaine accepté (A4)
        "seuil_alerte": -0.04,      # alerte orange
        "seuil_vente_auto": -0.06,  # vente automatique de toutes les actions
    },
    "Équilibré": {
        "seuil_achat": 0.5, "seuil_vente": -0.5, "max_par_action": 0.40, "reserve_min": 0.10,
        "var_max": 0.10, "seuil_alerte": -0.08, "seuil_vente_auto": -0.10,
    },
    "Dynamique": {
        "seuil_achat": 0.3, "seuil_vente": -0.7, "max_par_action": 0.60, "reserve_min": 0.0,
        "var_max": 0.14, "seuil_alerte": -0.08, "seuil_vente_auto": -0.10,
    },
}
RESUME_PROFILS = {
    "Prudent": "Protéger le capital avant tout.",
    "Équilibré": "Faire croître le capital avec un risque mesuré.",
    "Dynamique": "Chercher la performance en acceptant plus de variations.",
}

# ---------- Simulation Monte-Carlo (A4) ----------
NB_SIMULATIONS = 10_000
HORIZON_JOURS = 5          # une semaine de bourse
PERTE_MAX_SIMULATION = 0.10  # valeur par défaut (profil Équilibré)

# ---------- Sécurité ----------
LONGUEUR_MIN_MDP = 8
MAX_ESSAIS = 5
DUREE_BLOCAGE_MIN = 15
INACTIVITE_MIN = 30
NB_SAUVEGARDES = 7

# Attente maximale quand la base est occupée par une autre personne (secondes)
ATTENTE_BASE_S = 15.0

# Intervalle entre deux prolongations de la session en base (minutes)
PROLONGATION_SESSION_MIN = 5
