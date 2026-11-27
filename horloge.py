"""
Heure de référence de l'application : celle de la Bourse de Paris.

Tous les modules passent par ces fonctions au lieu de `datetime.now()` ou `date.today()`.
Sans cela, un serveur réglé sur un autre fuseau (Streamlit Community Cloud est à l'heure UTC)
daterait de la veille un ordre passé à 00h30 à Paris, ferait basculer la journée de bourse à la
mauvaise heure et décalerait la fenêtre des actualités de la semaine.

Le fuseau est fixé à Paris, et non pris sur le navigateur : la référence est le marché, pas le
lieu où se trouve la personne. Deux élèves dans deux fuseaux différents voient la même séance.

Les valeurs renvoyées sont « naïves » (sans fuseau attaché) mais calculées à l'heure de Paris :
la base de données enregistre ainsi des chaînes ISO comparables entre elles, sans mélange de
dates naïves et de dates avec fuseau (qui lèverait une TypeError à la comparaison).
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

FUSEAU = ZoneInfo("Europe/Paris")


def maintenant() -> datetime:
    """Date et heure à Paris, sans fuseau attaché (passage à l'heure d'été géré)."""
    return datetime.now(FUSEAU).replace(tzinfo=None)


def aujourdhui() -> date:
    """Jour en cours à Paris."""
    return maintenant().date()


def de_utc(annee, mois, jour, heure=0, minute=0, seconde=0) -> datetime:
    """Convertit une date UTC (celle des flux d'actualités) en heure de Paris."""
    utc = datetime(annee, mois, jour, heure, minute, seconde, tzinfo=timezone.utc)
    return utc.astimezone(FUSEAU).replace(tzinfo=None)
