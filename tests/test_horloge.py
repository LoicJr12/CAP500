"""Tests de l'heure de référence (Bourse de Paris)."""
import os
import subprocess
import sys
from datetime import datetime

import horloge
from conftest import RACINE


def test_heure_de_paris_independante_du_fuseau_du_serveur():
    """Un serveur en UTC (Streamlit Cloud) doit donner la même journée de bourse qu'à Paris."""
    code = ("import horloge;"
            "print(horloge.maintenant().isoformat());"
            "print(horloge.aujourdhui().isoformat())")
    sorties = {}
    for fuseau in ["UTC", "Europe/Paris", "Pacific/Honolulu"]:
        env = {**os.environ, "TZ": fuseau, "PYTHONPATH": str(RACINE)}
        resultat = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                  env=env, cwd=str(RACINE))
        assert resultat.returncode == 0, resultat.stderr
        sorties[fuseau] = resultat.stdout.split()
    # Même minute et même jour quel que soit le fuseau du serveur
    minutes = {s[0][:16] for s in sorties.values()}
    jours = {s[1] for s in sorties.values()}
    assert len(jours) == 1, sorties
    assert len(minutes) == 1, sorties


def test_maintenant_est_naif_et_coherent_avec_aujourdhui():
    """Les dates restent naïves : la base compare des chaînes ISO entre elles sans TypeError."""
    m = horloge.maintenant()
    assert m.tzinfo is None
    assert m.date() == horloge.aujourdhui()
    assert m - datetime(2026, 1, 1) > datetime(2026, 1, 2) - datetime(2026, 1, 1)


def test_conversion_d_une_date_utc_des_actualites():
    """Un flux d'actualités publie en UTC : 10h00 UTC en hiver devient 11h00 à Paris."""
    assert horloge.de_utc(2026, 1, 15, 10, 0, 0) == datetime(2026, 1, 15, 11, 0)
    # En été, le décalage est de deux heures
    assert horloge.de_utc(2026, 7, 15, 10, 0, 0) == datetime(2026, 7, 15, 12, 0)
