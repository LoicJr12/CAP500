"""
Comptes et connexion sécurisée (logigramme 2) :
- chaque personne crée son compte et a son propre portefeuille de 500 000 € ;
- mot de passe de 8 caractères minimum, enregistré haché (jamais en clair) ;
- compte bloqué 15 minutes après 5 essais ratés ;
- code de récupération pour choisir un nouveau mot de passe en cas d'oubli.
"""
import hashlib
import hmac
import math
import secrets
from datetime import datetime, timedelta

import base
import config
import horloge

ALPHABET_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sans 0/O ni 1/I pour éviter les confusions
ERREUR_CONNEXION = "Identifiant ou mot de passe incorrect."


def _hacher(texte: str, sel: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", texte.encode("utf-8"), bytes.fromhex(sel), 200_000).hex()


def _egal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _normaliser_code(code: str) -> str:
    return "".join(c for c in code.upper() if c.isalnum())


def _compte(identifiant: str = None, uid: int = None):
    with base.ouvrir() as con:
        if uid is not None:
            return con.execute("SELECT * FROM utilisateurs WHERE id = ?", (uid,)).fetchone()
        return con.execute("SELECT * FROM utilisateurs WHERE identifiant = ?", (identifiant.strip(),)).fetchone()


def _controler_mot_de_passe(mot_de_passe: str, confirmation: str):
    if len(mot_de_passe) < config.LONGUEUR_MIN_MDP:
        return f"Le mot de passe doit contenir au moins {config.LONGUEUR_MIN_MDP} caractères."
    if mot_de_passe != confirmation:
        return "Les deux mots de passe ne sont pas identiques."
    return None


def _blocage(compte, maintenant: datetime):
    """Message si le compte est bloqué, sinon None."""
    if compte["bloque_jusqua"]:
        fin_blocage = datetime.fromisoformat(compte["bloque_jusqua"])
        if fin_blocage > maintenant:
            minutes = math.ceil((fin_blocage - maintenant).total_seconds() / 60)
            return f"Compte bloqué : réessayez dans {minutes} min."
    return None


def _compter_echec(compte, maintenant: datetime, message: str) -> str:
    """Essais + 1 ; blocage de 15 minutes au 5e essai raté."""
    essais = compte["essais"] + 1
    with base.ouvrir() as con:
        if essais >= config.MAX_ESSAIS:
            fin = (maintenant + timedelta(minutes=config.DUREE_BLOCAGE_MIN)).isoformat()
            con.execute("UPDATE utilisateurs SET essais = 0, bloque_jusqua = ? WHERE id = ?", (fin, compte["id"]))
            return f"Compte bloqué {config.DUREE_BLOCAGE_MIN} minutes après {config.MAX_ESSAIS} essais ratés."
        con.execute("UPDATE utilisateurs SET essais = ? WHERE id = ?", (essais, compte["id"]))
    return message


def identifiant(uid: int) -> str:
    compte = _compte(uid=uid)
    return compte["identifiant"] if compte else ""


def creer_compte(identifiant_: str, mot_de_passe: str, confirmation: str):
    """Crée un compte avec un portefeuille neuf. Renvoie (ok, message, uid)."""
    identifiant_ = identifiant_.strip()
    if not 3 <= len(identifiant_) <= 30:
        return False, "L'identifiant doit contenir entre 3 et 30 caractères.", None
    if _compte(identifiant_) is not None:
        return False, "Cet identifiant est déjà utilisé : choisissez-en un autre.", None
    erreur = _controler_mot_de_passe(mot_de_passe, confirmation)
    if erreur:
        return False, erreur, None
    sel = secrets.token_hex(16)
    with base.ouvrir() as con:
        uid = con.execute(
            "INSERT INTO utilisateurs (identifiant, sel, hash, cree_le) VALUES (?, ?, ?, ?)",
            (identifiant_, sel, _hacher(mot_de_passe, sel), horloge.maintenant().isoformat(timespec="seconds")),
        ).lastrowid
    return True, "Compte créé.", uid


def nouveau_code_recuperation(uid: int) -> str:
    """Crée un code de récupération (affiché une seule fois) et enregistre sa version hachée."""
    brut = "".join(secrets.choice(ALPHABET_CODE) for _ in range(12))
    with base.ouvrir() as con:
        sel = con.execute("SELECT sel FROM utilisateurs WHERE id = ?", (uid,)).fetchone()["sel"]
        con.execute("UPDATE utilisateurs SET code_hash = ? WHERE id = ?", (_hacher(brut, sel), uid))
    return f"{brut[:4]}-{brut[4:8]}-{brut[8:]}"


def verifier(identifiant_: str, mot_de_passe: str, maintenant: datetime = None):
    """Vérifie les identifiants (logigramme 2). Renvoie (ok, message, uid)."""
    maintenant = maintenant or horloge.maintenant()
    compte = _compte(identifiant_)
    if compte is None:
        return False, ERREUR_CONNEXION, None
    bloque = _blocage(compte, maintenant)
    if bloque:
        return False, bloque, None
    if _egal(_hacher(mot_de_passe, compte["sel"]), compte["hash"]):
        with base.ouvrir() as con:
            con.execute("UPDATE utilisateurs SET essais = 0, bloque_jusqua = NULL WHERE id = ?", (compte["id"],))
        return True, "Connexion réussie.", compte["id"]
    return False, _compter_echec(compte, maintenant, ERREUR_CONNEXION), None


def mot_de_passe_oublie(identifiant_: str, code: str, mot_de_passe: str, confirmation: str,
                        maintenant: datetime = None):
    """
    Nouveau mot de passe grâce au code de récupération. Le portefeuille est conservé.
    Le code ne sert qu'une fois. Renvoie (ok, message, uid).
    """
    maintenant = maintenant or horloge.maintenant()
    compte = _compte(identifiant_)
    if compte is None or not compte["code_hash"]:
        return False, "Identifiant ou code de récupération incorrect.", None
    bloque = _blocage(compte, maintenant)
    if bloque:
        return False, bloque, None
    if not _egal(_hacher(_normaliser_code(code), compte["sel"]), compte["code_hash"]):
        return False, _compter_echec(compte, maintenant, "Identifiant ou code de récupération incorrect."), None
    erreur = _controler_mot_de_passe(mot_de_passe, confirmation)
    if erreur:
        return False, erreur, None
    with base.ouvrir() as con:
        con.execute("UPDATE utilisateurs SET hash = ?, code_hash = NULL, essais = 0, bloque_jusqua = NULL "
                    "WHERE id = ?", (_hacher(mot_de_passe, compte["sel"]), compte["id"]))
    fermer_autres_sessions(compte["id"])        # un nouveau mot de passe ferme les sessions ouvertes ailleurs
    return True, "Mot de passe modifié : votre portefeuille est conservé.", compte["id"]


def changer_mot_de_passe(uid: int, actuel: str, mot_de_passe: str, confirmation: str, jeton: str = None):
    """
    Change le mot de passe d'un compte connecté. Renvoie (ok, message).
    Les sessions ouvertes sur d'autres appareils sont fermées ; `jeton` est celle qu'on garde.
    """
    compte = _compte(uid=uid)
    if not _egal(_hacher(actuel, compte["sel"]), compte["hash"]):
        return False, "Mot de passe actuel incorrect."
    erreur = _controler_mot_de_passe(mot_de_passe, confirmation)
    if erreur:
        return False, erreur
    with base.ouvrir() as con:
        con.execute("UPDATE utilisateurs SET hash = ? WHERE id = ?", (_hacher(mot_de_passe, compte["sel"]), uid))
    fermer_autres_sessions(uid, sauf=jeton)
    return True, "Mot de passe modifié."


def verifier_mot_de_passe(uid: int, mot_de_passe: str) -> bool:
    compte = _compte(uid=uid)
    return compte is not None and _egal(_hacher(mot_de_passe, compte["sel"]), compte["hash"])


# =====================================================================
# Sessions : survivre au rafraîchissement de la page
# =====================================================================
# Streamlit perd `st.session_state` à chaque rechargement (F5) : sans jeton, la personne est
# déconnectée dès qu'elle actualise la page. Le jeton est tiré au hasard (32 octets), transmis dans
# l'adresse de la page et enregistré uniquement sous forme hachée. Il ne remplace pas le mot de
# passe : il ne permet pas de le changer (`changer_mot_de_passe` redemande l'actuel).
#
# Limite assumée : le jeton apparaît dans la barre d'adresse, donc dans l'historique du navigateur
# et sur un écran partagé. La fenêtre est volontairement courte (durée d'inactivité du compte) et
# la session est supprimée à la déconnexion comme au changement de mot de passe.
DUREE_SESSION_MIN = config.INACTIVITE_MIN


def _hacher_jeton(jeton: str) -> str:
    """SHA-256 suffit : le jeton est déjà 256 bits tirés au hasard, il n'y a rien à deviner."""
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def _fin_de_session(maintenant: datetime = None) -> str:
    return ((maintenant or horloge.maintenant()) + timedelta(minutes=DUREE_SESSION_MIN)).isoformat()


def ouvrir_session(uid: int, maintenant: datetime = None) -> str:
    """Crée une session pour ce compte et renvoie le jeton à placer dans l'adresse de la page."""
    purger_sessions(maintenant)
    jeton = secrets.token_urlsafe(32)
    with base.ouvrir() as con:
        con.execute("INSERT INTO sessions (jeton_hash, utilisateur_id, expire_le) VALUES (?, ?, ?)",
                    (_hacher_jeton(jeton), uid, _fin_de_session(maintenant)))
    return jeton


def session_valide(jeton: str, maintenant: datetime = None):
    """
    Renvoie l'identifiant interne du compte si le jeton correspond à une session encore valable,
    sinon None. Chaque reprise repousse l'expiration (fenêtre glissante, comme l'inactivité).
    """
    if not jeton:
        return None
    maintenant = maintenant or horloge.maintenant()
    with base.ouvrir() as con:
        ligne = con.execute("SELECT utilisateur_id, expire_le FROM sessions WHERE jeton_hash = ?",
                            (_hacher_jeton(jeton),)).fetchone()
        if ligne is None:
            return None
        if datetime.fromisoformat(ligne["expire_le"]) <= maintenant:
            con.execute("DELETE FROM sessions WHERE jeton_hash = ?", (_hacher_jeton(jeton),))
            return None
        con.execute("UPDATE sessions SET expire_le = ? WHERE jeton_hash = ?",
                    (_fin_de_session(maintenant), _hacher_jeton(jeton)))
        return ligne["utilisateur_id"]


def prolonger_session(jeton: str, maintenant: datetime = None) -> None:
    """Repousse l'expiration pendant que la personne travaille sans recharger la page."""
    if jeton:
        with base.ouvrir() as con:
            con.execute("UPDATE sessions SET expire_le = ? WHERE jeton_hash = ?",
                        (_fin_de_session(maintenant), _hacher_jeton(jeton)))


def fermer_session(jeton: str) -> None:
    """Déconnexion : la session ne peut plus servir, même si l'adresse a été copiée."""
    if jeton:
        with base.ouvrir() as con:
            con.execute("DELETE FROM sessions WHERE jeton_hash = ?", (_hacher_jeton(jeton),))


def fermer_autres_sessions(uid: int, sauf: str = None) -> None:
    """Ferme les sessions ouvertes ailleurs (changement ou réinitialisation du mot de passe)."""
    with base.ouvrir() as con:
        if sauf:
            con.execute("DELETE FROM sessions WHERE utilisateur_id = ? AND jeton_hash != ?",
                        (uid, _hacher_jeton(sauf)))
        else:
            con.execute("DELETE FROM sessions WHERE utilisateur_id = ?", (uid,))


def purger_sessions(maintenant: datetime = None) -> None:
    """Supprime les sessions expirées (appelé à chaque connexion, pour borner la table)."""
    with base.ouvrir() as con:
        con.execute("DELETE FROM sessions WHERE expire_le <= ?",
                    ((maintenant or horloge.maintenant()).isoformat(),))
