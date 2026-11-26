"""
Charte graphique CAP 500 : couleurs, logo, icônes, feuille de style et petits composants HTML.
"""
import base64
import html as _html

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import config

# ---------- Couleurs ----------
MARINE = "#0B2545"
MARINE_CLAIR = "#1D4E89"
OR = "#C9A227"
VERT = "#1F8A5B"
ROUGE = "#C0392B"
ORANGE = "#D98E04"
GRIS = "#6B7280"
FOND = "#F5F7FB"
BORDURE = "#E3E7EF"

COULEURS_CONSEIL = {"Acheter": VERT, "Vendre": ROUGE, "Ne rien faire": GRIS}
LIBELLES_CONSEIL = {"Acheter": "Acheter", "Vendre": "Vendre", "Ne rien faire": "Attendre"}
COULEURS_PROFIL = {"Prudent": "#2E86AB", "Équilibré": OR, "Dynamique": "#C8553D"}

# ---------- Thème des graphiques Plotly ----------
pio.templates["cap500"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", color="#1B2433", size=13),
    colorway=[MARINE, OR, MARINE_CLAIR, VERT, ROUGE, "#7C8DB5"],
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#FFFFFF",
    xaxis=dict(gridcolor="#EEF1F6", linecolor=BORDURE, zeroline=False),
    yaxis=dict(gridcolor="#EEF1F6", linecolor=BORDURE, zeroline=False),
    hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=BORDURE, font=dict(color="#1B2433")),
    separators=", ",
))
pio.templates.default = "plotly_white+cap500"

# ---------- Icônes (traits simples, dessinées en SVG) ----------
_TRACES = {
    "portefeuille": '<rect x="2" y="6" width="20" height="14" rx="2"/><path d="M2 10h20"/><path d="M16 15h2"/>',
    "conseil": '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.3h6c0-1 .4-1.8 1-2.3A7 7 0 0 0 12 2z"/>',
    "bouclier": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "courbe": '<polyline points="22 6 13.5 14.5 8.5 9.5 2 16"/><polyline points="16 6 22 6 22 12"/>',
    "haut": '<line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>',
    "bas": '<line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>',
    "info": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    "valide": '<polyline points="20 6 9 17 4 12"/>',
    "cadenas": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "utilisateurs": '<circle cx="9" cy="8" r="4"/><path d="M2 21v-1a6 6 0 0 1 12 0v1"/><path d="M16 4a4 4 0 0 1 0 8"/><path d="M22 21v-1a6 6 0 0 0-4-5.6"/>',
    "alerte": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
}


def icone(nom: str, taille: int = 20, couleur: str = "currentColor", epaisseur: float = 2) -> str:
    return (f"<svg width='{taille}' height='{taille}' viewBox='0 0 24 24' fill='none' stroke='{couleur}' "
            f"stroke-width='{epaisseur}' stroke-linecap='round' stroke-linejoin='round' "
            f"style='flex-shrink:0;vertical-align:middle'>{_TRACES[nom]}</svg>")


# ---------- Logo ----------
def _image(nom: str):
    chemin = config.DOSSIER_ASSETS / nom
    if not chemin.exists():
        return None, None
    mime = "image/svg+xml" if chemin.suffix == ".svg" else "image/png"
    return mime, base64.b64encode(chemin.read_bytes()).decode()


def logo_html(clair: bool = False, largeur: int = 210) -> str:
    """Le logo en HTML. Pour utiliser votre propre logo, déposez assets/logo.png (il remplace le logo dessiné)."""
    mime, contenu = _image("logo.png")
    if contenu is None:
        mime, contenu = _image("logo_clair.svg" if clair else "logo.svg")
    if contenu is None:
        return f"<div class='hk-marque'>{config.NOM_APPLI}</div>"
    return f"<img src='data:{mime};base64,{contenu}' width='{largeur}' alt='{config.NOM_APPLI}'>"


def icone_page():
    chemin = config.DOSSIER_ASSETS / "icone.png"
    return str(chemin) if chemin.exists() else None


# ---------- Feuille de style ----------
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stMarkdown, button, input, textarea, select {{
    font-family: 'Inter', 'Segoe UI', Helvetica, Arial, sans-serif;
}}
.stApp {{ background: {FOND}; }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1240px; }}
#MainMenu, footer, [data-testid="stStatusWidget"], [data-testid="stDecoration"] {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stHeaderActionElements"] {{ display: none; }}

h1, h2, h3 {{ color: {MARINE}; letter-spacing: -0.01em; }}
[data-testid="stMarkdownContainer"] h3 {{ font-size: 1.1rem !important; font-weight: 700 !important;
    padding: .1rem 0 .55rem !important; }}
[data-testid="stMarkdownContainer"] p {{ line-height: 1.55; }}

/* Cadres en cartes blanches */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: #FFFFFF; border: 1px solid {BORDURE} !important; border-radius: 16px;
    box-shadow: 0 1px 2px rgba(11,37,69,.04), 0 6px 18px rgba(11,37,69,.05);
}}
[data-testid="stExpander"] details {{ background: #FFFFFF; border: 1px solid {BORDURE}; border-radius: 12px; }}
[data-testid="stExpander"] summary p {{ font-weight: 600; color: {MARINE}; }}

/* Boutons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
    border-radius: 10px; font-weight: 600; border: 1px solid {BORDURE}; min-height: 2.6rem;
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
    background: {MARINE}; border-color: {MARINE}; color: #FFFFFF;
}}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
    background: {MARINE_CLAIR}; border-color: {MARINE_CLAIR};
}}
.stButton > button[kind="tertiary"] {{ color: {MARINE_CLAIR}; border: none; min-height: 0; padding: 0; }}

/* Champs */
[data-testid="stTextInput"] input {{ border-radius: 10px; }}
[data-testid="stWidgetLabel"] p {{ font-weight: 600; color: #374151; }}

/* Onglets */
.stTabs [data-baseweb="tab-list"] {{ gap: .3rem; border-bottom: 1px solid {BORDURE}; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 600; color: {GRIS}; padding: .6rem .9rem; }}
.stTabs [aria-selected="true"] {{ color: {MARINE}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: {OR}; height: 3px; }}

/* Menu latéral */
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {MARINE} 0%, #0F2E52 100%); }}
section[data-testid="stSidebar"] * {{ color: #DCE3EE; }}
section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap: 2px; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label {{
    width: 100%; padding: .6rem .8rem; border-radius: 10px; transition: background .15s;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ background: rgba(255,255,255,.07); }}
section[data-testid="stSidebar"] div[role="radiogroup"] label[data-selected="true"] {{
    background: rgba(201,162,39,.16); box-shadow: inset 3px 0 0 {OR};
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label[data-selected="true"] p {{ color: #FFFFFF; font-weight: 600; }}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:not([data-testid="stMarkdownContainer"]) {{
    display: none; }}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {{ display: none; }}
section[data-testid="stSidebar"] .stButton > button {{
    background: transparent; border: 1px solid rgba(255,255,255,.22); color: #DCE3EE;
}}
section[data-testid="stSidebar"] .stButton > button:hover {{ border-color: {OR}; color: #FFFFFF; }}
section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.12); }}

/* En-têtes de page */
.hk-entete {{ margin-bottom: 1.3rem; }}
.hk-surtitre {{ font-size: .76rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: {OR}; }}
.hk-titre {{ font-size: 1.95rem; font-weight: 800; color: {MARINE}; line-height: 1.2; margin: .15rem 0 .25rem; }}
.hk-soustitre {{ color: {GRIS}; font-size: 1rem; }}
.hk-marque {{ font-weight: 800; letter-spacing: .2em; color: #FFFFFF; }}

/* Chiffres clés */
.hk-kpi {{ background: #FFFFFF; border: 1px solid {BORDURE}; border-radius: 16px; padding: 1rem 1.15rem;
          box-shadow: 0 1px 2px rgba(11,37,69,.04); height: 100%; }}
.hk-kpi-libelle {{ font-size: .82rem; color: {GRIS}; font-weight: 600; display: flex; align-items: center; gap: .35rem; }}
.hk-kpi-valeur {{ font-size: 1.5rem; font-weight: 800; color: {MARINE}; margin-top: .3rem; white-space: nowrap; }}
.hk-kpi-detail {{ font-size: .82rem; margin-top: .25rem; color: {GRIS}; line-height: 1.4; }}
.hk-kpi.accent {{ background: linear-gradient(135deg, {MARINE} 0%, {MARINE_CLAIR} 100%); border: none; }}
.hk-kpi.accent .hk-kpi-libelle {{ color: #B9C6DA; }}
.hk-kpi.accent .hk-kpi-valeur {{ color: #FFFFFF; }}
.hk-kpi.accent .hk-kpi-detail {{ color: #DCE3EE; }}
.hk-kpi.accent .hk-hausse {{ color: #7FE0A8; }}
.hk-kpi.accent .hk-baisse {{ color: #FF9C8F; }}
.hk-aide {{ display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px;
           border-radius: 50%; background: #EEF1F6; color: {GRIS}; font-size: .68rem; font-weight: 700; cursor: help; }}
.hk-kpi.accent .hk-aide {{ background: rgba(255,255,255,.15); color: #FFFFFF; }}

.hk-hausse {{ color: {VERT}; font-weight: 600; }}
.hk-baisse {{ color: {ROUGE}; font-weight: 600; }}
.hk-neutre {{ color: {GRIS}; font-weight: 600; }}

.hk-pastille {{ display: inline-block; padding: .25rem .75rem; border-radius: 999px; font-size: .8rem;
               font-weight: 700; white-space: nowrap; }}
.hk-point {{ display: inline-block; width: .6rem; height: .6rem; border-radius: 50%; margin-right: .45rem; }}

/* Résumé du jour */
.hk-resume {{ background: #FFFFFF; border: 1px solid {BORDURE}; border-radius: 16px; padding: 1.1rem 1.3rem;
             margin-bottom: 1rem; box-shadow: 0 6px 18px rgba(11,37,69,.05); }}
.hk-resume-titre {{ font-weight: 800; color: {MARINE}; font-size: 1.05rem; margin-bottom: .5rem; }}
.hk-resume-ligne {{ display: flex; gap: .75rem; align-items: flex-start; padding: .45rem 0; font-size: .98rem;
                   color: #1F2937; border-top: 1px solid #F0F2F7; }}
.hk-resume-ligne:first-of-type {{ border-top: none; }}
.hk-rond {{ width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
           flex-shrink: 0; }}

/* Conseil */
.hk-conseil {{ border-radius: 16px; padding: 1.2rem 1.4rem; background: #FFFFFF; border: 1px solid {BORDURE};
              border-left-width: 6px; margin-bottom: 1rem; box-shadow: 0 6px 18px rgba(11,37,69,.05); }}
.hk-conseil-titre {{ font-size: .78rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }}
.hk-conseil-grand {{ font-size: 1.6rem; font-weight: 800; margin: .15rem 0 .35rem; }}
.hk-conseil-texte {{ font-size: 1.02rem; color: #1B2433; line-height: 1.55; }}
.hk-conseil-sens {{ font-size: .92rem; color: {GRIS}; margin-top: .4rem; }}

/* Les 4 points étudiés */
.hk-note {{ background: #FFFFFF; border: 1px solid {BORDURE}; border-radius: 14px; padding: .9rem 1rem; height: 100%; }}
.hk-note-nom {{ font-size: .92rem; color: {MARINE}; font-weight: 700; }}
.hk-note-tech {{ font-size: .72rem; color: #9AA3B2; text-transform: uppercase; letter-spacing: .06em; }}
.hk-note-verdict {{ font-size: 1.05rem; font-weight: 800; margin-top: .45rem; }}
.hk-note-question {{ font-size: .8rem; color: {GRIS}; margin-top: .45rem; line-height: 1.4; }}
.hk-jauge {{ position: relative; height: 6px; background: #EEF1F6; border-radius: 3px; margin-top: .5rem; }}
.hk-jauge-milieu {{ position: absolute; left: 50%; top: -3px; width: 1px; height: 12px; background: #B8C0CC; }}
.hk-jauge-barre {{ position: absolute; top: 0; height: 6px; border-radius: 3px; }}

/* Listes */
.hk-ligne {{ font-size: .95rem; padding: .3rem 0; line-height: 1.4; }}
.hk-ligne small {{ color: {GRIS}; }}
.hk-entete-tableau {{ font-size: .72rem; font-weight: 700; color: {GRIS}; text-transform: uppercase; letter-spacing: .06em; }}
.hk-argument {{ display: flex; gap: .65rem; padding: .6rem 0; border-top: 1px solid #F0F2F7; }}
.hk-argument:first-child {{ border-top: none; }}
.hk-argument small {{ color: {GRIS}; display: block; margin-top: .1rem; }}
.hk-actu {{ padding: .6rem 0; border-top: 1px solid #F0F2F7; font-size: .93rem; }}
.hk-actu:first-child {{ border-top: none; }}
.hk-actu a {{ color: {MARINE}; text-decoration: none; font-weight: 500; }}
.hk-actu a:hover {{ text-decoration: underline; }}
.hk-actu small {{ color: {GRIS}; }}
.hk-recap {{ display: flex; justify-content: space-between; gap: 1rem; padding: .5rem 0; border-bottom: 1px dashed {BORDURE}; }}
.hk-recap span:first-child {{ color: #4B5563; }}
.hk-recap.total {{ border-bottom: none; font-weight: 800; color: {MARINE}; font-size: 1.12rem; }}
.hk-etape-num {{ display: inline-flex; width: 24px; height: 24px; border-radius: 50%; background: {MARINE}; color: #FFFFFF;
                font-size: .8rem; font-weight: 700; align-items: center; justify-content: center; margin-right: .45rem; }}
.hk-question {{ font-weight: 700; color: {MARINE}; margin: .4rem 0 .2rem; display: flex; align-items: center; }}

/* Étapes de démarrage */
.hk-etapes {{ display: flex; gap: .6rem; margin-bottom: 1.2rem; flex-wrap: wrap; }}
.hk-etape {{ flex: 1; min-width: 180px; background: #FFFFFF; border: 1px solid {BORDURE}; border-radius: 12px;
            padding: .7rem .9rem; display: flex; gap: .6rem; align-items: center; font-size: .88rem; color: {GRIS}; }}
.hk-etape b {{ color: #374151; }}
.hk-etape .hk-etape-num {{ background: #E5E9F0; color: {GRIS}; margin: 0; flex-shrink: 0; }}
.hk-etape.active {{ border-color: {OR}; box-shadow: 0 0 0 3px rgba(201,162,39,.15); }}
.hk-etape.active .hk-etape-num {{ background: {OR}; color: #FFFFFF; }}
.hk-etape.faite .hk-etape-num {{ background: {VERT}; color: #FFFFFF; }}

/* Cartes de profil */
.hk-profil {{ background: #FFFFFF; border: 2px solid {BORDURE}; border-radius: 16px; padding: 1.1rem 1.2rem;
              min-height: 330px; margin-bottom: .5rem; }}
.hk-profil.actif {{ border-color: {OR}; box-shadow: 0 0 0 4px rgba(201,162,39,.12); }}
.hk-profil-nom {{ font-size: 1.2rem; font-weight: 800; }}
.hk-profil-pour {{ color: #374151; margin: .3rem 0 .7rem; font-size: .93rem; min-height: 2.6rem; }}
.hk-profil ul {{ padding-left: 0; list-style: none; margin: 0; }}
.hk-profil li {{ display: flex; gap: .5rem; font-size: .86rem; color: #4B5563; padding: .25rem 0; }}

/* Page de connexion */
.hk-hero {{ background: linear-gradient(150deg, {MARINE} 0%, #123A6B 60%, {MARINE_CLAIR} 100%); border-radius: 24px;
           padding: 2.4rem 2.4rem 2rem; color: #FFFFFF; min-height: 600px; display: flex; flex-direction: column;
           position: relative; overflow: hidden; }}
.hk-hero::after {{ content: ""; position: absolute; right: -80px; bottom: -80px; width: 280px; height: 280px;
                  border-radius: 50%; border: 40px solid rgba(201,162,39,.12); }}
.hk-hero-titre {{ color: #FFFFFF; font-size: 2.3rem; font-weight: 800; line-height: 1.2; margin: 2.2rem 0 .9rem; }}
.hk-or {{ color: {OR}; }}
.hk-hero p {{ color: #C9D4E5; font-size: 1.02rem; max-width: 30rem; }}
.hk-atout {{ display: flex; gap: .9rem; align-items: flex-start; margin-top: 1.2rem; }}
.hk-atout-icone {{ width: 42px; height: 42px; border-radius: 12px; background: rgba(255,255,255,.09);
                  display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
.hk-atout b {{ color: #FFFFFF; }}
.hk-atout div {{ color: #C9D4E5; font-size: .93rem; }}
.hk-hero-pied {{ margin-top: auto; padding-top: 1.6rem; font-size: .8rem; color: #9FB0C8; }}
.hk-acces-titre {{ font-size: 1.7rem; font-weight: 800; color: {MARINE}; margin-top: .5rem; }}

.hk-code {{ font-family: 'Consolas', monospace; font-size: 1.7rem; font-weight: 700; letter-spacing: .15em;
           background: {FOND}; border: 2px dashed {OR}; border-radius: 14px; padding: 1.1rem; text-align: center;
           color: {MARINE}; }}
.hk-avatar {{ width: 40px; height: 40px; border-radius: 50%; background: {OR}; color: {MARINE} !important;
             display: flex; align-items: center; justify-content: center; font-weight: 800; flex-shrink: 0; }}
.hk-lexique {{ background: #FFFFFF; border: 1px solid {BORDURE}; border-radius: 12px; padding: .8rem 1rem; margin-bottom: .7rem; }}
.hk-lexique b {{ color: {MARINE}; }}
.hk-lexique div {{ color: #4B5563; font-size: .9rem; margin-top: .2rem; }}
.hk-pied {{ text-align: center; color: {GRIS}; font-size: .8rem; margin-top: 2.5rem; }}
</style>
"""


def appliquer_style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# ---------- Composants ----------
def echapper(texte) -> str:
    return _html.escape(str(texte))


def entete(titre: str, surtitre: str = "", sous_titre: str = "") -> None:
    st.markdown(
        f"<div class='hk-entete'><div class='hk-surtitre'>{echapper(surtitre)}</div>"
        f"<div class='hk-titre'>{echapper(titre)}</div>"
        f"<div class='hk-soustitre'>{sous_titre}</div></div>",
        unsafe_allow_html=True,
    )


def classe_variation(x) -> str:
    if x is None or x != x or abs(x) < 1e-12:
        return "hk-neutre"
    return "hk-hausse" if x > 0 else "hk-baisse"


def aide(texte: str) -> str:
    """Petit « ? » : l'explication apparaît au survol de la souris."""
    return f"<span class='hk-aide' title='{echapper(texte)}'>?</span>"


def kpi(colonne, libelle: str, valeur: str, detail: str = "", accent: bool = False, explication: str = "") -> None:
    colonne.markdown(
        f"<div class='hk-kpi{' accent' if accent else ''}'><div class='hk-kpi-libelle'>{libelle}"
        f"{aide(explication) if explication else ''}</div>"
        f"<div class='hk-kpi-valeur'>{valeur}</div><div class='hk-kpi-detail'>{detail}</div></div>",
        unsafe_allow_html=True,
    )


def pastille(texte: str, couleur: str) -> str:
    return (f"<span class='hk-pastille' style='background:{couleur}1A;color:{couleur};"
            f"border:1px solid {couleur}40'>{echapper(texte)}</span>")


def pastille_conseil(conseil: str) -> str:
    return pastille(LIBELLES_CONSEIL[conseil], COULEURS_CONSEIL[conseil])


def pastille_profil(profil: str) -> str:
    return pastille(f"Profil {profil}", COULEURS_PROFIL[profil])


def point(couleur: str) -> str:
    return f"<span class='hk-point' style='background:{couleur}'></span>"


def rond(nom_icone: str, couleur: str) -> str:
    return f"<div class='hk-rond' style='background:{couleur}1A'>{icone(nom_icone, 18, couleur)}</div>"


def couleur_note(note: float) -> str:
    return VERT if note >= 0.3 else ROUGE if note <= -0.3 else GRIS


def jauge(note: float) -> str:
    """Barre de −2 à +2 qui part du milieu."""
    couleur = couleur_note(note)
    largeur = min(abs(note), 2) / 2 * 50
    gauche = 50 if note >= 0 else 50 - largeur
    return (f"<div class='hk-jauge'><div class='hk-jauge-milieu'></div>"
            f"<div class='hk-jauge-barre' style='left:{gauche}%;width:{largeur}%;background:{couleur}'></div></div>")


def etapes(actuelle: int, titres: list) -> str:
    """Les étapes de démarrage : 1 = profil, 2 = investir, 3 = suivre."""
    blocs = []
    for i, (titre, texte) in enumerate(titres, start=1):
        etat = "faite" if i < actuelle else "active" if i == actuelle else ""
        numero = icone("valide", 14, "#FFFFFF", 3) if i < actuelle else str(i)
        blocs.append(f"<div class='hk-etape {etat}'><span class='hk-etape-num'>{numero}</span>"
                     f"<div><b>{echapper(titre)}</b><br>{echapper(texte)}</div></div>")
    return f"<div class='hk-etapes'>{''.join(blocs)}</div>"


def initiales(nom: str) -> str:
    morceaux = [m for m in nom.replace(".", " ").replace("_", " ").split() if m]
    return ("".join(m[0] for m in morceaux[:2]) or "?").upper()
