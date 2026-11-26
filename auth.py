"""
Connexion sécurisée (logigramme 2) :
- mot de passe de 8 caractères minimum, enregistré haché (jamais en clair) ;
- compte bloqué 15 minutes après 5 essais ratés ;
- code de récupération pour recréer le compte en cas d'oubli.
"""
import hashlib
import hmac
import math
import secrets
from datetime import datetime, timedelta

import base
import config

ALPHABET_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sans 0/O ni 1/I pour éviter les confusions


def _hacher(texte: str, sel: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", texte.encode("utf-8"), bytes.fromhex(sel), 200_000).hex()


def _egal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _normaliser_code(code: str) -> str:
    return "".join(c for c in code.upper() if c.isalnum())


def _lire_compte():
    with base.ouvrir() as con:
        return con.execute("SELECT * FROM utilisateur WHERE id = 1").fetchone()


def _controler_saisie(identifiant: str, mot_de_passe: str, confirmation: str):
    if not identifiant:
        return "Saisissez un identifiant."
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
            con.execute("UPDATE utilisateur SET essais = 0, bloque_jusqua = ? WHERE id = 1", (fin,))
            return f"Compte bloqué {config.DUREE_BLOCAGE_MIN} minutes après {config.MAX_ESSAIS} essais ratés."
        con.execute("UPDATE utilisateur SET essais = ? WHERE id = 1", (essais,))
    return message


def compte_existe() -> bool:
    return _lire_compte() is not None


def identifiant_actuel() -> str:
    compte = _lire_compte()
    return compte["identifiant"] if compte else ""


def creer_compte(identifiant: str, mot_de_passe: str, confirmation: str):
    """Crée le compte unique du client. Renvoie (ok, message)."""
    identifiant = identifiant.strip()
    if compte_existe():
        return False, "Un compte existe déjà."
    erreur = _controler_saisie(identifiant, mot_de_passe, confirmation)
    if erreur:
        return False, erreur
    sel = secrets.token_hex(16)
    with base.ouvrir() as con:
        con.execute(
            "INSERT INTO utilisateur (id, identifiant, sel, hash) VALUES (1, ?, ?, ?)",
            (identifiant, sel, _hacher(mot_de_passe, sel)),
        )
    return True, "Compte créé. Vous pouvez maintenant vous connecter."


def nouveau_code_recuperation() -> str:
    """Crée un code de récupération (affiché une seule fois) et enregistre sa version hachée."""
    brut = "".join(secrets.choice(ALPHABET_CODE) for _ in range(12))
    with base.ouvrir() as con:
        sel = con.execute("SELECT sel FROM utilisateur WHERE id = 1").fetchone()["sel"]
        con.execute("UPDATE utilisateur SET code_hash = ? WHERE id = 1", (_hacher(brut, sel),))
    return f"{brut[:4]}-{brut[4:8]}-{brut[8:]}"


def verifier(identifiant: str, mot_de_passe: str, maintenant: datetime = None):
    """Vérifie les identifiants (logigramme 2). Renvoie (ok, message)."""
    maintenant = maintenant or datetime.now()
    compte = _lire_compte()
    if compte is None:
        return False, "Aucun compte n'existe encore."

    bloque = _blocage(compte, maintenant)
    if bloque:
        return False, bloque

    correct = _egal(identifiant.strip(), compte["identifiant"]) and _egal(
        _hacher(mot_de_passe, compte["sel"]), compte["hash"])
    if correct:
        with base.ouvrir() as con:
            con.execute("UPDATE utilisateur SET essais = 0, bloque_jusqua = NULL WHERE id = 1")
        return True, "Connexion réussie."
    return False, _compter_echec(compte, maintenant, "Identifiant ou mot de passe incorrect.")


def recreer_compte(code: str, identifiant: str, mot_de_passe: str, confirmation: str,
                   garder_portefeuille: bool, maintenant: datetime = None):
    """
    Recrée le compte avec le code de récupération (mot de passe oublié ou nouveau départ).
    Une copie de la base est faite avant. Renvoie (ok, message).
    """
    maintenant = maintenant or datetime.now()
    compte = _lire_compte()
    if compte is None:
        return False, "Aucun compte n'existe encore : créez-en un."
    if not compte["code_hash"]:
        return False, ("Ce compte n'a pas de code de récupération. "
                       "Supprimez le fichier data/portefeuille.db pour repartir de zéro.")
    bloque = _blocage(compte, maintenant)
    if bloque:
        return False, bloque
    if not _egal(_hacher(_normaliser_code(code), compte["sel"]), compte["code_hash"]):
        return False, _compter_echec(compte, maintenant, "Code de récupération incorrect.")

    identifiant = identifiant.strip()
    erreur = _controler_saisie(identifiant, mot_de_passe, confirmation)
    if erreur:
        return False, erreur

    base.copie_securite("avant_recreation")
    sel = secrets.token_hex(16)
    with base.ouvrir() as con:
        con.execute(
            "UPDATE utilisateur SET identifiant = ?, sel = ?, hash = ?, code_hash = NULL, "
            "essais = 0, bloque_jusqua = NULL WHERE id = 1",
            (identifiant, sel, _hacher(mot_de_passe, sel)),
        )
    if garder_portefeuille:
        return True, "Compte recréé : votre portefeuille est conservé."
    base.reinitialiser_portefeuille()
    with base.ouvrir() as con:
        con.execute("DELETE FROM reglages")
    return True, "Compte recréé : nouveau portefeuille de 500 000 €."


def changer_identifiants(mot_de_passe_actuel: str, identifiant: str, mot_de_passe: str, confirmation: str):
    """Change l'identifiant et le mot de passe (connecté). Renvoie (ok, message)."""
    compte = _lire_compte()
    if not _egal(_hacher(mot_de_passe_actuel, compte["sel"]), compte["hash"]):
        return False, "Mot de passe actuel incorrect."
    identifiant = identifiant.strip()
    erreur = _controler_saisie(identifiant, mot_de_passe, confirmation)
    if erreur:
        return False, erreur
    with base.ouvrir() as con:
        con.execute("UPDATE utilisateur SET identifiant = ?, hash = ? WHERE id = 1",
                    (identifiant, _hacher(mot_de_passe, compte["sel"])))
    return True, "Identifiant et mot de passe modifiés."
