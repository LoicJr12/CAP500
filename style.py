"""
Charte graphique CAP 500 : couleurs, logo, styles CSS, petits composants HTML et thème des graphiques.
"""
import base64
import html

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
FOND = "#F4F6FA"
BORDURE = "#E3E7EF"

COULEURS_CONSEIL = {"Acheter": VERT, "Vendre": ROUGE, "Ne rien faire": GRIS}
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
))
pio.templates.default = "plotly_white+cap500"


# ---------- Logo ----------
def _image(nom: str):
    """Renvoie (type MIME, contenu) d'une image du dossier assets."""
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

html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select {{
    font-family: 'Inter', 'Segoe UI', Helvetica, Arial, sans-serif;
}}
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1280px; }}
#MainMenu, footer, [data-testid="stStatusWidget"], [data-testid="stDecoration"] {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}

h1, h2, h3 {{ color: {MARINE}; letter-spacing: -0.01em; }}
[data-testid="stMarkdownContainer"] h3 {{ font-size: 1.12rem !important; font-weight: 700 !important;
    padding: .1rem 0 .5rem !important; }}
[data-testid="stHeaderActionElements"] {{ display: none; }}

/* Cadres (st.container(border=True)) en cartes blanches */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: #FFFFFF; border: 1px solid {BORDURE} !important; border-radius: 14px;
    box-shadow: 0 1px 2px rgba(11,37,69,.04), 0 4px 14px rgba(11,37,69,.04);
}}

/* Boutons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
    border-radius: 10px; font-weight: 600; border: 1px solid {BORDURE};
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
    background: {MARINE}; border-color: {MARINE}; color: #FFFFFF;
}}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
    background: {MARINE_CLAIR}; border-color: {MARINE_CLAIR};
}}

/* Champs de saisie */
[data-testid="stTextInput"] input {{ border-radius: 9px; }}

/* Onglets */
.stTabs [data-baseweb="tab-list"] {{ gap: .4rem; border-bottom: 1px solid {BORDURE}; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 600; color: {GRIS}; }}
.stTabs [aria-selected="true"] {{ color: {MARINE}; }}

/* Menu latéral */
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {MARINE} 0%, #0F2E52 100%); }}
section[data-testid="stSidebar"] * {{ color: #DCE3EE; }}
section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap: 2px; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label {{
    width: 100%; padding: .55rem .75rem; border-radius: 9px; transition: background .15s;
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

/* Composants maison */
.hk-entete {{ margin-bottom: 1.2rem; }}
.hk-surtitre {{ font-size: .78rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: {OR}; }}
.hk-titre {{ font-size: 1.9rem; font-weight: 800; color: {MARINE}; line-height: 1.2; margin: .15rem 0 .2rem; }}
.hk-soustitre {{ color: {GRIS}; font-size: .95rem; }}
.hk-marque {{ font-weight: 800; letter-spacing: .2em; color: #FFFFFF; }}

.hk-kpi {{ background: #FFFFFF; border: 1px solid {BORDURE}; border-radius: 14px; padding: 1rem 1.1rem;
          box-shadow: 0 1px 2px rgba(11,37,69,.04); height: 100%; }}
.hk-kpi-libelle {{ font-size: .8rem; color: {GRIS}; font-weight: 600; }}
.hk-kpi-valeur {{ font-size: 1.45rem; font-weight: 800; color: {MARINE}; margin-top: .25rem; white-space: nowrap; }}
.hk-kpi-detail {{ font-size: .82rem; margin-top: .2rem; color: {GRIS}; }}
.hk-kpi.accent {{ background: linear-gradient(135deg, {MARINE} 0%, {MARINE_CLAIR} 100%); border: none; }}
.hk-kpi.accent .hk-kpi-libelle {{ color: #B9C6DA; }}
.hk-kpi.accent .hk-kpi-valeur {{ color: #FFFFFF; }}
.hk-kpi.accent .hk-kpi-detail {{ color: #DCE3EE; }}
.hk-kpi.accent .hk-hausse {{ color: #7FE0A8; }}
.hk-kpi.accent .hk-baisse {{ color: #FF9C8F; }}

.hk-hausse {{ color: {VERT}; font-weight: 600; }}
.hk-baisse {{ color: {ROUGE}; font-weight: 600; }}
.hk-neutre {{ color: {GRIS}; font-weight: 600; }}

.hk-pastille {{ display: inline-block; padding: .22rem .7rem; border-radius: 999px; font-size: .8rem;
               font-weight: 700; white-space: nowrap; }}
.hk-point {{ display: inline-block; width: .6rem; height: .6rem; border-radius: 50%; margin-right: .45rem; }}

.hk-conseil {{ border-radius: 14px; padding: 1.1rem 1.3rem; background: #FFFFFF; border: 1px solid {BORDURE};
              border-left-width: 6px; margin-bottom: .8rem; }}
.hk-conseil-titre {{ font-size: .8rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }}
.hk-conseil-texte {{ font-size: 1.05rem; color: #1B2433; margin-top: .35rem; line-height: 1.5; }}

.hk-note {{ background: #FFFFFF; border: 1px solid {BORDURE}; border-radius: 12px; padding: .8rem .9rem; }}
.hk-note-haut {{ display: flex; justify-content: space-between; align-items: baseline; }}
.hk-note-nom {{ font-size: .8rem; color: {GRIS}; font-weight: 600; }}
.hk-note-valeur {{ font-size: 1.15rem; font-weight: 800; }}
.hk-jauge {{ position: relative; height: 6px; background: #EEF1F6; border-radius: 3px; margin-top: .55rem; }}
.hk-jauge-milieu {{ position: absolute; left: 50%; top: -3px; width: 1px; height: 12px; background: #B8C0CC; }}
.hk-jauge-barre {{ position: absolute; top: 0; height: 6px; border-radius: 3px; }}

.hk-ligne {{ font-size: .95rem; }}
.hk-ligne small {{ color: {GRIS}; }}
.hk-entete-tableau {{ font-size: .75rem; font-weight: 700; color: {GRIS}; text-transform: uppercase; letter-spacing: .06em; }}

.hk-actu {{ padding: .6rem 0; border-bottom: 1px solid #EEF1F6; font-size: .93rem; }}
.hk-actu a {{ color: {MARINE}; text-decoration: none; font-weight: 500; }}
.hk-actu a:hover {{ text-decoration: underline; }}
.hk-actu small {{ color: {GRIS}; }}

.hk-recap {{ display: flex; justify-content: space-between; padding: .45rem 0; border-bottom: 1px dashed {BORDURE}; }}
.hk-recap.total {{ border-bottom: none; font-weight: 800; color: {MARINE}; font-size: 1.1rem; }}

.hk-code {{ font-family: 'Consolas', monospace; font-size: 1.6rem; font-weight: 700; letter-spacing: .15em;
           background: {FOND}; border: 2px dashed {OR}; border-radius: 12px; padding: 1rem; text-align: center;
           color: {MARINE}; }}
.hk-pied {{ text-align: center; color: {GRIS}; font-size: .8rem; margin-top: 2.5rem; }}
</style>
"""


def appliquer_style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# ---------- Composants ----------
def echapper(texte) -> str:
    return html.escape(str(texte))


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


def kpi(colonne, libelle: str, valeur: str, detail: str = "", accent: bool = False) -> None:
    colonne.markdown(
        f"<div class='hk-kpi{' accent' if accent else ''}'><div class='hk-kpi-libelle'>{libelle}</div>"
        f"<div class='hk-kpi-valeur'>{valeur}</div><div class='hk-kpi-detail'>{detail}</div></div>",
        unsafe_allow_html=True,
    )


def pastille(texte: str, couleur: str) -> str:
    return (f"<span class='hk-pastille' style='background:{couleur}1A;color:{couleur};"
            f"border:1px solid {couleur}40'>{echapper(texte)}</span>")


def pastille_conseil(conseil: str) -> str:
    return pastille(conseil, COULEURS_CONSEIL[conseil])


def pastille_profil(profil: str) -> str:
    return pastille(f"Profil {profil}", COULEURS_PROFIL[profil])


def point(couleur: str) -> str:
    return f"<span class='hk-point' style='background:{couleur}'></span>"


def jauge_note(nom: str, note: float, aide: str = "") -> str:
    """Note de −2 à +2 avec une barre qui part du milieu."""
    couleur = VERT if note > 0.05 else ROUGE if note < -0.05 else GRIS
    largeur = min(abs(note), 2) / 2 * 50
    gauche = 50 if note >= 0 else 50 - largeur
    texte = (("+" if note > 0.05 else "") + f"{note:.1f}").replace(".", ",").replace("-", "−")
    return (f"<div class='hk-note' title='{echapper(aide)}'><div class='hk-note-haut'>"
            f"<span class='hk-note-nom'>{nom}</span>"
            f"<span class='hk-note-valeur' style='color:{couleur}'>{texte}"
            f"</span></div><div class='hk-jauge'><div class='hk-jauge-milieu'></div>"
            f"<div class='hk-jauge-barre' style='left:{gauche}%;width:{largeur}%;background:{couleur}'></div>"
            f"</div></div>")
