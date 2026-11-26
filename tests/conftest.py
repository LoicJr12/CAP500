"""Préparation commune aux tests : une base de données temporaire et des cours fictifs."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import base    # noqa: E402
import config  # noqa: E402
import donnees  # noqa: E402


@pytest.fixture(autouse=True)
def base_temporaire(tmp_path, monkeypatch):
    """Chaque test utilise sa propre base vide : la vraie base n'est jamais touchée."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "DOSSIER_SAUVEGARDES", tmp_path / "sauvegardes")
    base.initialiser()


@pytest.fixture
def uid():
    """Un compte de test avec son portefeuille neuf de 500 000 €."""
    import auth
    ok, _, numero = auth.creer_compte("client", "MotDePasse2026", "MotDePasse2026")
    assert ok
    return numero


def serie_cours(n=260, depart=100.0, tendance=0.0005, volatilite=0.015, graine=1) -> pd.DataFrame:
    """Fabrique des cours fictifs (uniquement pour les tests)."""
    tirage = np.random.default_rng(graine)
    cloture = depart * np.exp(np.cumsum(tendance + volatilite * tirage.standard_normal(n)))
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    return pd.DataFrame({
        "ouverture": cloture * 0.998, "haut": cloture * 1.01, "bas": cloture * 0.99,
        "cloture": cloture, "volume": 1_000_000.0,
    }, index=dates)


def enregistrer(code: str, df: pd.DataFrame) -> None:
    donnees.enregistrer_cours([
        (jour.strftime("%Y-%m-%d"), code, l.ouverture, l.haut, l.bas, l.cloture, l.volume)
        for jour, l in zip(df.index, df.itertuples())
    ])


@pytest.fixture
def cours_fictifs():
    """Enregistre des cours fictifs pour les 5 actions et le CAC 40."""
    departs = {"RMS.PA": 1300, "AI.PA": 188, "TTE.PA": 80, "DSY.PA": 25, "CAP.PA": 117, config.INDICE: 8000}
    cours = {}
    for i, (code, depart) in enumerate(departs.items()):
        cours[code] = serie_cours(depart=depart, graine=i + 1)
        enregistrer(code, cours[code])
    return cours
