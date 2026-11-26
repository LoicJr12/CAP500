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
            (identifiant_, sel, _hacher(mot_de_passe, sel), datetime.now().isoformat(timespec="seconds")),
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
    maintenant = maintenant or datetime.now()
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
    maintenant = maintenant or datetime.now()
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
    return True, "Mot de passe modifié : votre portefeuille est conservé.", compte["id"]


def changer_mot_de_passe(uid: int, actuel: str, mot_de_passe: str, confirmation: str):
    """Change le mot de passe d'un compte connecté. Renvoie (ok, message)."""
    compte = _compte(uid=uid)
    if not _egal(_hacher(actuel, compte["sel"]), compte["hash"]):
        return False, "Mot de passe actuel incorrect."
    erreur = _controler_mot_de_passe(mot_de_passe, confirmation)
    if erreur:
        return False, erreur
    with base.ouvrir() as con:
        con.execute("UPDATE utilisateurs SET hash = ? WHERE id = ?", (_hacher(mot_de_passe, compte["sel"]), uid))
    return True, "Mot de passe modifié."


def verifier_mot_de_passe(uid: int, mot_de_passe: str) -> bool:
    compte = _compte(uid=uid)
    return compte is not None and _egal(_hacher(mot_de_passe, compte["sel"]), compte["hash"])
