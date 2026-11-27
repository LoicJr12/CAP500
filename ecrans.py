"""
Les écrans de l'interface Streamlit (voir le dossier de spécification, section 3).
Les textes sont écrits pour être compris par une personne qui ne connaît pas la bourse.
"""
import io
import json
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import auth
import base
import config
import donnees
import financier
import graphique
import horloge
import moteur
import portefeuille
import profil
import style
import textes
from affichage import date_fr, date_longue, euros, lire_nombre, nombre, pourcent, texte_nombre
from style import COULEURS_CONSEIL, GRIS, MARINE, OR, ROUGE, VERT, icone

PAGES = ["Accueil", "Investir mon capital", "Les actions", "Acheter / vendre", "Mon profil", "Historique",
         "Réglages", "Guide"]
ICONES = {
    "Accueil": ":material/home:",
    "Investir mon capital": ":material/rocket_launch:",
    "Les actions": ":material/query_stats:",
    "Acheter / vendre": ":material/swap_horiz:",
    "Mon profil": ":material/shield_person:",
    "Historique": ":material/history:",
    "Réglages": ":material/settings:",
    "Guide": ":material/menu_book:",
}
COULEURS_TONALITE = {1: VERT, 0: "#B8C0CC", -1: ROUGE}


# =====================================================================
# Outils communs
# =====================================================================
def html(texte: str, conteneur=None) -> None:
    (conteneur or st).markdown(texte, unsafe_allow_html=True)


def uid() -> int:
    return st.session_state["uid"]


def flash(type_message: str, texte: str) -> None:
    """Garde un message à afficher au prochain affichage de la page."""
    st.session_state["flash"] = (type_message, texte)


def afficher_flash() -> None:
    if "flash" in st.session_state:
        type_message, texte = st.session_state.pop("flash")
        getattr(st, type_message)(texte)


def aller_a(page: str, code: str = None) -> None:
    st.session_state["page"] = page
    if code:
        st.session_state["action_choisie"] = code


CLE_JETON = "s"        # nom du paramètre de session dans l'adresse de la page


def deconnecter(message: str = None) -> None:
    # La session est fermée en base avant de vider st.session_state : une adresse copiée
    # ailleurs ne doit plus donner accès au compte après une déconnexion.
    auth.fermer_session(st.session_state.get("jeton"))
    st.query_params.pop(CLE_JETON, None)
    for cle in list(st.session_state.keys()):
        del st.session_state[cle]
    if message:
        st.session_state["message_connexion"] = message


def page_de_depart(numero: int) -> str:
    """Là où en est la personne : choisir son profil, investir son capital, ou l'accueil."""
    if not base.lire_reglages(numero).get("profil_defini"):
        return "Mon profil"
    return "Accueil" if portefeuille.depart_fait(numero) else "Investir mon capital"


def reprendre_session() -> bool:
    """
    Rattache la personne à son compte après un rafraîchissement de la page, grâce au jeton
    présent dans l'adresse (Streamlit vide st.session_state à chaque rechargement).
    Renvoie True si la session a été reprise.
    """
    jeton = st.query_params.get(CLE_JETON)
    numero = auth.session_valide(jeton)
    if numero is None:
        if jeton:                                   # jeton inconnu ou expiré : on nettoie l'adresse
            st.query_params.pop(CLE_JETON, None)
        return False
    st.session_state.update(connecte=True, uid=numero, identifiant=auth.identifiant(numero),
                            derniere_activite=time.time(), jeton=jeton,
                            derniere_prolongation=time.time(), page=page_de_depart(numero))
    return True


def pages_du_menu() -> list:
    """« Investir mon capital » n'apparaît que tant que le capital n'est pas investi."""
    if portefeuille.depart_fait(uid()):
        return [p for p in PAGES if p != "Investir mon capital"]
    return PAGES


def choisir_action(conteneur=None, libelle: str = "Entreprise") -> str:
    codes = list(config.ACTIONS)
    if st.session_state.get("action_choisie") not in codes:
        st.session_state["action_choisie"] = codes[0]
    return (conteneur or st).selectbox(libelle, codes, format_func=config.ACTIONS.get, key="action_choisie")


def champ_nombre(libelle: str, cle: str, defaut=None, conteneur=None, entier: bool = False,
                 aide: str = None, masquer_libelle: bool = False, exemple: str = None):
    """Champ qui accepte la virgule et les espaces (« 12 500,50 »). Renvoie le nombre ou None."""
    conteneur = conteneur or st
    if cle not in st.session_state:
        st.session_state[cle] = "" if defaut is None else texte_nombre(defaut, 0 if entier else 2)
    texte = conteneur.text_input(libelle, key=cle, help=aide,
                                 placeholder=exemple or ("ex. 150" if entier else "ex. 25 000"),
                                 label_visibility="collapsed" if masquer_libelle else "visible")
    valeur = lire_nombre(texte)
    if texte.strip() and valeur is None:
        conteneur.caption(":red[Écrivez un nombre, par exemple 25 000 ou 12,5]")
    return valeur


def variation(x, decimales: int = 1) -> str:
    return f"<span class='{style.classe_variation(x)}'>{pourcent(x, decimales, signe=True)}</span>"


def question(numero: int, texte: str, conteneur=None) -> None:
    html(f"<div class='hk-question'><span class='hk-etape-num'>{numero}</span>{texte}</div>", conteneur)


def recap(lignes: list, total: tuple = None) -> str:
    contenu = "".join(f"<div class='hk-recap'><span>{a}</span><b>{b}</b></div>" for a, b in lignes)
    if total:
        contenu += f"<div class='hk-recap total'><span>{total[0]}</span><span>{total[1]}</span></div>"
    return contenu


# =====================================================================
# Données et calculs (logigramme 4), gardés en mémoire 1 heure
# =====================================================================
@st.cache_data(ttl=3600, show_spinner="Mise à jour des prix et des actualités…")
def actualiser_donnees(jour: str) -> dict:
    cours = donnees.mettre_a_jour_cours()
    actus = {code: donnees.telecharger_actualites(code) for code in config.ACTIONS}
    return {"cours": cours, "actus": actus, "heure": horloge.maintenant().strftime("%d/%m/%Y à %H:%M")}


@st.cache_data(ttl=3600, show_spinner="Calcul des conseils…")
def calculer_analyses(reglages_json: str, jeton: str) -> dict:
    reglages = json.loads(reglages_json)
    cours = {code: donnees.lire_cours(code) for code in config.ACTIONS}
    ratios = financier.calculer_ratios(donnees.charger_comptes(), cours)
    analystes = donnees.charger_analystes()
    graine = int(horloge.aujourdhui().strftime("%Y%m%d"))   # même simulation toute la journée
    analyses = {}
    for i, (code, df) in enumerate(cours.items()):
        if len(df) >= 2:
            analyses[code] = moteur.analyser(code, df, ratios, analystes, donnees.actualites_semaine(code),
                                             reglages, graine + i)
    return analyses


def analyses_courantes(statut: dict) -> dict:
    reglages = base.lire_reglages(uid())
    cles = {k: reglages[k] for k in [*config.REGLAGES_DEFAUT, "var_max"]}
    return calculer_analyses(json.dumps(cles, sort_keys=True), statut["heure"])


def tout_recalculer() -> None:
    actualiser_donnees.clear()
    calculer_analyses.clear()


def afficher_etat_donnees(statut: dict) -> None:
    """Message si les prix n'ont pas pu être mis à jour (logigramme 4)."""
    echecs = [code for code in config.ACTIONS if not statut["cours"].get(code)]
    if not echecs:
        return
    sans_donnees = [config.ACTIONS[c] for c in echecs if donnees.dernier_cours(c)[0] is None]
    if sans_donnees:
        st.error("Aucun prix disponible pour : " + ", ".join(sans_donnees)
                 + ". Vérifiez la connexion internet, ou importez les prix dans Réglages → Données.")
    anciens = [c for c in echecs if donnees.dernier_cours(c)[0] is not None]
    if anciens:
        derniere = max(donnees.dernier_cours(c)[1] for c in anciens)
        st.warning(f"Les prix n'ont pas pu être mis à jour (connexion internet ?). "
                   f"Les calculs utilisent les derniers prix connus, du {date_fr(derniere)}.")


# =====================================================================
# Connexion et création de compte
# =====================================================================
def ecran_connexion() -> None:
    gauche, _, droite = st.columns([1.15, 0.06, 1], vertical_alignment="center")
    html(f"""<div class='hk-hero'>
        {style.logo_html(clair=True, largeur=200)}
        <div class='hk-hero-titre'>Investissez 500 000 €<br><span class='hk-or'>en toute simplicité.</span></div>
        <p>CAP 500 vous conseille sur 5 grandes entreprises françaises et vous explique
        chaque conseil avec des mots simples.</p>
        <div class='hk-atout'><div class='hk-atout-icone'>{icone('conseil', 22, OR)}</div>
          <div><b>Des conseils expliqués</b><br>Acheter, vendre ou attendre : on vous dit toujours pourquoi.</div></div>
        <div class='hk-atout'><div class='hk-atout-icone'>{icone('bouclier', 22, OR)}</div>
          <div><b>Une protection automatique</b><br>Si la perte atteint votre limite, tout est vendu pour vous protéger.</div></div>
        <div class='hk-atout'><div class='hk-atout-icone'>{icone('courbe', 22, OR)}</div>
          <div><b>Un suivi clair</b><br>Votre gain ou votre perte en un coup d'œil, comparé au CAC 40.</div></div>
        <div class='hk-hero-pied'>Argent virtuel · vrais prix de la Bourse de Paris · Hermès, Air Liquide,
        TotalEnergies, Dassault Systèmes, Capgemini</div>
    </div>""", gauche)

    with droite:
        html("<div class='hk-acces-titre'>Bienvenue</div>"
             "<div class='hk-soustitre' style='margin-bottom:1rem'>Connectez-vous, ou créez votre compte "
             "en 1 minute.</div>")
        if "message_connexion" in st.session_state:
            st.info(st.session_state.pop("message_connexion"))
        with st.container(border=True):
            onglet_connexion, onglet_creation = st.tabs(["Se connecter", "Créer un compte"])
            with onglet_connexion:
                formulaire_connexion()
                with st.expander("Mot de passe oublié ?"):
                    formulaire_oubli()
            with onglet_creation:
                formulaire_creation()


def ouvrir_session(numero: int, identifiant: str, code: str = None) -> None:
    """Après connexion : on envoie la personne là où elle en est (profil, investissement ou accueil)."""
    base.sauvegarder()
    jeton = auth.ouvrir_session(numero)
    st.query_params[CLE_JETON] = jeton          # survit au rafraîchissement de la page
    st.session_state.update(connecte=True, uid=numero, identifiant=auth.identifiant(numero),
                            derniere_activite=time.time(), jeton=jeton,
                            derniere_prolongation=time.time(), page=page_de_depart(numero))
    if code:
        st.session_state["code_a_noter"] = code
    st.rerun()


def formulaire_connexion() -> None:
    with st.form("connexion", border=False):
        identifiant = st.text_input("Identifiant", placeholder="Votre identifiant", key="connexion_identifiant")
        mdp = st.text_input("Mot de passe", type="password", placeholder="Votre mot de passe", key="connexion_mdp")
        if st.form_submit_button("Se connecter", type="primary", width="stretch"):
            ok, message, numero = auth.verifier(identifiant, mdp)
            if ok:
                ouvrir_session(numero, identifiant)
            st.error(message)
    st.caption("Pas encore de compte ? Cliquez sur l'onglet « Créer un compte ».")


def formulaire_creation() -> None:
    with st.form("creation_compte", border=False):
        identifiant = st.text_input("Choisissez un identifiant", placeholder="ex. lamine.d", key="creation_identifiant",
                                    help="C'est le nom que vous taperez pour vous connecter (3 à 30 caractères).")
        mdp = st.text_input("Choisissez un mot de passe", type="password", key="creation_mdp",
                            placeholder=f"{config.LONGUEUR_MIN_MDP} caractères minimum")
        confirmation = st.text_input("Retapez le mot de passe", type="password", key="creation_confirmation")
        if st.form_submit_button("Créer mon compte", type="primary", width="stretch"):
            ok, message, numero = auth.creer_compte(identifiant, mdp, confirmation)
            if ok:
                ouvrir_session(numero, identifiant, auth.nouveau_code_recuperation(numero))
            st.error(message)
    html(f"<div style='display:flex;gap:.5rem;align-items:center;color:{GRIS};font-size:.85rem'>"
         f"{icone('cadenas', 16, GRIS)} Gratuit · aucune donnée bancaire · 500 000 € virtuels pour commencer</div>")


def formulaire_oubli() -> None:
    st.caption("Saisissez le code de récupération reçu à la création de votre compte. "
               "Votre portefeuille est conservé.")
    with st.form("oubli", border=False):
        identifiant = st.text_input("Identifiant", key="oubli_identifiant")
        code = st.text_input("Code de récupération", placeholder="XXXX-XXXX-XXXX")
        mdp = st.text_input("Nouveau mot de passe", type="password")
        confirmation = st.text_input("Retapez le nouveau mot de passe", type="password")
        if st.form_submit_button("Changer mon mot de passe", width="stretch"):
            ok, message, numero = auth.mot_de_passe_oublie(identifiant, code, mdp, confirmation)
            if ok:
                ouvrir_session(numero, identifiant, auth.nouveau_code_recuperation(numero))
            st.error(message)


def ecran_code_recuperation() -> None:
    """Affiché une seule fois, juste après la création du compte (ou un changement de mot de passe)."""
    _, centre, _ = st.columns([1, 1.4, 1])
    code = st.session_state["code_a_noter"]
    with centre:
        html(f"<div style='text-align:center;margin:2rem 0 1.2rem'>{style.logo_html(largeur=230)}</div>")
        with st.container(border=True):
            html(f"<div style='display:flex;gap:.6rem;align-items:center'>{style.rond('valide', VERT)}"
                 f"<div class='hk-acces-titre' style='margin:0;font-size:1.4rem'>Votre compte est prêt</div></div>")
            st.write("Voici votre **code de récupération**. Il sert à choisir un nouveau mot de passe si vous "
                     "oubliez le vôtre. **Il ne sera plus jamais affiché** : notez-le ou téléchargez-le.")
            html(f"<div class='hk-code'>{code}</div>")
            st.write("")
            st.download_button("Télécharger le code", icon=":material/download:", width="stretch",
                               data=(f"{config.NOM_APPLI} – code de récupération\n"
                                     f"Identifiant : {st.session_state['identifiant']}\nCode : {code}\n"),
                               file_name="cap500_code_recuperation.txt", mime="text/plain")
            note = st.checkbox("J'ai noté ou téléchargé mon code")
            st.button("Commencer", type="primary", width="stretch", disabled=not note,
                      on_click=lambda: st.session_state.pop("code_a_noter", None))


# =====================================================================
# Menu latéral
# =====================================================================
def barre_laterale(statut: dict) -> None:
    sb = st.sidebar
    reglages = base.lire_reglages(uid())
    nom = st.session_state.get("identifiant", "")
    html(f"<div style='margin:.3rem 0 1.5rem'>{style.logo_html(clair=True, largeur=180)}</div>", sb)
    html(f"<div style='display:flex;gap:.7rem;align-items:center;margin-bottom:1.2rem;padding:.7rem;"
         f"background:rgba(255,255,255,.06);border-radius:12px'>"
         f"<div class='hk-avatar'>{style.echapper(style.initiales(nom))}</div>"
         f"<div style='min-width:0'><div style='color:#FFFFFF;font-weight:700;overflow:hidden;"
         f"text-overflow:ellipsis'>{style.echapper(nom)}</div>"
         f"<div style='margin-top:.2rem'>"
         f"{style.pastille_profil(reglages['profil']) if reglages.get('profil_defini') else style.pastille('Profil à choisir', '#9FB0C8')}"
         f"</div></div></div>", sb)
    pages = pages_du_menu()
    if st.session_state.get("page") not in pages:
        st.session_state["page"] = "Accueil"
    sb.radio("Menu", pages, key="page", format_func=lambda p: f"{ICONES[p]} {p}", label_visibility="collapsed")
    sb.divider()
    sb.caption(f"Prix mis à jour le {statut['heure']}")
    if sb.button("Actualiser les prix", icon=":material/refresh:", width="stretch"):
        tout_recalculer()
        st.rerun()
    if sb.button("Se déconnecter", icon=":material/logout:", width="stretch"):
        base.sauvegarder()
        deconnecter("Vous êtes déconnecté. À bientôt !")
        st.rerun()


# =====================================================================
# Accueil (tableau de bord)
# =====================================================================
def ecran_accueil(analyses: dict, prix: dict) -> None:
    numero = uid()
    reglages = base.lire_reglages(numero)
    etat = portefeuille.valeur(numero, prix)
    gain = etat["valeur"] - config.CAPITAL
    cac = donnees.lire_cours(config.INDICE)
    cac_dernier = float(cac["cloture"].iloc[-1]) if not cac.empty else None
    cac_var = float(cac["cloture"].iloc[-1] / cac["cloture"].iloc[-2] - 1) if len(cac) > 1 else None
    portefeuille.enregistrer_historique(numero, etat["valeur"], etat["liquidites"], cac_dernier)
    pos = portefeuille.positions(numero)
    conseils = {code: moteur.conseiller(a, code in pos, reglages)[0] for code, a in analyses.items()}
    raisons = {code: raison_courte(a, conseils[code], reglages) for code, a in analyses.items()}

    style.entete(f"Bonjour {st.session_state.get('identifiant', '')}", date_longue(horloge.aujourdhui()),
                 "Voici où en est votre portefeuille aujourd'hui.")

    if not portefeuille.depart_fait(numero):
        with st.container(border=True):
            c1, c2 = st.columns([3, 1.2], vertical_alignment="center")
            c1.markdown("**Votre argent n'est pas encore investi.** Répartissez vos 500 000 € entre les 5 "
                        "entreprises : CAP 500 peut vous proposer une répartition adaptée à votre profil.")
            c2.button("Investir mon capital", type="primary", icon=":material/rocket_launch:", width="stretch",
                      on_click=aller_a, args=("Investir mon capital",))

    resume_du_jour(etat, gain, conseils, reglages)

    c = st.columns(4)
    style.kpi(c[0], "Valeur de mon portefeuille", euros(etat["valeur"], 0),
              f"{pourcent(etat['perte'], 2, signe=True)} depuis le départ", accent=True,
              explication="Vos actions au prix du jour + votre argent disponible.")
    style.kpi(c[1], "Gain ou perte", f"<span class='{style.classe_variation(gain)}'>{euros(gain, 0)}</span>",
              "par rapport aux 500 000 € de départ",
              explication="Positif : vous avez gagné de l'argent. Négatif : vous en avez perdu.")
    part_liq = etat["liquidites"] / etat["valeur"] if etat["valeur"] else 0
    style.kpi(c[2], "Argent disponible", euros(etat["liquidites"], 0),
              f"{pourcent(part_liq, 0)} du portefeuille, prêt à être investi",
              explication="L'argent qui n'est pas placé en actions (on parle aussi de liquidités).")
    style.kpi(c[3], "Marché français (CAC 40)", nombre(cac_dernier, 0), f"{variation(cac_var, 2)} aujourd'hui",
              explication="L'indice des 40 plus grandes entreprises françaises : il sert de point de comparaison.")
    st.write("")

    gauche, droite = st.columns([2.3, 1])
    with gauche, st.container(border=True):
        st.markdown("### Les 5 entreprises et nos conseils")
        tableau_actions(analyses, etat, conseils, raisons, pos)
    with droite, st.container(border=True):
        st.markdown("### Où est mon argent ?")
        graphique_repartition(prix, etat, pos)

    with st.container(border=True):
        st.markdown("### Mon portefeuille comparé au marché")
        graphique_historique(numero)
        st.caption("Les deux courbes partent de 100. Au-dessus de 100, la valeur a augmenté ; en dessous, "
                   "elle a baissé. Si votre courbe est au-dessus de celle du CAC 40, vous faites mieux que le marché.")


def resume_du_jour(etat: dict, gain: float, conseils: dict, reglages: dict) -> None:
    """Trois phrases simples : combien je vaux, que faire, suis-je protégé."""
    if gain > 0.5:
        evolution = f"<b class='hk-hausse'>{euros(gain, 0)} de plus</b> qu'au départ"
    elif gain < -0.5:
        evolution = f"<b class='hk-baisse'>{euros(-gain, 0)} de moins</b> qu'au départ"
    else:
        evolution = "autant qu'au départ"
    ligne1 = (f"Votre portefeuille vaut <b>{euros(etat['valeur'], 0)}</b>, soit {evolution} "
              f"({pourcent(etat['perte'], 2, signe=True)}).")

    a_acheter = [config.ACTIONS[c] for c, v in conseils.items() if v == "Acheter"]
    a_vendre = [config.ACTIONS[c] for c, v in conseils.items() if v == "Vendre"]
    if not a_acheter and not a_vendre:
        ligne2 = "Aucun achat ni aucune vente conseillés aujourd'hui : le plus sage est d'attendre."
    else:
        morceaux = []
        if a_acheter:
            morceaux.append(f"<b class='hk-hausse'>à acheter</b> : {', '.join(a_acheter)}")
        if a_vendre:
            morceaux.append(f"<b class='hk-baisse'>à vendre</b> : {', '.join(a_vendre)}")
        ligne2 = "Nos conseils du jour, " + " · ".join(morceaux) + ". Pour les autres, mieux vaut attendre."

    limite = -reglages["seuil_vente_auto"]
    if portefeuille.limite_atteinte(uid()):
        ligne3, couleur3, icone3 = ("Limite de perte atteinte : vos actions ont été vendues et les achats sont "
                                    "bloqués. Vous pouvez repartir de zéro dans Réglages."), ROUGE, "alerte"
    elif etat["perte"] <= reglages["seuil_alerte"]:
        ligne3, couleur3, icone3 = (f"Attention : votre perte approche de la limite de {pourcent(limite, 0)}. "
                                    "Au-delà, toutes vos actions seront vendues automatiquement."), style.ORANGE, "alerte"
    else:
        ligne3, couleur3, icone3 = (f"Protection active : si la perte atteint {pourcent(limite, 0)}, "
                                    "tout sera vendu automatiquement. Vous en êtes loin."), VERT, "bouclier"

    html(f"""<div class='hk-resume'><div class='hk-resume-titre'>En résumé</div>
      <div class='hk-resume-ligne'>{style.rond('portefeuille', MARINE)}<div>{ligne1}</div></div>
      <div class='hk-resume-ligne'>{style.rond('conseil', OR)}<div>{ligne2}</div></div>
      <div class='hk-resume-ligne'>{style.rond(icone3, couleur3)}<div>{ligne3}</div></div>
    </div>""")


def detail_conseils(analyses: dict, reglages: dict, pos: dict = None) -> None:
    """
    Pour chaque entreprise : le conseil, la phrase d'argumentation (A6) et les 4 notes.
    Affiché sur place (dépliant) pour ne pas obliger à quitter l'écran en cours de saisie.
    """
    pos = pos or {}
    for code, nom in config.ACTIONS.items():
        analyse = analyses.get(code)
        if analyse is None:
            st.caption(f"**{nom}** : prix indisponible, aucun conseil aujourd'hui.")
            continue
        conseil, phrase = moteur.conseiller(analyse, code in pos, reglages)
        notes = " · ".join(f"{textes.OUTILS[outil][0]} : {textes.verdict(note)}"
                           for outil, note in analyse.notes.items())
        html(f"<div class='hk-recap' style='display:block'>"
             f"<b>{nom}</b> {style.pastille_conseil(conseil)}"
             f"<div style='margin:.35rem 0 .2rem'>{style.echapper(phrase)}</div>"
             f"<small style='color:{GRIS}'>{style.echapper(notes)}</small></div>")


def raison_courte(analyse, conseil: str, reglages: dict) -> str:
    """
    La raison qui pèse le plus dans le conseil, en quelques mots, pour l'afficher juste à côté
    de la pastille : la personne ne doit pas avoir à changer d'écran pour savoir pourquoi.
    Le détail entre parenthèses est retiré (il reste visible dans « Les actions »).
    """
    choisies = moteur.raisons(conseil, analyse.arguments, reglages, nombre=1)
    if not choisies:
        return "aucun signal marqué aujourd'hui"
    return choisies[0].texte.split(" (")[0]


def tableau_actions(analyses: dict, etat: dict, conseils: dict, raisons: dict, pos: dict) -> None:
    largeurs = [2.6, 1.2, 1, 1.2, 0.9, 1.3, 0.9]
    entetes = [("Entreprise", ""), ("Prix", "Prix d'une action aujourd'hui"),
               ("Jour", "Évolution du prix depuis hier"), ("Conseil", "Notre conseil du jour"),
               ("J'en ai", "Nombre d'actions que vous possédez"), ("Valeur", "Ce que valent vos actions"), ("", "")]
    for colonne, (titre, bulle) in zip(st.columns(largeurs), entetes):
        html(f"<span class='hk-entete-tableau' title='{style.echapper(bulle)}'>{titre}</span>", colonne)
    for code, nom in config.ACTIONS.items():
        cols = st.columns(largeurs, vertical_alignment="center")
        html(f"<div class='hk-ligne'><b>{nom}</b><br><small>{textes.SECTEURS[code]}</small></div>", cols[0])
        analyse = analyses.get(code)
        if analyse is None:
            cols[1].caption("Prix indisponible")
            continue
        quantite = pos.get(code, {}).get("quantite", 0)
        valeur_ligne = quantite * analyse.cours
        html(f"<span class='hk-ligne'>{euros(analyse.cours)}</span>", cols[1])
        html(variation(analyse.variation_jour), cols[2])
        html(f"{style.pastille_conseil(conseils[code])}"
             f"<div class='hk-raison'>{style.echapper(raisons[code])}</div>", cols[3])
        html(f"<span class='hk-ligne'>{nombre(quantite, 0)}</span>", cols[4])
        part = f"<br><small>{pourcent(valeur_ligne / etat['valeur'], 0)} du total</small>" if quantite else ""
        html(f"<div class='hk-ligne'>{euros(valeur_ligne, 0)}{part}</div>", cols[5])
        cols[6].button("Pourquoi ?", key=f"voir_{code}", help=f"Voir toutes les raisons du conseil pour {nom}",
                       on_click=aller_a, args=("Les actions", code), width="stretch")


def graphique_repartition(prix: dict, etat: dict, pos: dict) -> None:
    noms = [config.ACTIONS[c] for c in pos] + ["Argent disponible"]
    valeurs = [p["quantite"] * prix.get(c, p["prix_revient"]) for c, p in pos.items()] + [etat["liquidites"]]
    couleurs = [MARINE, style.MARINE_CLAIR, OR, "#7C8DB5", "#2E86AB"][:len(pos)] + ["#D5DBE5"]
    fig = go.Figure(go.Pie(labels=noms, values=valeurs, hole=0.64, sort=False, marker=dict(colors=couleurs),
                           textinfo="none", hovertemplate="%{label}<br>%{value:,.0f} €<br>%{percent}<extra></extra>"))
    investi = etat["titres"] / etat["valeur"] if etat["valeur"] else 0
    fig.update_layout(height=290, margin=dict(l=0, r=0, t=0, b=0), showlegend=True,
                      legend=dict(orientation="h", y=-0.05, font=dict(size=11)),
                      annotations=[dict(text=f"<b>{pourcent(investi, 0)}</b><br>investi", showarrow=False,
                                        font=dict(size=15, color=MARINE))])
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def graphique_historique(numero: int) -> None:
    hist = portefeuille.lire_historique(numero)
    if len(hist) < 2:
        st.caption("La courbe apparaîtra au bout de quelques jours : un point est ajouté chaque jour où vous "
                   "ouvrez CAP 500.")
        return
    courbe = hist["valeur"] / hist["valeur"].iloc[0] * 100
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist["date"], y=courbe, name="Mon portefeuille", line=dict(width=3, color=MARINE),
                             fill="tozeroy", fillcolor="rgba(11,37,69,0.06)"))
    cac = hist.dropna(subset=["cac40"])
    minimum = courbe.min()
    if len(cac) >= 2:
        courbe_cac = cac["cac40"] / cac["cac40"].iloc[0] * 100
        minimum = min(minimum, courbe_cac.min())
        fig.add_trace(go.Scatter(x=cac["date"], y=courbe_cac, name="CAC 40", line=dict(dash="dot", color=OR, width=2)))
    fig.add_hline(y=100, line_color="#B8C0CC", line_width=1)
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.12),
                      yaxis_range=[minimum - 1, None])
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# =====================================================================
# Investir mon capital (répartition de départ, logigramme 3)
# =====================================================================
def ecran_repartition(prix: dict, analyses: dict) -> None:
    numero = uid()
    style.entete("Investir mes 500 000 €", "Étape 2 sur 3",
                 "Choisissez combien placer sur chaque entreprise. Vous n'êtes pas obligé de tout investir : "
                 "ce qui reste est gardé de côté.")
    if portefeuille.depart_fait(numero):
        st.info("Votre capital est déjà investi. Pour modifier votre portefeuille, utilisez « Acheter / vendre ».")
        return
    html(etapes_demarrage(2))

    r = base.lire_reglages(numero)
    taux = r["taux_frais"]
    plafond = r["max_par_action"] * config.CAPITAL
    reserve = r["reserve_min"] * config.CAPITAL
    with st.container(border=True):
        c1, c2 = st.columns([2.6, 1.4], vertical_alignment="center")
        html(f"<div style='display:flex;gap:.8rem;align-items:center'>{style.rond('conseil', OR)}<div>"
             f"<b>Vous ne savez pas comment répartir ?</b><br><span style='color:{GRIS};font-size:.92rem'>"
             f"CAP 500 ne propose que les entreprises dont le conseil du jour est « Acheter », "
             f"selon votre profil {r['profil']} ; le reste est gardé de côté. "
             f"Vous pourrez modifier la proposition avant de valider.</span></div></div>", c1)
        c2.button("Proposer une répartition", type="primary", icon=":material/auto_awesome:", width="stretch",
                  on_click=proposer_repartition, args=({c: a.score for c, a in analyses.items()},))

    montants, erreurs, depassements = {}, [], []
    with st.container(border=True):
        st.markdown("### Combien sur chaque entreprise ?")
        st.caption(f"Votre profil {r['profil']} : nous conseillons au plus {euros(plafond, 0)} sur une même "
                   f"entreprise, et au moins {euros(reserve, 0)} gardés de côté. "
                   f"Ce sont des repères : vous restez libre de placer davantage.")
        largeurs = [2.5, 1.1, 2, 1.1, 0.9]
        for colonne, titre in zip(st.columns(largeurs), ["Entreprise", "Prix d'une action", "Montant à investir (€)",
                                                         "Nombre d'actions", "Part"]):
            html(f"<span class='hk-entete-tableau'>{titre}</span>", colonne)
        for code, nom in config.ACTIONS.items():
            cols = st.columns(largeurs, vertical_alignment="center")
            analyse = analyses.get(code)
            # « Vendre » est impossible ici : on ne détient encore rien (règle RG9, moteur.recommander)
            conseil = moteur.recommander(analyse.score, False, r) if analyse else None
            raison = f"<div class='hk-raison'>{style.echapper(raison_courte(analyse, conseil, r))}</div>" \
                if analyse else ""
            html(f"<div class='hk-ligne'><b>{nom}</b> {style.pastille_conseil(conseil) if conseil else ''}"
                 f"<br><small>{textes.SECTEURS[code]}</small>{raison}</div>", cols[0])
            html(f"<span class='hk-ligne'>{euros(prix.get(code))}</span>", cols[1])
            montant = champ_nombre(f"Montant {nom}", f"montant_{code}", conteneur=cols[2], masquer_libelle=True,
                                   exemple="0")
            montants[code] = montant or 0.0
            if montants[code] > plafond + 0.01:
                depassements.append((code, nom, montants[code]))
            nb = portefeuille.quantite_possible(montants[code], prix.get(code), taux)
            html(f"<span class='hk-ligne'>{nombre(nb, 0)}</span>", cols[3])
            html(f"<span class='hk-ligne'>{pourcent(montants[code] / config.CAPITAL, 0)}</span>", cols[4])
        with st.expander("Pourquoi ces conseils ? Le détail des 5 entreprises"):
            detail_conseils(analyses, r)

    total = sum(montants.values())
    reste = config.CAPITAL - total
    c = st.columns(3)
    style.kpi(c[0], "Je vais investir", euros(total, 0), f"{pourcent(total / config.CAPITAL, 0)} de mes 500 000 €",
              accent=True)
    style.kpi(c[1], "Je garde de côté", euros(reste, 0), f"minimum demandé : {euros(reserve, 0)}",
              explication="Argent non investi, disponible plus tard pour acheter.")
    style.kpi(c[2], "Frais estimés", euros(total * taux, 0), f"{pourcent(taux, 2)} du montant acheté",
              explication="Ce que prend l'intermédiaire à chaque achat.")
    st.write("")

    if total > config.CAPITAL:
        erreurs.append(f"Le total dépasse vos 500 000 € de {euros(total - config.CAPITAL)}.")
    for erreur in erreurs:
        st.error(erreur)
    if not erreurs:
        avertir_concentration(depassements, reste, reserve, plafond, r["profil"])
    if erreurs or total <= 0:
        if total <= 0:
            st.caption("Saisissez au moins un montant, ou cliquez sur « Proposer une répartition ».")
        return

    if not st.session_state.get("repartition_en_attente"):
        st.button("Valider ma répartition", type="primary", icon=":material/check:",
                  on_click=lambda: st.session_state.update(repartition_en_attente=True))
    else:
        tout_sur_une = any(m >= TOUT_LE_CAPITAL * config.CAPITAL for m in montants.values())
        st.warning(f"Vous allez investir {euros(total)} au prix du jour"
                   f"{', dont tout votre capital sur une seule action' if tout_sur_une else ''}. On confirme ?")
        # On ne valide pas sans avoir vu, pour chaque entreprise achetée, le conseil et sa raison.
        recapitulatif_conseils(montants, analyses, r)
        c1, c2, _ = st.columns([1, 1, 2])
        c1.button("Oui, investir", type="primary", icon=":material/check:", on_click=confirmer_repartition,
                  width="stretch")
        c2.button("Modifier", icon=":material/edit:", width="stretch",
                  on_click=lambda: st.session_state.pop("repartition_en_attente", None))


def recapitulatif_conseils(montants: dict, analyses: dict, reglages: dict) -> None:
    """
    Récapitulatif affiché juste avant de valider : chaque entreprise où de l'argent est placé,
    avec le conseil du jour et la raison. Le but est qu'on ne puisse pas investir sans avoir lu
    pourquoi, et qu'un achat contraire au conseil soit signalé avant d'être validé.
    """
    lignes, contre_avis = [], []
    for code, montant in montants.items():
        analyse = analyses.get(code)
        if montant <= 0 or analyse is None:
            continue
        conseil = moteur.recommander(analyse.score, False, reglages)
        raison = raison_courte(analyse, conseil, reglages)
        lignes.append(f"<div class='hk-recap'><span>{config.ACTIONS[code]} · "
                      f"<small style='color:{GRIS}'>{style.echapper(raison)}</small></span>"
                      f"<b>{euros(montant, 0)} {style.pastille_conseil(conseil)}</b></div>")
        if conseil != "Acheter":
            contre_avis.append(config.ACTIONS[code])
    if lignes:
        html("".join(lignes))
    if contre_avis:
        st.info(f"Nous ne conseillons pas l'achat de {', '.join(contre_avis)} aujourd'hui : les signaux ne "
                "sont pas assez nets. Vous pouvez investir quand même, c'est votre décision.",
                icon=":material/info:")


TOUT_LE_CAPITAL = 0.99   # à partir de 99 % du capital sur une action, on parle de « tout le capital »


def avertir_concentration(depassements: list, reste: float, reserve: float, plafond: float, profil: str) -> None:
    """Messages (non bloquants) quand la répartition dépasse les repères du profil."""
    for code, nom, montant in depassements:
        if montant >= TOUT_LE_CAPITAL * config.CAPITAL:
            st.error(f"**Vous êtes en train d'investir tout votre capital dans {nom}.** "
                     f"Pour votre profil {profil}, nous vous conseillons au maximum {euros(plafond, 0)} "
                     f"({pourcent(plafond / config.CAPITAL, 0)} du capital) sur une même entreprise. "
                     f"Tout placer sur une seule action est **très risqué** : si son cours baisse, "
                     f"c'est tout votre portefeuille qui baisse. Vous pouvez continuer, mais en connaissance de cause.",
                     icon=":material/warning:")
        else:
            st.warning(f"{nom} : {euros(montant, 0)} ({pourcent(montant / config.CAPITAL, 0)} du capital). "
                       f"Pour votre profil {profil}, nous conseillons au maximum {euros(plafond, 0)}. "
                       f"Cette concentration augmente le risque.", icon=":material/warning:")
    if reste < reserve - 0.01 and not any(m >= TOUT_LE_CAPITAL * config.CAPITAL for _, _, m in depassements):
        st.warning(f"Votre profil {profil} conseille de garder au moins {euros(reserve, 0)} de côté "
                   f"(il vous reste {euros(reste, 0)}).", icon=":material/warning:")


def proposer_repartition(scores: dict) -> None:
    reglages = base.lire_reglages(uid())
    proposition = portefeuille.repartition_conseillee(scores, reglages)
    for code in config.ACTIONS:
        montant = proposition.get(code, 0)
        st.session_state[f"montant_{code}"] = texte_nombre(montant, 0) if montant else ""
    st.session_state.pop("repartition_en_attente", None)
    # La proposition ne retient que les entreprises conseillées à l'achat : certains jours,
    # aucune ne l'est. Il faut le dire, sinon la page semble simplement ne pas avoir répondu.
    retenues = [config.ACTIONS[c] for c, m in proposition.items() if m > 0]
    if not retenues:
        flash("info", f"Aujourd'hui, nous ne conseillons l'achat d'aucune des 5 entreprises : les signaux "
                      f"ne sont pas assez nets pour votre profil {reglages['profil']}. Vous pouvez attendre "
                      f"quelques jours, ou saisir vous-même des montants ci-dessous.")
    else:
        garde = config.CAPITAL - sum(proposition.values())
        flash("success", f"Proposition : {', '.join(retenues)}. {euros(garde, 0)} restent de côté, "
                         "parce que nous ne proposons que les entreprises conseillées à l'achat.")


def confirmer_repartition() -> None:
    st.session_state.pop("repartition_en_attente", None)
    montants = {code: lire_nombre(st.session_state.get(f"montant_{code}", "")) or 0.0 for code in config.ACTIONS}
    ok, message = portefeuille.repartir(uid(), montants, donnees.cours_actuels(),
                                        base.lire_reglages(uid())["taux_frais"])
    flash("success" if ok else "error", message)
    if ok:
        aller_a("Accueil")


def etapes_demarrage(actuelle: int) -> str:
    return style.etapes(actuelle, textes.ETAPES)


# =====================================================================
# Les actions (fiche d'une entreprise)
# =====================================================================
def ecran_fiche_action(analyses: dict) -> None:
    numero = uid()
    haut_gauche, haut_droite = st.columns([3, 1.2], vertical_alignment="bottom")
    code = choisir_action(haut_droite, "Changer d'entreprise")
    analyse = analyses.get(code)
    with haut_gauche:
        style.entete(config.ACTIONS[code], "Les actions", textes.SECTEURS[code])
    if analyse is None:
        st.error("Les prix de cette entreprise ne sont pas disponibles pour le moment.")
        return

    reglages = base.lire_reglages(numero)
    position = portefeuille.positions(numero).get(code)
    conseil, phrase = moteur.conseiller(analyse, position is not None, reglages)
    couleur = COULEURS_CONSEIL[conseil]

    html(f"<div class='hk-conseil' style='border-left-color:{couleur}'>"
         f"<div class='hk-conseil-titre' style='color:{GRIS}'>Notre conseil aujourd'hui</div>"
         f"<div class='hk-conseil-grand' style='color:{couleur}'>{style.LIBELLES_CONSEIL[conseil]}</div>"
         f"<div class='hk-conseil-texte'>{style.echapper(phrase)}</div>"
         f"<div class='hk-conseil-sens'>{textes.SENS_CONSEIL[conseil]}</div></div>")

    c = st.columns(4)
    style.kpi(c[0], "Prix d'une action", euros(analyse.cours), f"{variation(analyse.variation_jour, 2)} depuis hier",
              accent=True, explication=f"Dernier prix connu, le {date_fr(analyse.date_cours)}.")
    style.kpi(c[1], "Avis des experts",
              variation(analyse.potentiel) if analyse.potentiel is not None else "Pas d'avis",
              provenance_objectif(analyse),
              explication="Écart entre le prix visé par les experts des banques et le prix actuel.")
    style.kpi(c[2], "J'en possède",
              f"{nombre(position['quantite'], 0)} action{'s' if position['quantite'] > 1 else ''}" if position
              else "Aucune",
              f"valeur : {euros(position['quantite'] * analyse.cours, 0)}" if position else "&nbsp;")
    style.kpi(c[3], "Note globale", f"<span style='color:{style.couleur_note(analyse.score)}'>"
              f"{textes.verdict(analyse.score)}</span>",
              f"{nombre(analyse.score, 2)} sur une échelle de −2 à +2",
              explication=f"Moyenne des 4 points étudiés. Achat conseillé à partir de "
                          f"{nombre(reglages['seuil_achat'], 1)} pour votre profil {reglages['profil']}.")
    st.write("")

    st.markdown("### Les 4 points étudiés")
    for colonne, cle in zip(st.columns(4), ["graphique", "infos", "financier", "hasard"]):
        titre, technique, question_ = textes.OUTILS[cle]
        note = analyse.notes[cle]
        html(f"<div class='hk-note'><div class='hk-note-tech'>{technique}</div>"
             f"<div class='hk-note-nom'>{titre}</div>"
             f"<div class='hk-note-verdict' style='color:{style.couleur_note(note)}'>{textes.verdict(note)}</div>"
             f"{style.jauge(note)}<div class='hk-note-question'>{question_}</div></div>", colonne)
    st.write("")

    gauche, droite = st.columns([1.15, 1])
    with gauche, st.container(border=True):
        st.markdown("### Pourquoi ce conseil ?")
        if not analyse.arguments:
            st.caption("Aucun signal marqué pour le moment.")
        for a in sorted(analyse.arguments, key=lambda a: -abs(a.valeur)):
            sens = "haut" if a.valeur > 0 else "bas"
            teinte = VERT if a.valeur > 0 else ROUGE
            texte = a.texte[0].upper() + a.texte[1:]
            html(f"<div class='hk-argument'>{style.rond(sens, teinte)}<div>{style.echapper(texte)}"
                 f"<small>{textes.expliquer(a.texte)}</small></div></div>")
    with droite, st.container(border=True):
        st.markdown("### Actualités récentes")
        actualites = donnees.lire_actualites(code, 6)
        if not actualites:
            st.caption("Aucune actualité disponible pour le moment.")
        for a in actualites:
            source = f" · {style.echapper(a['source'])}" if a["source"] else ""
            html(f"<div class='hk-actu'>{style.point(COULEURS_TONALITE[a['tonalite']])}"
                 f"<a href='{style.echapper(a['lien'])}' target='_blank'>{style.echapper(a['titre'])}</a>"
                 f"<br><small>{date_fr(a['date'])}{source}</small></div>")
        st.caption("Point vert : nouvelle plutôt bonne · rouge : plutôt mauvaise · gris : neutre.")

    with st.container(border=True):
        # Le radio prend plus de large que l'ancien sélecteur : la colonne de droite est élargie
        # pour que les trois périodes tiennent sur une ligne.
        titre, choix = st.columns([2.5, 1.8], vertical_alignment="center")
        titre.markdown("### Évolution du prix")
        periode = choix.radio("Période", ["1 mois", "6 mois", "1 an"], index=1, horizontal=True,
                              key="periode_fiche", label_visibility="collapsed")
        jours = {"1 mois": 21, "6 mois": 126, "1 an": 252}[periode]
        ind = graphique.indicateurs(donnees.lire_cours(code)).tail(jours)
        simple, technique = st.tabs(["Prix", "Indicateurs techniques (pour les connaisseurs)"])
        with simple:
            graphique_prix_simple(ind)
            st.caption("La ligne bleue est le prix. Les lignes dorée et grise sont les moyennes des 20 et 50 "
                       "derniers jours : quand le prix passe au-dessus, la tendance est plutôt à la hausse.")
        with technique:
            graphique_technique(ind)

    st.button(f"Acheter ou vendre {config.ACTIONS[code]}", type="primary", icon=":material/swap_horiz:",
              on_click=aller_a, args=("Acheter / vendre", code))

    with st.expander("Pour aller plus loin : le détail des calculs"):
        afficher_detail(analyse, reglages)


def graphique_prix_simple(df: pd.DataFrame) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["cloture"], name="Prix", line=dict(width=2.8, color=MARINE),
                             fill="tozeroy", fillcolor="rgba(11,37,69,0.05)"))
    fig.add_trace(go.Scatter(x=df.index, y=df["MM20"], name="Moyenne 20 jours", line=dict(width=1.6, color=OR)))
    fig.add_trace(go.Scatter(x=df.index, y=df["MM50"], name="Moyenne 50 jours",
                             line=dict(width=1.6, color="#9AA3B2", dash="dash")))
    bas, haut = df["cloture"].min(), df["cloture"].max()
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified",
                      legend=dict(orientation="h", y=1.1), yaxis_range=[bas * 0.97, haut * 1.03],
                      yaxis_ticksuffix=" €")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def graphique_technique(df: pd.DataFrame) -> None:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.06,
                        subplot_titles=("", "RSI (14 jours)", "MACD"))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_haut"], line=dict(width=0), showlegend=False,
                             hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_bas"], line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(29,78,137,0.08)", name="Bandes de Bollinger"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["cloture"], name="Prix", line=dict(width=2.4, color=MARINE)),
                  row=1, col=1)
    dernier = df.iloc[-1]
    if pd.notna(dernier["support"]):
        fig.add_hline(y=dernier["support"], line_dash="dot", line_color=VERT, annotation_text="Support",
                      annotation_font_color=VERT, row=1, col=1)
        fig.add_hline(y=dernier["resistance"], line_dash="dot", line_color=ROUGE, annotation_text="Résistance",
                      annotation_font_color=ROUGE, row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color=style.MARINE_CLAIR)), row=2, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(201,162,39,0.07)", line_width=0, row=2, col=1)
    ecart_macd = df["MACD"] - df["MACD_signal"]
    fig.add_trace(go.Bar(x=df.index, y=ecart_macd, name="Écart MACD",
                         marker_color=[VERT if v >= 0 else ROUGE for v in ecart_macd.fillna(0)], opacity=0.55),
                  row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color=MARINE, width=1.6)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal", line=dict(color=OR, width=1.4)),
                  row=3, col=1)
    fig.update_layout(height=600, margin=dict(l=10, r=10, t=20, b=10), hovermode="x unified",
                      legend=dict(orientation="h", y=1.06))
    fig.update_annotations(font=dict(size=12, color=GRIS))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("RSI au-dessus de 70 : l'action a beaucoup monté ; sous 30 : elle a beaucoup baissé. "
               "MACD : barres vertes = élan à la hausse, rouges = élan à la baisse. Voir le Guide pour le détail.")


def provenance_objectif(analyse) -> str:
    """
    Sous l'avis des experts : le sens de l'écart, puis la source et la date de l'objectif.
    La contrainte C6 demande que chaque recommandation cite ses sources et sa date ; le chiffre
    seul ne suffisait pas. Source et date viennent de `data/analystes.csv`.
    """
    if analyse.potentiel is None:
        return "aucun objectif récent"
    sens = "de hausse attendue" if analyse.potentiel > 0 else "de baisse attendue"
    detail = analyse.analystes or {}
    provenance = []
    if detail.get("source"):
        source = str(detail["source"])
        # Une source peut lister plusieurs banques : on raccourcit pour la tuile, le détail
        # complet reste lisible dans le fichier data/analystes.csv et dans Réglages → Données.
        provenance.append(source if len(source) <= 38 else source[:37].rstrip(" ,(") + "…")
    if detail.get("date"):
        quand = str(detail["date"])
        provenance.append(date_fr(quand) if "-" in quand else quand)
    if not provenance:
        return f"{sens} · source non renseignée"
    return f"{sens} · objectif de {euros(detail['objectif'])} ({' · '.join(provenance)})"


def afficher_detail(analyse, reglages: dict) -> None:
    gauche, droite = st.columns(2)
    sim = analyse.simulation
    with gauche:
        if sim:
            st.markdown("**Simulation de la semaine prochaine (10 000 scénarios)**")
            html(recap([
                ("Chances que le prix monte", pourcent(sim["proba_hausse"], 0)),
                ("Perte possible dans les pires cas (5 %)", pourcent(sim["perte_95"], 1)),
                ("Limite acceptée par votre profil", pourcent(reglages["var_max"], 0)),
            ]))
            fig = go.Figure(go.Histogram(x=sim["rendements"] * 100, nbinsx=50, marker_color=style.MARINE_CLAIR,
                                         opacity=0.85))
            fig.add_vline(x=0, line_dash="dot", line_color=GRIS)
            fig.update_layout(height=220, xaxis_title="Gain ou perte en une semaine (%)", yaxis_title="Scénarios",
                              margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with droite:
        if analyse.ratios:
            st.markdown("**Santé financière (5 ratios)**")
            lignes = []
            for cle, libelle in financier.LIBELLES.items():
                v = analyse.ratios.get(cle)
                lignes.append((libelle, nombre(v, 1) if cle in ("per", "dette_ebitda") else pourcent(v)))
            html(recap(lignes))
            st.caption("Calculés à partir des comptes annuels (data/comptes.csv) et comparés aux 4 autres "
                       "entreprises.")
        st.markdown("**Poids de chaque point dans la note globale**")
        html(recap([(textes.OUTILS[o][0], pourcent(reglages[moteur.CLES_POIDS[o]], 0))
                    for o in ["graphique", "infos", "financier", "hasard"]]))


# =====================================================================
# Acheter / vendre (A7)
# =====================================================================
def ecran_achat_vente(analyses: dict) -> None:
    numero = uid()
    style.entete("Acheter ou vendre", "Passer un ordre",
                 "En 3 étapes. L'opération se fait au dernier prix connu, frais compris.")
    r = base.lire_reglages(numero)
    taux = r["taux_frais"]

    gauche, droite = st.columns([1.3, 1])
    with gauche, st.container(border=True):
        question(1, "Quelle entreprise ?")
        code = choisir_action(libelle="Entreprise")
        cours, date_cours = donnees.dernier_cours(code)
        if cours is None:
            st.error("Prix indisponible pour le moment.")
            return
        detenus = portefeuille.positions(numero).get(code, {}).get("quantite", 0)
        analyse = analyses.get(code)
        conseil, phrase = (None, "")
        if analyse:
            conseil, phrase = moteur.conseiller(analyse, detenus > 0, r)
            html(f"<div style='font-size:.9rem;color:{GRIS};margin:-.2rem 0 .4rem'>Notre conseil : "
                 f"{style.pastille_conseil(conseil)} &nbsp;· vous en avez {nombre(detenus, 0)}</div>"
                 f"<div class='hk-raison' style='margin:-.1rem 0 .5rem'>{style.echapper(phrase)}</div>")

        question(2, "Que voulez-vous faire ?")
        sens = st.radio("Opération", ["Acheter", "Vendre"], horizontal=True, key="sens_ordre",
                        label_visibility="collapsed")

        question(3, "Combien ?")
        mode = st.radio("Saisie", ["En euros", "En nombre d'actions"], horizontal=True, key="mode_saisie",
                        label_visibility="collapsed")
        maximum = quantite_maximale(numero, code, sens, cours, detenus, r)
        if mode == "En euros":
            montant = champ_nombre("Montant (€)", "montant_ordre", defaut=10_000, exemple="ex. 10 000",
                                   masquer_libelle=True)
            if sens == "Acheter":
                qte = portefeuille.quantite_possible(montant or 0, cours, taux)
            else:
                qte = int((montant or 0) // cours)
            st.caption(f"Soit **{nombre(qte, 0)} action{'s' if qte > 1 else ''}** à {euros(cours)}.")
        else:
            saisie = champ_nombre("Nombre d'actions", "quantite_ordre", defaut=1, entier=True, masquer_libelle=True)
            qte = int(saisie) if saisie is not None and float(saisie).is_integer() else saisie
        st.caption(f"Maximum possible : {nombre(maximum, 0)} action{'s' if maximum > 1 else ''}"
                   + (f" (selon votre argent disponible et votre profil {r['profil']})" if sens == "Acheter"
                      else " (celles que vous possédez)"))
        if sens == "Acheter" and portefeuille.limite_atteinte(numero):
            st.warning("Limite de perte atteinte : les achats sont bloqués.")

        attente = st.session_state.get("ordre_en_attente")
        if attente is None:
            st.button(f"{sens}", type="primary", width="stretch", icon=":material/arrow_forward:",
                      on_click=preparer_ordre, args=(code, "achat" if sens == "Acheter" else "vente", qte, cours))
        else:
            operation = "acheter" if attente["sens"] == "achat" else "vendre"
            st.warning(f"Vous allez **{operation} {nombre(attente['quantite'], 0)} action"
                       f"{'s' if attente['quantite'] > 1 else ''} {config.ACTIONS[attente['code']]}** "
                       f"à {euros(attente['prix'])}. On confirme ?")
            # La raison du conseil est rappelée au moment de décider, pas seulement en haut de l'écran.
            if conseil:
                st.caption(f"Notre conseil du jour : **{style.LIBELLES_CONSEIL[conseil]}**. {phrase}")
                attendu = {"achat": "Acheter", "vente": "Vendre"}[attente["sens"]]
                if conseil != attendu:
                    st.info("Cette opération ne suit pas notre conseil du jour. Vous pouvez la faire "
                            "quand même, c'est votre décision.", icon=":material/info:")
            c1, c2 = st.columns(2)
            c1.button("Oui, confirmer", type="primary", icon=":material/check:", on_click=confirmer_ordre,
                      width="stretch")
            c2.button("Annuler", icon=":material/close:", width="stretch",
                      on_click=lambda: st.session_state.pop("ordre_en_attente", None))

    with droite, st.container(border=True):
        st.markdown("### Récapitulatif")
        q = qte if isinstance(qte, int) and qte > 0 else 0
        brut = q * cours
        frais = portefeuille.calculer_frais(brut, taux)
        achat = sens == "Acheter"
        total = brut + frais if achat else brut - frais
        liq_apres = portefeuille.liquidites(numero) + (-total if achat else total)
        html(recap([
            ("Entreprise", config.ACTIONS[code]),
            ("Prix d'une action", f"{euros(cours)} <small style='color:{GRIS}'>({date_fr(date_cours)})</small>"),
            ("Nombre d'actions", nombre(q, 0)),
            ("Montant", euros(brut)),
            (f"Frais ({pourcent(taux, 2)}) {style.aide('Ce que prend l’intermédiaire à chaque opération.')}",
             euros(frais)),
            ("Argent disponible après", euros(liq_apres)),
        ], ("Vous payez" if achat else "Vous recevez", euros(total))))


def quantite_maximale(numero: int, code: str, sens: str, cours: float, detenus: int, r: dict) -> int:
    if sens == "Vendre":
        return detenus
    etat = portefeuille.valeur(numero, donnees.cours_actuels())
    selon_liquidites = (etat["liquidites"] - r["reserve_min"] * etat["valeur"]) / (cours * (1 + r["taux_frais"]))
    selon_plafond = r["max_par_action"] * etat["valeur"] / cours - detenus
    return max(int(min(selon_liquidites, selon_plafond)), 0)


def preparer_ordre(code: str, sens: str, quantite, prix: float) -> None:
    ok, message = portefeuille.verifier_ordre(uid(), code, sens, quantite, prix,
                                              base.lire_reglages(uid())["taux_frais"])
    if ok:
        st.session_state["ordre_en_attente"] = {"code": code, "sens": sens, "quantite": quantite, "prix": prix}
    else:
        flash("error", message)


def confirmer_ordre() -> None:
    attente = st.session_state.pop("ordre_en_attente", None)
    if attente:
        ok, message = portefeuille.passer_ordre(uid(), taux=base.lire_reglages(uid())["taux_frais"], **attente)
        flash("success" if ok else "error", message)
        if ok:
            calculer_analyses.clear()


# =====================================================================
# Mon profil
# =====================================================================
def regles_simples(valeurs: dict) -> list:
    reserve = valeurs["reserve_min"]
    return [
        f"Vente automatique si la perte atteint {pourcent(-valeurs['seuil_vente_auto'], 0)}",
        f"Au plus {pourcent(valeurs['max_par_action'], 0)} de l'argent sur une même entreprise",
        f"Au moins {pourcent(reserve, 0)} d'argent toujours gardé de côté" if reserve else
        "Tout l'argent peut être investi",
        "Achat conseillé seulement si les signaux sont " +
        ("très nets" if valeurs["seuil_achat"] >= 0.8 else "bons" if valeurs["seuil_achat"] >= 0.5 else
         "plutôt bons"),
    ]


def ecran_profil() -> None:
    numero = uid()
    r = base.lire_reglages(numero)
    debut = not portefeuille.depart_fait(numero)
    style.entete("Mon profil d'investisseur", "Étape 1 sur 3" if debut else "Profil",
                 "Votre profil adapte nos conseils, les limites d'achat et la protection contre les pertes.")
    if debut:
        html(etapes_demarrage(1))

    st.markdown("### Les 3 profils")
    for colonne, (nom, valeurs) in zip(st.columns(3), config.PROFILS.items()):
        actif = nom == r["profil"] and r.get("profil_defini")
        couleur = style.COULEURS_PROFIL[nom]
        lignes = "".join(f"<li>{icone('valide', 16, couleur, 2.5)}<span>{t}</span></li>" for t in regles_simples(valeurs))
        html(f"<div class='hk-profil{' actif' if actif else ''}'>"
             f"<div class='hk-profil-nom' style='color:{couleur}'>{nom}"
             f"{' &nbsp;' + style.pastille('Votre profil', couleur) if actif else ''}</div>"
             f"<div class='hk-profil-pour'>{textes.PROFILS_SIMPLES[nom]}</div><ul>{lignes}</ul></div>", colonne)
        colonne.button("Profil actuel" if actif else f"Choisir {nom}", key=f"choisir_{nom}", width="stretch",
                       disabled=bool(actif), type="secondary", on_click=_appliquer_profil, args=(nom,))
    st.caption("La perte ne dépasse jamais 10 %, quel que soit le profil.")
    st.write("")

    with st.container(border=True):
        st.markdown("### Vous hésitez ? Répondez à 4 questions")
        st.caption("Nous choisirons le profil qui vous correspond. Il n'y a pas de bonne ou de mauvaise réponse.")
        with st.form("questionnaire", border=False):
            for i, (texte_question, reponses) in enumerate(profil.QUESTIONS):
                st.radio(f"{i + 1}. {texte_question}", [t for t, _ in reponses], index=None, key=f"question_{i}")
            st.form_submit_button("Trouver mon profil", type="primary", on_click=appliquer_questionnaire)


def appliquer_questionnaire() -> None:
    reponses = [st.session_state.get(f"question_{i}") for i in range(len(profil.QUESTIONS))]
    if None in reponses:
        flash("error", "Répondez aux 4 questions pour trouver votre profil.")
        return
    points = [dict(choix)[rep] for (_, choix), rep in zip(profil.QUESTIONS, reponses)]
    _appliquer_profil(profil.calculer_profil(points))


def _appliquer_profil(nom: str) -> None:
    base.choisir_profil(uid(), nom)
    calculer_analyses.clear()
    flash("success", f"Profil {nom} choisi : {textes.PROFILS_SIMPLES[nom].lower()}")
    if not portefeuille.depart_fait(uid()):
        aller_a("Investir mon capital")


# =====================================================================
# Historique
# =====================================================================
def ecran_historique() -> None:
    numero = uid()
    style.entete("Historique", "Suivi", "Toutes vos opérations et l'évolution de votre portefeuille.")
    ordres = portefeuille.lire_ordres(numero)
    hist = portefeuille.lire_historique(numero)
    operations, evolution = st.tabs(["Mes opérations", "Évolution jour par jour"])
    with operations:
        if ordres.empty:
            st.info("Aucune opération pour le moment.")
        else:
            montant = ordres["quantite"] * ordres["prix"]
            total = montant.where(ordres["sens"] == "vente", montant + ordres["frais"])
            total = total.where(ordres["sens"] == "achat", montant - ordres["frais"])
            st.dataframe(pd.DataFrame({
                "Date": pd.to_datetime(ordres["date"]).dt.strftime("%d/%m/%Y %H:%M"),
                "Entreprise": ordres["code"].map(config.ACTIONS),
                "Opération": ordres["sens"].map({"achat": "Achat", "vente": "Vente"}),
                "Nombre d'actions": ordres["quantite"].map(lambda x: nombre(x, 0)),
                "Prix unitaire": ordres["prix"].map(euros),
                "Frais": ordres["frais"].map(euros),
                "Total": total.map(euros),
                "Décidé par": ordres["automatique"].map({0: "Vous", 1: "Vente automatique"}),
            }).iloc[::-1], hide_index=True, width="stretch")
        st.download_button("Télécharger en Excel", icon=":material/download:", data=export_excel(ordres, hist),
                           file_name=f"cap500_historique_{horloge.aujourdhui():%Y-%m-%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with evolution:
        graphique_historique(numero)
        if not hist.empty:
            st.dataframe(pd.DataFrame({
                "Date": hist["date"].dt.strftime("%d/%m/%Y"),
                "Valeur du portefeuille": hist["valeur"].map(euros),
                "Argent disponible": hist["liquidites"].map(euros),
                "CAC 40": hist["cac40"].map(nombre),
            }).iloc[::-1], hide_index=True, width="stretch")


def export_excel(ordres: pd.DataFrame, hist: pd.DataFrame) -> bytes:
    tampon = io.BytesIO()
    colonnes = ["date", "code", "sens", "quantite", "prix", "frais", "automatique"]
    with pd.ExcelWriter(tampon, engine="openpyxl") as fichier:
        ordres.reindex(columns=colonnes).to_excel(fichier, sheet_name="Opérations", index=False)
        hist.to_excel(fichier, sheet_name="Historique", index=False)
    return tampon.getvalue()


# =====================================================================
# Réglages
# =====================================================================
def ecran_reglages() -> None:
    style.entete("Réglages", "Compte et paramètres", "Votre compte, vos sauvegardes et les réglages avancés.")
    compte, sauvegarde, avances, donnees_ = st.tabs(["Mon compte", "Sauvegarde", "Réglages avancés", "Données"])
    with compte:
        section_compte()
    with sauvegarde:
        section_sauvegarde()
    with avances:
        formulaire_reglages()
    with donnees_:
        section_donnees()


def section_compte() -> None:
    numero = uid()
    gauche, droite = st.columns(2)
    with gauche, st.container(border=True):
        st.markdown("### Changer de mot de passe")
        st.caption(f"Identifiant : **{style.echapper(auth.identifiant(numero))}**")
        with st.form("mot_de_passe", border=False, clear_on_submit=True):
            actuel = st.text_input("Mot de passe actuel", type="password")
            mdp = st.text_input("Nouveau mot de passe", type="password")
            confirmation = st.text_input("Retapez le nouveau mot de passe", type="password")
            if st.form_submit_button("Modifier", type="primary"):
                ok, message = auth.changer_mot_de_passe(numero, actuel, mdp, confirmation,
                                                        st.session_state.get("jeton"))
                (st.success if ok else st.error)(message)

        st.markdown("### Nouveau code de récupération")
        st.caption("À faire si vous avez perdu votre code. Le nouveau code remplace l'ancien.")
        with st.form("nouveau_code", border=False, clear_on_submit=True):
            mdp_code = st.text_input("Mot de passe actuel", type="password", key="mdp_code")
            if st.form_submit_button("Créer un nouveau code"):
                if auth.verifier_mot_de_passe(numero, mdp_code):
                    html(f"<div class='hk-code'>{auth.nouveau_code_recuperation(numero)}</div>")
                    st.caption("Notez-le : il ne sera plus affiché.")
                else:
                    st.error("Mot de passe incorrect.")

    with droite, st.container(border=True):
        st.markdown("### Repartir de zéro")
        st.write("Votre portefeuille actuel est archivé et vous recommencez avec 500 000 €. "
                 "Votre compte et votre profil sont conservés.")
        st.text_input("Pour confirmer, tapez RECOMMENCER", key="confirmation_reinit")
        st.button("Repartir de zéro", icon=":material/restart_alt:", on_click=reinitialiser,
                  disabled=st.session_state.get("confirmation_reinit", "").strip().upper() != "RECOMMENCER")


def reinitialiser() -> None:
    base.reinitialiser_portefeuille(uid())
    calculer_analyses.clear()
    st.session_state["confirmation_reinit"] = ""
    flash("success", "C'est reparti : vous avez de nouveau 500 000 € à investir.")
    aller_a("Investir mon capital")


def section_sauvegarde() -> None:
    numero = uid()
    with st.container(border=True):
        st.markdown("### Télécharger mes données")
        st.write("Un fichier avec toutes vos opérations, votre historique et vos réglages. Utile si l'application "
                 "est en ligne : vous pourrez tout récupérer si les données sont effacées.")
        st.download_button("Télécharger ma sauvegarde", icon=":material/download:", data=base.exporter_compte(numero),
                           file_name=f"cap500_{auth.identifiant(numero)}_{horloge.aujourdhui():%Y-%m-%d}.json",
                           mime="application/json")
    with st.container(border=True):
        st.markdown("### Restaurer une sauvegarde")
        st.write("Remplace votre portefeuille actuel par celui du fichier (l'actuel est archivé, pas supprimé).")
        fichier = st.file_uploader("Fichier de sauvegarde (.json)", type=["json"], key="fichier_restauration")
        if fichier is not None and st.button("Restaurer", icon=":material/upload:"):
            ok, message = base.importer_compte(numero, fichier.getvalue())
            if ok:
                calculer_analyses.clear()
            flash("success" if ok else "error", message)
            st.rerun()


def formulaire_reglages() -> None:
    r = base.lire_reglages(uid())
    html(f"<div class='hk-resume' style='display:flex;gap:.7rem'>{style.rond('info', OR)}<div>"
         "<b>Réservé aux connaisseurs.</b> Ces réglages changent la façon dont les conseils sont calculés. "
         "Choisir un profil (page Mon profil) remet les seuils du profil.</div></div>")
    with st.form("reglages"):
        st.markdown("**Importance de chaque point dans la note globale** (le total doit faire 100 %)")
        c = st.columns(4)
        saisies = {
            "poids_graphique": c[0].text_input("Tendance du prix (%)", texte_nombre(r["poids_graphique"] * 100)),
            "poids_infos": c[1].text_input("Experts et actualités (%)", texte_nombre(r["poids_infos"] * 100)),
            "poids_financier": c[2].text_input("Santé de l'entreprise (%)", texte_nombre(r["poids_financier"] * 100)),
            "poids_hasard": c[3].text_input("Risque simulé (%)", texte_nombre(r["poids_hasard"] * 100)),
        }
        st.markdown("**Seuils des conseils et frais**")
        c = st.columns(3)
        saisies["seuil_achat"] = c[0].text_input("Acheter si la note atteint", texte_nombre(r["seuil_achat"]))
        saisies["seuil_vente"] = c[1].text_input("Vendre si la note descend à", texte_nombre(r["seuil_vente"]))
        saisies["taux_frais"] = c[2].text_input("Frais par opération (%)", texte_nombre(r["taux_frais"] * 100, 3))
        if st.form_submit_button("Enregistrer", type="primary"):
            valeurs = {cle: lire_nombre(texte) for cle, texte in saisies.items()}
            poids = ["poids_graphique", "poids_infos", "poids_financier", "poids_hasard"]
            if None in valeurs.values():
                st.error("Un des champs ne contient pas un nombre (exemple : 12,5).")
            elif abs(sum(valeurs[p] for p in poids) - 100) > 0.01:
                st.error(f"Le total doit faire 100 % (actuellement {nombre(sum(valeurs[p] for p in poids), 1)} %).")
            elif not -2 <= valeurs["seuil_vente"] < valeurs["seuil_achat"] <= 2:
                st.error("Les seuils vont de −2 à 2, et celui de vente doit être plus bas que celui d'achat.")
            elif not 0 <= valeurs["taux_frais"] <= 5:
                st.error("Les frais doivent être entre 0 et 5 %.")
            else:
                for p in poids:
                    base.ecrire_reglage(uid(), p, valeurs[p] / 100)
                base.ecrire_reglage(uid(), "seuil_achat", valeurs["seuil_achat"])
                base.ecrire_reglage(uid(), "seuil_vente", valeurs["seuil_vente"])
                base.ecrire_reglage(uid(), "taux_frais", valeurs["taux_frais"] / 100)
                calculer_analyses.clear()
                st.success("Réglages enregistrés.")


def etat_comptes(comptes: pd.DataFrame) -> None:
    """
    Prévient quand les comptes annuels sont en retard ou incomplets : l'analyse financière (A3)
    compare alors un cours d'aujourd'hui à des comptes plus anciens, ce qui fausse le PER.
    """
    annee = financier.dernier_exercice(comptes)
    if annee is None:
        st.warning("Aucun compte annuel : l'analyse de la santé des entreprises ne compte pas "
                   "dans les conseils. Remplissez `data/comptes.csv`.")
        return
    attendue = horloge.aujourdhui().year - 1       # les comptes de l'année N sont publiés début N+1
    if annee < attendue:
        st.warning(f"Le dernier exercice renseigné est {annee}, alors que les comptes {attendue} "
                   f"devraient être disponibles. Le PER compare un prix d'aujourd'hui à un bénéfice "
                   f"de {annee} : à mettre à jour depuis les rapports annuels.")
    else:
        st.caption(f"Dernier exercice renseigné : {annee}.")
    incomplets = financier.exercices_incomplets(comptes)
    if incomplets:
        detail = " · ".join(f"**{config.ACTIONS[c]}** : {', '.join(v)}" for c, v in incomplets.items())
        st.info(f"Données manquantes sur le dernier exercice ({detail}). En attendant, les calculs "
                "utilisent la dernière valeur connue de chaque donnée.")


def section_donnees() -> None:
    st.markdown("**Importer des prix** (si la mise à jour automatique ne fonctionne pas)")
    if not base.est_administrateur(uid()):
        # Les cours sont communs à tous les comptes : un import changerait la valeur des
        # portefeuilles et les conseils de tout le monde.
        st.info("Les prix sont communs à tous les comptes : seul le compte principal peut les importer. "
                "Vous pouvez demander à la personne qui gère l'application de le faire.")
    else:
        st.caption("Fichier CSV avec au moins une colonne « date » et une colonne « clôture » "
                   "(export ABC Bourse par exemple).")
        st.caption(":orange[Attention : les prix importés servent à tous les comptes de l'application.]")
        code = st.selectbox("Entreprise concernée", list(config.ACTIONS) + [config.INDICE],
                            format_func=lambda c: config.ACTIONS.get(c, "CAC 40"), key="code_import")
        fichier = st.file_uploader("Fichier CSV", type=["csv", "txt"])
        if fichier is not None and st.button("Importer"):
            try:
                nb = donnees.importer_csv_cours(fichier, code)
                calculer_analyses.clear()
                st.success(f"{nb} prix importés.")
            except ValueError as erreur:
                st.error(str(erreur))
    st.divider()
    st.markdown("**Comptes annuels des entreprises** – fichier `data/comptes.csv`")
    comptes = donnees.charger_comptes()
    etat_comptes(comptes)
    if not comptes.empty:
        st.dataframe(comptes, hide_index=True, width="stretch")
    st.markdown("**Objectifs des experts** – fichier `data/analystes.csv` (à mettre à jour chaque semaine)")
    analystes = donnees.charger_analystes()
    if not analystes.empty:
        st.dataframe(analystes, hide_index=True, width="stretch")
    st.caption("Après une modification de ces fichiers, cliquez sur « Actualiser les prix » dans le menu.")


# =====================================================================
# Guide
# =====================================================================
def ecran_guide() -> None:
    style.entete("Guide", "Comprendre CAP 500", "Tout ce qu'il faut savoir, sans jargon.")

    st.markdown("### Comment ça marche ?")
    for colonne, (i, (titre, texte)) in zip(st.columns(3), enumerate(textes.ETAPES, start=1)):
        html(f"<div class='hk-note'><span class='hk-etape-num'>{i}</span><div class='hk-note-nom' "
             f"style='margin-top:.5rem'>{titre}</div><div class='hk-note-question' style='font-size:.9rem'>"
             f"{texte}</div></div>", colonne)
    st.write("")

    st.markdown("### Comment sont décidés les conseils ?")
    st.write("Pour chaque entreprise, CAP 500 étudie 4 points. Chacun reçoit une note de −2 (très défavorable) "
             "à +2 (très favorable). La note globale est une moyenne où chaque point compte plus ou moins :")
    poids = {"graphique": 40, "infos": 25, "financier": 20, "hasard": 15}
    for colonne, (cle, (titre, technique, question_)) in zip(st.columns(4), textes.OUTILS.items()):
        html(f"<div class='hk-note'><div class='hk-note-tech'>{technique}</div><div class='hk-note-nom'>{titre}</div>"
             f"<div class='hk-note-verdict' style='color:{OR}'>{poids[cle]} %</div>"
             f"<div class='hk-note-question'>{question_}</div></div>", colonne)
    st.write("")
    html(recap([
        ("Note globale assez haute", f"{style.pastille_conseil('Acheter')}"),
        ("Note globale assez basse (et vous possédez l'action)", f"{style.pastille_conseil('Vendre')}"),
        ("Entre les deux", f"{style.pastille_conseil('Ne rien faire')}"),
    ]))
    st.caption("Les seuils exacts dépendent de votre profil (page Mon profil).")
    st.write("")

    gauche, droite = st.columns([1, 1.1])
    with gauche:
        st.markdown("### Questions fréquentes")
        for q, r in textes.FAQ:
            with st.expander(q):
                st.write(r)
    with droite:
        st.markdown("### Petit lexique")
        recherche = st.text_input("Chercher un mot", placeholder="ex. dividende, RSI, PER…",
                                  label_visibility="collapsed")
        mots = [(m, d) for m, d in textes.LEXIQUE
                if recherche.strip().lower() in (m + " " + d).lower()]
        if not mots:
            st.caption("Aucun mot trouvé.")
        for mot, definition in mots:
            html(f"<div class='hk-lexique'><b>{mot}</b><div>{definition}</div></div>")
