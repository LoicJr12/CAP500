"""Tests de l'algorithme A1 (analyse graphique)."""
import pandas as pd

import graphique
from conftest import serie_cours


def test_indicateurs_calcules():
    ind = graphique.indicateurs(serie_cours())
    for colonne in ["MM20", "MM50", "RSI", "MACD", "MACD_signal", "BB_haut", "BB_bas", "support", "resistance"]:
        assert colonne in ind.columns
    rsi = ind["RSI"].dropna()
    assert ((rsi >= 0) & (rsi <= 100)).all()
    assert (ind["BB_haut"].dropna() >= ind["BB_bas"].dropna()).all()


def test_moyenne_mobile_20_jours():
    df = pd.DataFrame({"cloture": [float(i) for i in range(1, 61)]},
                      index=pd.bdate_range("2026-01-01", periods=60))
    ind = graphique.indicateurs(df)
    assert ind["MM20"].iloc[-1] == sum(range(41, 61)) / 20


def test_forte_hausse_donne_tendance_haussiere_et_rsi_eleve():
    df = serie_cours(tendance=0.01, volatilite=0.002)
    note, arguments = graphique.note_graphique(graphique.indicateurs(df))
    textes = " ".join(a.texte for a in arguments)
    assert "tendance haussière" in textes
    assert "surachetée" in textes          # RSI > 70
    assert -2 <= note <= 2


def test_forte_baisse_donne_tendance_baissiere():
    df = serie_cours(tendance=-0.01, volatilite=0.002)
    _, arguments = graphique.note_graphique(graphique.indicateurs(df))
    assert any("tendance baissière" in a.texte for a in arguments)


def test_historique_trop_court():
    note, arguments = graphique.note_graphique(graphique.indicateurs(serie_cours(n=30)))
    assert note == 0 and arguments == []
