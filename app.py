"""
CAP 500 – interface de gestion du portefeuille de 500 000 €.
Lancer avec :  streamlit run app.py   (ou F5 dans VS Code)

Déroulement (logigramme 1 du dossier de conception) :
connexion ou création de compte → [profil de risque] → [investissement du capital] → chargement des données et calculs → menu
"""
import time
from datetime import date

import streamlit as st

import base
import config
import donnees
import ecrans
import portefeuille
import style

st.set_page_config(page_title=config.NOM_APPLI, page_icon=style.icone_page(), layout="wide")
style.appliquer_style()
base.initialiser()

# ---------- Déconnexion automatique après 30 minutes sans activité ----------
if st.session_state.get("connecte"):
    inactivite = time.time() - st.session_state.get("derniere_activite", time.time())
    if inactivite > config.INACTIVITE_MIN * 60:
        base.sauvegarder()
        ecrans.deconnecter(f"Session fermée après {config.INACTIVITE_MIN} minutes sans activité.")
    else:
        st.session_state["derniere_activite"] = time.time()

# ---------- Connexion ou création de compte (logigramme 2) ----------
if not st.session_state.get("connecte"):
    ecrans.ecran_connexion()
    st.stop()
if "code_a_noter" in st.session_state:          # juste après la création du compte
    ecrans.ecran_code_recuperation()
    st.stop()

uid = st.session_state["uid"]

# ---------- Chargement des données (logigramme 4) ----------
statut = ecrans.actualiser_donnees(date.today().isoformat())
prix = donnees.cours_actuels()
reglages = base.lire_reglages(uid)

# ---------- Protection contre les pertes (A8) ----------
niveau, message = portefeuille.controler_perte(uid, prix, reglages["taux_frais"])

# ---------- Menu et messages ----------
ecrans.barre_laterale(statut)
ecrans.afficher_flash()
ecrans.afficher_etat_donnees(statut)
if niveau == "vente":
    st.error(message)
    st.toast(message, icon=":material/warning:")
elif niveau in ("alerte", "limite"):
    st.warning(message)

analyses = ecrans.analyses_courantes(statut)

# ---------- Affichage de l'écran choisi ----------
page = st.session_state.get("page", "Accueil")
if page == "Accueil":
    ecrans.ecran_accueil(analyses, prix)
elif page == "Investir mon capital":
    ecrans.ecran_repartition(prix, analyses)
elif page == "Les actions":
    ecrans.ecran_fiche_action(analyses)
elif page == "Acheter / vendre":
    ecrans.ecran_achat_vente(analyses)
elif page == "Mon profil":
    ecrans.ecran_profil()
elif page == "Historique":
    ecrans.ecran_historique()
elif page == "Réglages":
    ecrans.ecran_reglages()
else:
    ecrans.ecran_guide()

st.markdown(f"<div class='hk-pied'>{config.NOM_APPLI} · argent virtuel, vrais prix de la Bourse de Paris "
            "(Yahoo Finance) · les conseils ne sont pas une garantie de gain</div>", unsafe_allow_html=True)
