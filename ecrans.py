"""
Les écrans de l'interface Streamlit (voir le dossier de spécification, section 3).
"""
import io
import json
import time
from datetime import date, datetime

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
import moteur
import portefeuille
import profil
import style
from affichage import date_fr, date_longue, euros, lire_nombre, nombre, pourcent, texte_nombre
from style import COULEURS_CONSEIL, GRIS, MARINE, OR, ROUGE, VERT

PAGES = ["Tableau de bord", "Répartition de départ", "Fiche action", "Achat / vente", "Mon profil",
         "Historique et réglages"]
ICONES = {
    "Tableau de bord": ":material/space_dashboard:",
    "Répartition de départ": ":material/donut_large:",
    "Fiche action": ":material/query_stats:",
    "Achat / vente": ":material/swap_horiz:",
    "Mon profil": ":material/shield_person:",
    "Historique et réglages": ":material/tune:",
}
COULEURS_TONALITE = {1: VERT, 0: "#B8C0CC", -1: ROUGE}
AIDE = {
    "graphique": "Moyennes mobiles, RSI, MACD et bandes de Bollinger. +2 = signaux d'achat, −2 = signaux de vente.",
    "infos": "Écart entre l'objectif des analystes et le cours, et actualités positives ou négatives de la semaine.",
    "financier": "5 ratios (croissance du CA, marge nette, PER, endettement, rendement) comparés aux 4 autres.",
    "hasard": "10 000 scénarios simulés sur une semaine : probabilité de hausse et risque de perte.",
}
LIBELLES_REGLES = {
    "seuil_achat": "Achat si score ≥",
    "seuil_vente": "Vente si score ≤",
    "max_par_action": "Part max. par action",
    "reserve_min": "Liquidités min.",
    "var_max": "Risque / semaine",
    "seuil_alerte": "Alerte",
    "seuil_vente_auto": "Vente automatique",
}


# =====================================================================
# Outils communs
# =====================================================================
def html(texte: str, conteneur=None) -> None:
    (conteneur or st).markdown(texte, unsafe_allow_html=True)


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


def deconnecter(message: str = None) -> None:
    for cle in list(st.session_state.keys()):
        del st.session_state[cle]
    if message:
        st.session_state["message_connexion"] = message


def choisir_action(conteneur=None, libelle: str = "Action") -> str:
    codes = list(config.ACTIONS)
    if st.session_state.get("action_choisie") not in codes:
        st.session_state["action_choisie"] = codes[0]
    return (conteneur or st).selectbox(libelle, codes, format_func=config.ACTIONS.get, key="action_choisie")


def champ_nombre(libelle: str, cle: str, defaut=None, conteneur=None, entier: bool = False,
                 aide: str = None, masquer_libelle: bool = False):
    """Champ de saisie qui accepte la virgule et les espaces (« 12 500,50 »). Renvoie le nombre ou None."""
    conteneur = conteneur or st
    if cle not in st.session_state:
        st.session_state[cle] = "" if defaut is None else texte_nombre(defaut, 0 if entier else 2)
    texte = conteneur.text_input(libelle, key=cle, help=aide, placeholder="ex. 150" if entier else "ex. 25 000,50",
                                 label_visibility="collapsed" if masquer_libelle else "visible")
    valeur = lire_nombre(texte)
    if texte.strip() and valeur is None:
        conteneur.caption(":red[Nombre non reconnu]")
    return valeur


def variation(x, decimales: int = 1) -> str:
    return f"<span class='{style.classe_variation(x)}'>{pourcent(x, decimales, signe=True)}</span>"


# =====================================================================
# Données et calculs (logigramme 4), gardés en mémoire 1 heure
# =====================================================================
@st.cache_data(ttl=3600, show_spinner="Mise à jour des cours et des actualités…")
def actualiser_donnees(jour: str) -> dict:
    cours = donnees.mettre_a_jour_cours()
    actus = {code: donnees.telecharger_actualites(code) for code in config.ACTIONS}
    return {"cours": cours, "actus": actus, "heure": datetime.now().strftime("%d/%m/%Y à %H:%M")}


@st.cache_data(ttl=3600, show_spinner="Calcul des recommandations…")
def calculer_analyses(reglages_json: str, jeton: str) -> dict:
    reglages = json.loads(reglages_json)
    cours = {code: donnees.lire_cours(code) for code in config.ACTIONS}
    ratios = financier.calculer_ratios(donnees.charger_comptes(), cours)
    analystes = donnees.charger_analystes()
    graine = int(date.today().strftime("%Y%m%d"))   # même simulation toute la journée
    analyses = {}
    for i, (code, df) in enumerate(cours.items()):
        if len(df) >= 2:
            analyses[code] = moteur.analyser(code, df, ratios, analystes, donnees.actualites_semaine(code),
                                             reglages, graine + i)
    return analyses


def analyses_courantes(statut: dict) -> dict:
    reglages = base.lire_reglages()
    cles = {k: reglages[k] for k in [*config.REGLAGES_DEFAUT, "var_max"]}
    return calculer_analyses(json.dumps(cles, sort_keys=True), statut["heure"])


def tout_recalculer() -> None:
    actualiser_donnees.clear()
    calculer_analyses.clear()


def afficher_etat_donnees(statut: dict) -> None:
    """Message orange si les cours n'ont pas pu être mis à jour (logigramme 4)."""
    echecs = [code for code in config.ACTIONS if not statut["cours"].get(code)]
    if not echecs:
        return
    sans_donnees = [config.ACTIONS[c] for c in echecs if donnees.dernier_cours(c)[0] is None]
    if sans_donnees:
        st.error("Aucun cours disponible pour : " + ", ".join(sans_donnees)
                 + ". Vérifiez votre connexion internet ou importez un fichier CSV (Historique et réglages).")
    anciens = [c for c in echecs if donnees.dernier_cours(c)[0] is not None]
    if anciens:
        derniere = max(donnees.dernier_cours(c)[1] for c in anciens)
        st.warning(f"Cours du {date_fr(derniere)} : mise à jour impossible pour le moment.")


# =====================================================================
# Écran 0 – Connexion
# =====================================================================
def ecran_connexion() -> None:
    _, centre, _ = st.columns([1, 1.3, 1])
    with centre:
        html(f"<div style='text-align:center;margin:2.5rem 0 1.5rem'>{style.logo_html(largeur=270)}</div>")
        if "message_connexion" in st.session_state:
            st.info(st.session_state.pop("message_connexion"))

        if "code_a_noter" in st.session_state:
            afficher_code_recuperation()
        elif not auth.compte_existe():
            formulaire_creation()
        else:
            with st.container(border=True):
                onglet_connexion, onglet_oubli = st.tabs(["Se connecter", "Mot de passe oublié · nouveau compte"])
                with onglet_connexion:
                    formulaire_connexion()
                with onglet_oubli:
                    formulaire_recreation()
        html("<div class='hk-pied'>Gestion de portefeuille · Hermès, Air Liquide, TotalEnergies, "
             "Dassault Systèmes, Capgemini</div>")


def formulaire_creation() -> None:
    with st.container(border=True):
        st.markdown("### Créer votre compte")
        st.caption(f"Première utilisation : choisissez un identifiant et un mot de passe "
                   f"({config.LONGUEUR_MIN_MDP} caractères minimum).")
        with st.form("creation_compte", border=False):
            identifiant = st.text_input("Identifiant")
            mdp = st.text_input("Mot de passe", type="password")
            confirmation = st.text_input("Confirmer le mot de passe", type="password")
            if st.form_submit_button("Créer le compte", type="primary", width="stretch"):
                ok, message = auth.creer_compte(identifiant, mdp, confirmation)
                if ok:
                    st.session_state["code_a_noter"] = auth.nouveau_code_recuperation()
                    st.session_state["message_connexion"] = message
                    st.rerun()
                st.error(message)


def afficher_code_recuperation() -> None:
    with st.container(border=True):
        st.markdown("### Votre code de récupération")
        st.write("Notez-le et gardez-le en lieu sûr. Il vous permettra de recréer votre compte si vous oubliez "
                 "votre mot de passe. **Il ne sera plus affiché.**")
        html(f"<div class='hk-code'>{st.session_state['code_a_noter']}</div>")
        st.write("")
        st.button("J'ai noté mon code", type="primary", width="stretch",
                  on_click=lambda: st.session_state.pop("code_a_noter", None))


def formulaire_connexion() -> None:
    with st.form("connexion", border=False):
        identifiant = st.text_input("Identifiant")
        mdp = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Se connecter", type="primary", width="stretch"):
            ok, message = auth.verifier(identifiant, mdp)
            if ok:
                base.sauvegarder()
                if not base.lire_reglages().get("profil_defini"):
                    page = "Mon profil"
                elif not portefeuille.depart_fait():
                    page = "Répartition de départ"
                else:
                    page = "Tableau de bord"
                st.session_state.update(connecte=True, identifiant=identifiant.strip(),
                                        derniere_activite=time.time(), page=page)
                st.rerun()
            st.error(message)


def formulaire_recreation() -> None:
    st.caption("Saisissez le code de récupération reçu à la création du compte, puis vos nouveaux identifiants. "
               "Une copie de sécurité des données est faite avant.")
    with st.form("recreation", border=False):
        code = st.text_input("Code de récupération", placeholder="XXXX-XXXX-XXXX")
        identifiant = st.text_input("Nouvel identifiant")
        mdp = st.text_input("Nouveau mot de passe", type="password")
        confirmation = st.text_input("Confirmer le mot de passe", type="password")
        choix = st.radio("Votre portefeuille", ["Le garder", "Repartir de 500 000 €"], horizontal=True)
        if st.form_submit_button("Recréer le compte", type="primary", width="stretch"):
            ok, message = auth.recreer_compte(code, identifiant, mdp, confirmation, choix == "Le garder")
            if ok:
                tout_recalculer()
                st.session_state["code_a_noter"] = auth.nouveau_code_recuperation()
                st.session_state["message_connexion"] = message
                st.rerun()
            st.error(message)


# =====================================================================
# Menu latéral
# =====================================================================
def barre_laterale(statut: dict) -> None:
    sb = st.sidebar
    reglages = base.lire_reglages()
    html(f"<div style='margin:.3rem 0 1.6rem'>{style.logo_html(clair=True, largeur=190)}</div>", sb)
    html(f"<div style='margin-bottom:1.1rem;font-size:.88rem'>"
         f"<div style='color:#9FB0C8;font-size:.75rem'>Connecté</div>"
         f"<div style='color:#FFFFFF;font-weight:600;margin-bottom:.4rem'>"
         f"{style.echapper(st.session_state.get('identifiant', ''))}</div>"
         f"{style.pastille_profil(reglages['profil'])}</div>", sb)
    sb.radio("Menu", PAGES, key="page", format_func=lambda p: f"{ICONES[p]} {p}", label_visibility="collapsed")
    sb.divider()
    sb.caption(f"Données du {statut['heure']}")
    if sb.button("Actualiser les données", icon=":material/refresh:", width="stretch"):
        tout_recalculer()
        st.rerun()
    if sb.button("Se déconnecter", icon=":material/logout:", width="stretch"):
        base.sauvegarder()
        deconnecter("Vous êtes déconnecté.")
        st.rerun()


# =====================================================================
# Écran 1 – Tableau de bord
# =====================================================================
def ecran_tableau_de_bord(analyses: dict, prix: dict) -> None:
    reglages = base.lire_reglages()
    etat = portefeuille.valeur(prix)
    gain = etat["valeur"] - config.CAPITAL
    cac = donnees.lire_cours(config.INDICE)
    cac_dernier = float(cac["cloture"].iloc[-1]) if not cac.empty else None
    cac_var = float(cac["cloture"].iloc[-1] / cac["cloture"].iloc[-2] - 1) if len(cac) > 1 else None
    portefeuille.enregistrer_historique(etat["valeur"], etat["liquidites"], cac_dernier)

    style.entete("Tableau de bord", f"Bonjour {st.session_state.get('identifiant', '')} · {date_longue(date.today())}",
                 "Vue d'ensemble de votre portefeuille et de nos conseils du jour.")

    c = st.columns(4)
    style.kpi(c[0], "Valeur du portefeuille", euros(etat["valeur"], 0),
              f"{pourcent(etat['perte'], 2, signe=True)} depuis le départ", accent=True)
    style.kpi(c[1], "Gain / perte", f"<span class='{style.classe_variation(gain)}'>{euros(gain, 0)}</span>",
              f"sur {euros(config.CAPITAL, 0)} de capital")
    part_liq = etat["liquidites"] / etat["valeur"] if etat["valeur"] else 0
    style.kpi(c[2], "Liquidités", euros(etat["liquidites"], 0),
              f"{pourcent(part_liq, 0)} du total · min. {pourcent(reglages['reserve_min'], 0)}")
    style.kpi(c[3], config.NOM_INDICE, nombre(cac_dernier, 0), f"{variation(cac_var, 2)} aujourd'hui")
    st.write("")
    jauge_protection(etat["perte"], reglages)

    if not portefeuille.depart_fait():
        with st.container(border=True):
            st.markdown("**Votre capital n'est pas encore investi.** Répartissez vos 500 000 € entre les 5 actions.")
            st.button("Répartir mon capital", type="primary", on_click=aller_a, args=("Répartition de départ",))

    gauche, droite = st.columns([2.3, 1])
    with gauche, st.container(border=True):
        st.markdown("### Vos actions")
        tableau_actions(analyses, etat, reglages)
    with droite, st.container(border=True):
        st.markdown("### Répartition")
        graphique_repartition(prix, etat)

    with st.container(border=True):
        st.markdown(f"### Évolution face au {config.NOM_INDICE}")
        graphique_historique()


def jauge_protection(perte: float, reglages: dict) -> None:
    """Barre qui montre où en est la perte par rapport à la vente automatique (A8)."""
    limite = -reglages["seuil_vente_auto"]
    alerte = -reglages["seuil_alerte"]
    remplissage = min(max(-perte, 0) / limite, 1) * 100
    couleur = ROUGE if -perte >= alerte else OR if perte < 0 else VERT
    texte = "aucune perte" if perte >= 0 else f"perte de {pourcent(-perte, 1)}"
    html(f"""<div class='hk-kpi' style='padding:.8rem 1.1rem;margin-bottom:1rem'>
      <div style='display:flex;justify-content:space-between;font-size:.85rem'>
        <span style='font-weight:700;color:{MARINE}'>Protection contre les pertes</span>
        <span style='color:{GRIS}'>Aujourd'hui : <b style='color:{couleur}'>{texte}</b> · alerte à
        −{pourcent(alerte, 0)} · vente automatique à −{pourcent(limite, 0)}</span></div>
      <div class='hk-jauge' style='height:8px;margin-top:.6rem'>
        <div class='hk-jauge-barre' style='left:0;height:8px;width:{remplissage:.1f}%;background:{couleur}'></div>
        <div style='position:absolute;left:{alerte / limite * 100:.1f}%;top:-3px;width:2px;height:14px;
        background:{OR}'></div></div></div>""")


def tableau_actions(analyses: dict, etat: dict, reglages: dict) -> None:
    pos = portefeuille.positions()
    largeurs = [2.2, 1.2, 0.9, 1.4, 0.8, 1.4, 0.7]
    entetes = st.columns(largeurs)
    for colonne, titre in zip(entetes, ["Action", "Cours", "Jour", "Conseil", "Titres", "Valeur", ""]):
        html(f"<span class='hk-entete-tableau'>{titre}</span>", colonne)
    for code, nom in config.ACTIONS.items():
        cols = st.columns(largeurs, vertical_alignment="center")
        html(f"<div class='hk-ligne'><b>{nom}</b><br><small>{code.replace('.PA', '')} · Euronext Paris</small></div>",
             cols[0])
        analyse = analyses.get(code)
        if analyse is None:
            cols[1].caption("Cours indisponible")
            continue
        quantite = pos.get(code, {}).get("quantite", 0)
        conseil, _ = moteur.conseiller(analyse, quantite > 0, reglages)
        valeur_ligne = quantite * analyse.cours
        html(f"<span class='hk-ligne'>{euros(analyse.cours)}</span>", cols[1])
        html(variation(analyse.variation_jour), cols[2])
        html(style.pastille_conseil(conseil), cols[3])
        html(f"<span class='hk-ligne'>{nombre(quantite, 0)}</span>", cols[4])
        part = f"<br><small>{pourcent(valeur_ligne / etat['valeur'], 0)}</small>" if quantite else ""
        html(f"<div class='hk-ligne'>{euros(valeur_ligne, 0)}{part}</div>", cols[5])
        cols[6].button("", icon=":material/chevron_right:", key=f"voir_{code}", help=f"Voir {nom}",
                       on_click=aller_a, args=("Fiche action", code))


def graphique_repartition(prix: dict, etat: dict) -> None:
    pos = portefeuille.positions()
    noms = [config.ACTIONS[c] for c in pos] + ["Liquidités"]
    valeurs = [p["quantite"] * prix.get(c, p["prix_revient"]) for c, p in pos.items()] + [etat["liquidites"]]
    couleurs = [MARINE, style.MARINE_CLAIR, OR, "#7C8DB5", "#2E86AB"][:len(pos)] + ["#D5DBE5"]
    fig = go.Figure(go.Pie(labels=noms, values=valeurs, hole=0.62, sort=False, marker=dict(colors=couleurs),
                           textinfo="none", hovertemplate="%{label}<br>%{value:,.0f} €<br>%{percent}<extra></extra>"))
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), showlegend=True,
                      legend=dict(orientation="h", y=-0.05, font=dict(size=11)),
                      annotations=[dict(text=f"<b>{len(pos)}</b><br>action{'s' if len(pos) > 1 else ''}",
                                        showarrow=False, font=dict(size=15, color=MARINE))],
                      separators=", ")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def graphique_historique() -> None:
    hist = portefeuille.lire_historique()
    if len(hist) < 2:
        st.caption("La courbe apparaîtra après quelques jours d'utilisation (un point par jour).")
        return
    courbe = hist["valeur"] / hist["valeur"].iloc[0] * 100
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist["date"], y=courbe,
                             name="Mon portefeuille", line=dict(width=3, color=MARINE),
                             fill="tozeroy", fillcolor="rgba(11,37,69,0.06)"))
    cac = hist.dropna(subset=["cac40"])
    minimum = courbe.min()
    if len(cac) >= 2:
        courbe_cac = cac["cac40"] / cac["cac40"].iloc[0] * 100
        minimum = min(minimum, courbe_cac.min())
        fig.add_trace(go.Scatter(x=cac["date"], y=courbe_cac,
                                 name=config.NOM_INDICE, line=dict(dash="dot", color=OR, width=2)))
    fig.update_layout(height=300, yaxis_title="Base 100", margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.12), yaxis_range=[minimum - 1, None], separators=", ")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# =====================================================================
# Écran 2 – Répartition de départ (logigramme 3)
# =====================================================================
def ecran_repartition(prix: dict, analyses: dict) -> None:
    style.entete("Répartition de départ", "Investir le capital",
                 "Indiquez le montant à placer sur chaque action. Ce qui n'est pas investi reste en liquidités.")
    if portefeuille.depart_fait():
        st.info("La répartition de départ est déjà faite. Utilisez l'écran Achat / vente pour modifier votre portefeuille.")
        return

    r = base.lire_reglages()
    taux = r["taux_frais"]
    plafond = r["max_par_action"] * config.CAPITAL
    reserve = r["reserve_min"] * config.CAPITAL
    with st.container(border=True):
        c1, c2 = st.columns([3, 1.3], vertical_alignment="center")
        html(f"{style.pastille_profil(r['profil'])} &nbsp; au plus <b>{euros(plafond, 0)}</b> par action "
             f"({pourcent(r['max_par_action'], 0)}) · au moins <b>{euros(reserve, 0)}</b> en liquidités "
             f"({pourcent(r['reserve_min'], 0)})", c1)
        c2.button("Proposer selon mon profil", icon=":material/auto_awesome_motion:", width="stretch",
                  on_click=proposer_repartition, args=({c: a.score for c, a in analyses.items()},),
                  help="Répartition calculée à partir des scores et des limites de votre profil. Modifiable.")

    montants, erreurs = {}, []
    with st.container(border=True):
        largeurs = [2.3, 1.1, 1.9, 1, 1]
        for colonne, titre in zip(st.columns(largeurs), ["Action", "Cours", "Montant (€)", "Titres", "Part"]):
            html(f"<span class='hk-entete-tableau'>{titre}</span>", colonne)
        for code, nom in config.ACTIONS.items():
            cols = st.columns(largeurs, vertical_alignment="center")
            analyse = analyses.get(code)
            conseil = moteur.recommander(analyse.score, False, r) if analyse else None
            html(f"<div class='hk-ligne'><b>{nom}</b>&nbsp; {style.pastille_conseil(conseil) if conseil else ''}</div>",
                 cols[0])
            html(f"<span class='hk-ligne'>{euros(prix.get(code))}</span>", cols[1])
            montant = champ_nombre(f"Montant {nom}", f"montant_{code}", conteneur=cols[2], masquer_libelle=True)
            montants[code] = montant or 0.0
            if montants[code] > plafond + 0.01:
                erreurs.append(f"{nom} : {euros(montants[code], 0)} dépasse le maximum de {euros(plafond, 0)}.")
            html(f"<span class='hk-ligne'>{nombre(portefeuille.quantite_possible(montants[code], prix.get(code), taux), 0)}"
                 f"</span>", cols[3])
            html(f"<span class='hk-ligne'>{pourcent(montants[code] / config.CAPITAL, 0)}</span>", cols[4])

    total = sum(montants.values())
    c = st.columns(3)
    style.kpi(c[0], "Total investi", euros(total, 0), f"{pourcent(total / config.CAPITAL, 0)} du capital", accent=True)
    style.kpi(c[1], "Reste en liquidités", euros(config.CAPITAL - total, 0), f"minimum {euros(reserve, 0)}")
    style.kpi(c[2], "Frais estimés", euros(total * taux, 0), f"{pourcent(taux, 2)} par ordre")
    st.write("")

    if total > config.CAPITAL:
        erreurs.append(f"Le total dépasse votre capital de {euros(total - config.CAPITAL)}.")
    elif config.CAPITAL - total < reserve - 0.01:
        erreurs.append(f"Gardez au moins {euros(reserve, 0)} en liquidités (profil {r['profil']}).")
    for erreur in erreurs:
        st.error(erreur)
    if erreurs or total <= 0:
        if total <= 0:
            st.caption("Saisissez au moins un montant, ou cliquez sur « Proposer selon mon profil ».")
        return

    if not st.session_state.get("repartition_en_attente"):
        st.button("Valider la répartition", type="primary",
                  on_click=lambda: st.session_state.update(repartition_en_attente=True))
    else:
        st.warning(f"Confirmez-vous l'investissement de {euros(total)} ? "
                   "Les titres seront achetés au dernier cours connu.")
        c1, c2, _ = st.columns([1, 1, 2])
        c1.button("Confirmer", type="primary", icon=":material/check:", on_click=confirmer_repartition,
                  width="stretch")
        c2.button("Modifier", icon=":material/edit:", width="stretch",
                  on_click=lambda: st.session_state.pop("repartition_en_attente", None))


def proposer_repartition(scores: dict) -> None:
    proposition = portefeuille.repartition_conseillee(scores, base.lire_reglages())
    for code in config.ACTIONS:
        montant = proposition.get(code, 0)
        st.session_state[f"montant_{code}"] = texte_nombre(montant, 0) if montant else ""
    st.session_state.pop("repartition_en_attente", None)


def confirmer_repartition() -> None:
    st.session_state.pop("repartition_en_attente", None)
    montants = {code: lire_nombre(st.session_state.get(f"montant_{code}", "")) or 0.0 for code in config.ACTIONS}
    ok, message = portefeuille.repartir(montants, donnees.cours_actuels(), base.lire_reglages()["taux_frais"])
    flash("success" if ok else "error", message)
    if ok:
        aller_a("Tableau de bord")


# =====================================================================
# Écran 3 – Fiche action
# =====================================================================
def ecran_fiche_action(analyses: dict) -> None:
    haut_gauche, haut_droite = st.columns([3, 1.2], vertical_alignment="bottom")
    code = choisir_action(haut_droite)
    analyse = analyses.get(code)
    with haut_gauche:
        style.entete(config.ACTIONS[code], "Fiche action",
                     f"{code.replace('.PA', '')} · Euronext Paris"
                     + (f" · dernier cours le {date_fr(analyse.date_cours)}" if analyse else ""))
    if analyse is None:
        st.error("Cours indisponibles pour cette action.")
        return

    reglages = base.lire_reglages()
    position = portefeuille.positions().get(code)
    conseil, phrase = moteur.conseiller(analyse, position is not None, reglages)

    c = st.columns(4)
    style.kpi(c[0], "Cours", euros(analyse.cours), f"{variation(analyse.variation_jour, 2)} sur la journée",
              accent=True)
    style.kpi(c[1], "Potentiel selon les analystes",
              variation(analyse.potentiel) if analyse.potentiel is not None else "—",
              "écart avec l'objectif de cours")
    style.kpi(c[2], "Dans votre portefeuille",
              f"{nombre(position['quantite'], 0)} titres" if position else "Aucun titre",
              f"prix de revient {euros(position['prix_revient'])}" if position else "&nbsp;")
    style.kpi(c[3], "Score global", nombre(analyse.score, 2),
              f"achat dès {nombre(reglages['seuil_achat'], 1)} · vente dès {nombre(reglages['seuil_vente'], 1)}")
    st.write("")

    couleur = COULEURS_CONSEIL[conseil]
    html(f"<div class='hk-conseil' style='border-left-color:{couleur}'>"
         f"<div class='hk-conseil-titre' style='color:{couleur}'>Notre conseil · {conseil}</div>"
         f"<div class='hk-conseil-texte'>{style.echapper(phrase)}</div></div>")

    notes = st.columns(4)
    for colonne, (cle, nom) in zip(notes, [("graphique", "Analyse graphique"), ("infos", "Informations"),
                                           ("financier", "Analyse financière"), ("hasard", "Prise en compte du hasard")]):
        html(style.jauge_note(nom, analyse.notes[cle], AIDE[cle]), colonne)
    st.caption(f"Notes de −2 à +2. Recommandations indicatives, calculées selon votre profil {reglages['profil']} : "
               "elles ne garantissent pas de gain.")

    with st.container(border=True):
        titre, choix = st.columns([3, 1.2], vertical_alignment="center")
        titre.markdown("### Évolution du cours")
        periode = choix.segmented_control("Période", ["1 mois", "6 mois", "1 an"], default="1 an",
                                          key="periode_fiche", label_visibility="collapsed") or "1 an"
        jours = {"1 mois": 21, "6 mois": 126, "1 an": 252}[periode]
        ind = graphique.indicateurs(donnees.lire_cours(code))
        afficher_graphique(ind.tail(jours))

    st.button(f"Acheter ou vendre {config.ACTIONS[code]}", type="primary", icon=":material/swap_horiz:",
              on_click=aller_a, args=("Achat / vente", code))

    gauche, droite = st.columns([1.2, 1])
    with gauche, st.container(border=True):
        st.markdown("### Dernières actualités")
        actualites = donnees.lire_actualites(code, 6)
        if not actualites:
            st.caption("Aucune actualité disponible pour le moment.")
        for a in actualites:
            source = f" · {style.echapper(a['source'])}" if a["source"] else ""
            html(f"<div class='hk-actu'>{style.point(COULEURS_TONALITE[a['tonalite']])}"
                 f"<a href='{style.echapper(a['lien'])}' target='_blank'>{style.echapper(a['titre'])}</a>"
                 f"<br><small>{date_fr(a['date'])}{source}</small></div>")
    with droite, st.container(border=True):
        st.markdown("### Détail des calculs")
        afficher_detail(analyse, reglages)


def afficher_graphique(df: pd.DataFrame) -> None:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.06,
                        subplot_titles=("", "RSI (14 jours)", "MACD"))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_haut"], line=dict(width=0), showlegend=False,
                             hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_bas"], line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(29,78,137,0.08)", name="Bandes de Bollinger"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["cloture"], name="Cours", line=dict(width=2.6, color=MARINE)),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MM20"], name="Moyenne 20 j", line=dict(width=1.6, color=OR)),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MM50"], name="Moyenne 50 j",
                             line=dict(width=1.6, color="#7C8DB5", dash="dash")), row=1, col=1)
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

    fig.update_layout(height=640, margin=dict(l=10, r=10, t=20, b=10), hovermode="x unified",
                      legend=dict(orientation="h", y=1.06), separators=", ")
    fig.update_annotations(font=dict(size=12, color=GRIS))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def afficher_detail(analyse, reglages: dict) -> None:
    if analyse.arguments:
        st.dataframe(pd.DataFrame([{
            "Outil": a.outil.capitalize(),
            "Argument": a.texte,
            "Effet": nombre(a.valeur, 1),
        } for a in analyse.arguments]), hide_index=True, width="stretch")
    else:
        st.caption("Aucun signal marqué.")

    sim = analyse.simulation
    if sim:
        st.markdown("**Simulation sur une semaine (10 000 scénarios)**")
        html(f"<div class='hk-recap'><span>Probabilité de hausse</span><b>{pourcent(sim['proba_hausse'], 0)}</b></div>"
             f"<div class='hk-recap'><span>Perte possible (95 %)</span><b>{pourcent(sim['perte_95'], 1)}</b></div>"
             f"<div class='hk-recap'><span>Seuil de votre profil</span><b>{pourcent(reglages['var_max'], 0)}</b></div>")
        fig = go.Figure(go.Histogram(x=sim["rendements"] * 100, nbinsx=50, marker_color=style.MARINE_CLAIR,
                                     opacity=0.85))
        fig.add_vline(x=0, line_dash="dot", line_color=GRIS)
        fig.update_layout(height=200, xaxis_title="Gain ou perte sur 1 semaine (%)", yaxis_title="",
                          margin=dict(l=10, r=10, t=10, b=10), separators=", ")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    if analyse.ratios:
        st.markdown("**Ratios financiers**")
        for cle, libelle in financier.LIBELLES.items():
            v = analyse.ratios.get(cle)
            texte = nombre(v, 1) if cle in ("per", "dette_ebitda") else pourcent(v)
            html(f"<div class='hk-recap'><span>{libelle}</span><b>{texte}</b></div>")
        st.caption("Calculés à partir de data/comptes.csv : à vérifier dans les rapports annuels.")


# =====================================================================
# Écran 4 – Achat / vente (A7)
# =====================================================================
def ecran_achat_vente() -> None:
    style.entete("Achat / vente", "Passer un ordre", "Achetez ou vendez au dernier cours connu, frais compris.")
    r = base.lire_reglages()
    taux = r["taux_frais"]

    gauche, droite = st.columns([1.25, 1])
    with gauche, st.container(border=True):
        code = choisir_action()
        cours, date_cours = donnees.dernier_cours(code)
        if cours is None:
            st.error("Cours indisponible pour le moment.")
            return
        sens = st.segmented_control("Opération", ["Achat", "Vente"], default="Achat", key="sens_ordre") or "Achat"
        detenus = portefeuille.positions().get(code, {}).get("quantite", 0)
        maximum = quantite_maximale(code, sens, cours, detenus, r)
        quantite = champ_nombre("Quantité (nombre de titres)", "quantite_ordre", defaut=1, entier=True,
                                aide="Nombre entier. Les espaces sont acceptés : 1 500.")
        st.caption(f"Maximum possible : {nombre(maximum, 0)} titre{'s' if maximum > 1 else ''}"
                   + (f" (limites du profil {r['profil']})" if sens == "Achat" else ""))
        if sens == "Achat" and portefeuille.limite_atteinte():
            st.warning("Limite de perte atteinte : les achats sont bloqués.")

        valide = quantite is not None and float(quantite).is_integer()
        qte = int(quantite) if valide else quantite
        attente = st.session_state.get("ordre_en_attente")
        if attente is None:
            st.button("Passer l'ordre", type="primary", width="stretch", on_click=preparer_ordre,
                      args=(code, sens.lower(), qte, cours))
        else:
            operation = "l'achat" if attente["sens"] == "achat" else "la vente"
            st.warning(f"Confirmez-vous {operation} de {nombre(attente['quantite'], 0)} "
                       f"{config.ACTIONS[attente['code']]} à {euros(attente['prix'])} ?")
            c1, c2 = st.columns(2)
            c1.button("Confirmer", type="primary", icon=":material/check:", on_click=confirmer_ordre,
                      width="stretch")
            c2.button("Annuler", icon=":material/close:", width="stretch",
                      on_click=lambda: st.session_state.pop("ordre_en_attente", None))

    with droite, st.container(border=True):
        st.markdown("### Récapitulatif")
        q = qte if valide else 0
        montant = q * cours
        frais = portefeuille.calculer_frais(montant, taux)
        total = montant + frais if sens == "Achat" else montant - frais
        liq_apres = portefeuille.liquidites() + (-total if sens == "Achat" else total)
        lignes = [
            ("Cours", f"{euros(cours)} <small>({date_fr(date_cours)})</small>"),
            ("Titres détenus", nombre(detenus, 0)),
            ("Montant", euros(montant)),
            (f"Frais ({pourcent(taux, 2)})", euros(frais)),
            ("Liquidités après l'ordre", euros(liq_apres)),
        ]
        html("".join(f"<div class='hk-recap'><span>{a}</span><b>{b}</b></div>" for a, b in lignes)
             + f"<div class='hk-recap total'><span>{'Total à payer' if sens == 'Achat' else 'Total encaissé'}</span>"
               f"<span>{euros(total)}</span></div>")


def quantite_maximale(code: str, sens: str, cours: float, detenus: int, r: dict) -> int:
    if sens == "Vente":
        return detenus
    etat = portefeuille.valeur(donnees.cours_actuels())
    selon_liquidites = (etat["liquidites"] - r["reserve_min"] * etat["valeur"]) / (cours * (1 + r["taux_frais"]))
    selon_plafond = r["max_par_action"] * etat["valeur"] / cours - detenus
    return max(int(min(selon_liquidites, selon_plafond)), 0)


def preparer_ordre(code: str, sens: str, quantite, prix: float) -> None:
    ok, message = portefeuille.verifier_ordre(code, sens, quantite, prix, base.lire_reglages()["taux_frais"])
    if ok:
        st.session_state["ordre_en_attente"] = {"code": code, "sens": sens, "quantite": quantite, "prix": prix}
    else:
        flash("error", message)


def confirmer_ordre() -> None:
    attente = st.session_state.pop("ordre_en_attente", None)
    if attente:
        ok, message = portefeuille.passer_ordre(taux=base.lire_reglages()["taux_frais"], **attente)
        flash("success" if ok else "error", message)
        if ok:
            calculer_analyses.clear()


# =====================================================================
# Écran 5 – Profil de risque
# =====================================================================
def ecran_profil() -> None:
    r = base.lire_reglages()
    style.entete("Mon profil de risque", "Profil investisseur",
                 "Le profil adapte les conseils, les limites d'achat et la protection contre les pertes.")

    with st.container(border=True):
        c1, c2 = st.columns([1.4, 1], vertical_alignment="center")
        html(f"{style.pastille_profil(r['profil'])}<div style='font-size:1.05rem;margin-top:.5rem'>"
             f"{config.RESUME_PROFILS[r['profil']]}</div>"
             + ("" if r.get("profil_defini") else
                "<div style='color:#6B7280;font-size:.85rem;margin-top:.3rem'>Profil par défaut : "
                "répondez au questionnaire pour l'ajuster.</div>"), c1)
        c2.selectbox("Choisir directement", list(config.PROFILS), index=list(config.PROFILS).index(r["profil"]),
                     key="profil_direct", on_change=appliquer_profil_direct)

    gauche, droite = st.columns([1.2, 1])
    with gauche, st.container(border=True):
        st.markdown("### Questionnaire")
        with st.form("questionnaire", border=False):
            for i, (question, reponses) in enumerate(profil.QUESTIONS):
                st.radio(question, [texte for texte, _ in reponses], index=None, key=f"question_{i}")
            st.form_submit_button("Calculer mon profil", type="primary", on_click=appliquer_questionnaire)

    with droite, st.container(border=True):
        st.markdown("### Ce que change le profil")
        noms = list(config.PROFILS)
        entetes = "".join(
            f"<th style='text-align:right;padding:.4rem .5rem;color:{style.COULEURS_PROFIL[n]}'>{n}</th>" for n in noms)
        corps = ""
        for cle, libelle in LIBELLES_REGLES.items():
            cellules = ""
            for n in noms:
                v = config.PROFILS[n][cle]
                texte = nombre(v, 1) if cle in ("seuil_achat", "seuil_vente") else pourcent(v, 0)
                fond = "background:#F4F6FA;font-weight:700;" if n == r["profil"] else ""
                cellules += f"<td style='text-align:right;padding:.45rem .5rem;{fond}'>{texte}</td>"
            corps += (f"<tr style='border-top:1px solid #EEF1F6'><td style='padding:.45rem .5rem;color:#4B5563'>"
                      f"{libelle}</td>{cellules}</tr>")
        html(f"<table style='width:100%;border-collapse:collapse;font-size:.88rem'>"
             f"<tr><th></th>{entetes}</tr>{corps}</table>")
        st.caption("La perte maximale ne dépasse jamais 10 %, quel que soit le profil.")


def appliquer_questionnaire() -> None:
    reponses = [st.session_state.get(f"question_{i}") for i in range(len(profil.QUESTIONS))]
    if None in reponses:
        flash("error", "Répondez aux 4 questions.")
        return
    points = [dict(choix)[rep] for (_, choix), rep in zip(profil.QUESTIONS, reponses)]
    _appliquer_profil(profil.calculer_profil(points))


def appliquer_profil_direct() -> None:
    _appliquer_profil(st.session_state["profil_direct"])


def _appliquer_profil(nom: str) -> None:
    base.choisir_profil(nom)
    calculer_analyses.clear()
    st.session_state.pop("profil_direct", None)
    flash("success", f"Profil {nom} appliqué. {config.RESUME_PROFILS[nom]}")
    if not portefeuille.depart_fait():
        aller_a("Répartition de départ")


# =====================================================================
# Écran 6 – Historique et réglages
# =====================================================================
def ecran_historique_reglages() -> None:
    style.entete("Historique et réglages", "Suivi", "Vos ordres, l'évolution du portefeuille et les paramètres.")
    onglets = st.tabs(["Ordres", "Évolution", "Réglages", "Données et sauvegarde", "Compte"])
    ordres = portefeuille.lire_ordres()
    hist = portefeuille.lire_historique()

    with onglets[0]:
        if ordres.empty:
            st.caption("Aucun ordre pour le moment.")
        else:
            st.dataframe(pd.DataFrame({
                "Date": pd.to_datetime(ordres["date"]).dt.strftime("%d/%m/%Y %H:%M"),
                "Action": ordres["code"].map(config.ACTIONS),
                "Sens": ordres["sens"].str.capitalize(),
                "Quantité": ordres["quantite"].map(lambda x: nombre(x, 0)),
                "Prix": ordres["prix"].map(euros),
                "Frais": ordres["frais"].map(euros),
                "Origine": ordres["automatique"].map({0: "Client", 1: "Vente automatique"}),
            }).iloc[::-1], hide_index=True, width="stretch")
        st.download_button("Exporter en Excel", icon=":material/download:", data=export_excel(ordres, hist),
                           file_name=f"portefeuille_{date.today():%Y-%m-%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with onglets[1]:
        graphique_historique()
        if not hist.empty:
            st.dataframe(pd.DataFrame({
                "Date": hist["date"].dt.strftime("%d/%m/%Y"),
                "Valeur": hist["valeur"].map(euros),
                "Liquidités": hist["liquidites"].map(euros),
                config.NOM_INDICE: hist["cac40"].map(nombre),
            }).iloc[::-1], hide_index=True, width="stretch")

    with onglets[2]:
        formulaire_reglages()
    with onglets[3]:
        section_donnees()
    with onglets[4]:
        section_compte()


def export_excel(ordres: pd.DataFrame, hist: pd.DataFrame) -> bytes:
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as fichier:
        ordres.to_excel(fichier, sheet_name="Ordres", index=False)
        hist.to_excel(fichier, sheet_name="Historique", index=False)
    return tampon.getvalue()


def formulaire_reglages() -> None:
    r = base.lire_reglages()
    st.caption("Les nombres s'écrivent avec une virgule : 0,5 ou 12,5. "
               "Changer de profil remet les seuils de ce profil.")
    with st.form("reglages"):
        st.markdown("**Poids des 4 outils dans le score** (total = 100 %)")
        c = st.columns(4)
        saisies = {
            "poids_graphique": c[0].text_input("Graphique (%)", texte_nombre(r["poids_graphique"] * 100)),
            "poids_infos": c[1].text_input("Informations (%)", texte_nombre(r["poids_infos"] * 100)),
            "poids_financier": c[2].text_input("Financier (%)", texte_nombre(r["poids_financier"] * 100)),
            "poids_hasard": c[3].text_input("Hasard (%)", texte_nombre(r["poids_hasard"] * 100)),
        }
        st.markdown("**Seuils de recommandation et frais**")
        c = st.columns(3)
        saisies["seuil_achat"] = c[0].text_input("Acheter si le score atteint", texte_nombre(r["seuil_achat"]))
        saisies["seuil_vente"] = c[1].text_input("Vendre si le score descend à", texte_nombre(r["seuil_vente"]))
        saisies["taux_frais"] = c[2].text_input("Frais de courtage (%)", texte_nombre(r["taux_frais"] * 100, 3))
        if st.form_submit_button("Enregistrer", type="primary"):
            valeurs = {cle: lire_nombre(texte) for cle, texte in saisies.items()}
            poids = ["poids_graphique", "poids_infos", "poids_financier", "poids_hasard"]
            if None in valeurs.values():
                st.error("Un des champs ne contient pas un nombre valide.")
            elif abs(sum(valeurs[p] for p in poids) - 100) > 0.01:
                st.error(f"Le total des poids doit faire 100 % (actuellement "
                         f"{nombre(sum(valeurs[p] for p in poids), 1)} %).")
            elif not -2 <= valeurs["seuil_vente"] < valeurs["seuil_achat"] <= 2:
                st.error("Les seuils doivent être entre −2 et 2, celui de vente sous celui d'achat.")
            elif not 0 <= valeurs["taux_frais"] <= 5:
                st.error("Les frais doivent être entre 0 et 5 %.")
            else:
                for p in poids:
                    base.ecrire_reglage(p, valeurs[p] / 100)
                base.ecrire_reglage("seuil_achat", valeurs["seuil_achat"])
                base.ecrire_reglage("seuil_vente", valeurs["seuil_vente"])
                base.ecrire_reglage("taux_frais", valeurs["taux_frais"] / 100)
                calculer_analyses.clear()
                st.success("Réglages enregistrés.")


def section_donnees() -> None:
    st.markdown("**Importer des cours** (si le téléchargement automatique ne fonctionne pas)")
    st.caption("Fichier CSV avec au moins une colonne « date » et une colonne « clôture » (ex. export ABC Bourse).")
    code = st.selectbox("Action concernée", list(config.ACTIONS) + [config.INDICE],
                        format_func=lambda c: config.ACTIONS.get(c, config.NOM_INDICE), key="code_import")
    fichier = st.file_uploader("Fichier CSV", type=["csv", "txt"])
    if fichier is not None and st.button("Importer"):
        try:
            nb = donnees.importer_csv_cours(fichier, code)
            calculer_analyses.clear()
            st.success(f"{nb} cours importés.")
        except ValueError as erreur:
            st.error(str(erreur))

    st.divider()
    st.markdown("**Sauvegarde complète** (compte, ordres, historique, réglages)")
    st.caption("Utile si l'application est en ligne : téléchargez la sauvegarde régulièrement, "
               "et restaurez-la si les données ont été effacées.")
    c1, c2 = st.columns(2)
    c1.download_button("Télécharger la sauvegarde", icon=":material/download:", data=base.exporter_base(),
                       file_name=f"cap500_sauvegarde_{date.today():%Y-%m-%d}.db",
                       mime="application/octet-stream", width="stretch")
    restauration = c2.file_uploader("Restaurer une sauvegarde (.db)", type=["db"], key="fichier_restauration")
    if restauration is not None and c2.button("Restaurer", width="stretch"):
        ok, message = base.restaurer_base(restauration.getvalue())
        if ok:
            tout_recalculer()
        flash("success" if ok else "error", message)
        st.rerun()

    st.divider()
    st.markdown("**Comptes annuels** – à modifier dans `data/comptes.csv`")
    comptes = donnees.charger_comptes()
    if not comptes.empty:
        st.dataframe(comptes, hide_index=True, width="stretch")
    st.markdown("**Objectifs des analystes** – à mettre à jour chaque semaine dans `data/analystes.csv`")
    analystes = donnees.charger_analystes()
    if not analystes.empty:
        st.dataframe(analystes, hide_index=True, width="stretch")
    st.caption("Après une modification des fichiers, cliquez sur « Actualiser les données » dans le menu.")


def section_compte() -> None:
    gauche, droite = st.columns(2)
    with gauche, st.container(border=True):
        st.markdown("### Identifiant et mot de passe")
        with st.form("identifiants", border=False):
            actuel = st.text_input("Mot de passe actuel", type="password")
            identifiant = st.text_input("Identifiant", value=auth.identifiant_actuel())
            mdp = st.text_input("Nouveau mot de passe", type="password")
            confirmation = st.text_input("Confirmer le mot de passe", type="password")
            if st.form_submit_button("Modifier", type="primary"):
                ok, message = auth.changer_identifiants(actuel, identifiant, mdp, confirmation)
                (st.success if ok else st.error)(message)
                if ok:
                    st.session_state["identifiant"] = identifiant.strip()

        st.markdown("### Code de récupération")
        st.caption("Un nouveau code remplace l'ancien.")
        with st.form("nouveau_code", border=False):
            mdp_code = st.text_input("Mot de passe actuel", type="password", key="mdp_code")
            if st.form_submit_button("Générer un nouveau code"):
                ok, message = auth.verifier(st.session_state.get("identifiant", ""), mdp_code)
                if ok:
                    html(f"<div class='hk-code'>{auth.nouveau_code_recuperation()}</div>")
                    st.caption("Notez-le : il ne sera plus affiché.")
                else:
                    st.error(message)

    with droite, st.container(border=True):
        st.markdown("### Réinitialiser le portefeuille")
        st.caption("Supprime tous les ordres et l'historique pour repartir de 500 000 €. "
                   "Le compte, le profil, les cours et les actualités sont conservés. Une copie de sécurité est faite.")
        st.text_input("Tapez REINITIALISER pour confirmer", key="confirmation_reinit")
        st.button("Réinitialiser le portefeuille", on_click=reinitialiser,
                  disabled=st.session_state.get("confirmation_reinit") != "REINITIALISER")


def reinitialiser() -> None:
    base.copie_securite("avant_reinitialisation")
    base.reinitialiser_portefeuille()
    tout_recalculer()
    st.session_state["confirmation_reinit"] = ""
    flash("success", "Portefeuille réinitialisé.")
    aller_a("Répartition de départ")
