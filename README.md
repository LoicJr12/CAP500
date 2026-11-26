# CAP 500 – Interface de gestion de 500 000 €

Application Python / Streamlit conforme au dossier de conception et au dossier de spécification.

## 1. Installation (une seule fois)

1. Installer **Python 3.11 ou plus** (python.org). Sous Windows : cocher **« Add Python to PATH »**.
2. Installer **VS Code** et l'extension **Python** (VS Code la propose à l'ouverture du dossier).
3. Dans VS Code : *Fichier → Ouvrir le dossier…* → choisir `portefeuille`.
4. Ouvrir un terminal (*Terminal → Nouveau terminal*) et taper :

```bash
python -m venv .venv
```

5. Activer l'environnement :
   - Windows : `.venv\Scripts\activate`
   - Mac / Linux : `source .venv/bin/activate`
6. Installer les bibliothèques :

```bash
pip install -r requirements.txt
```

7. En bas à droite de VS Code, choisir l'interpréteur Python **`.venv`**.

## 2. Lancer l'application

- **Avec VS Code** : touche **F5** → « Lancer l'application (Streamlit) ».
- **Ou dans le terminal** : `streamlit run app.py`

La page s'ouvre sur `http://localhost:8501`. Sur la page d'accueil, deux choix : **Se connecter** ou **Créer un compte**.
Chaque personne a son propre compte et son propre portefeuille de 500 000 €. Pour un nouveau compte :
1. choisissez un identifiant et un mot de passe (onglet « Créer un compte ») ;
2. **notez ou téléchargez le code de récupération** affiché (il sert si vous oubliez le mot de passe) ;
3. répondez aux 4 questions du profil de risque ;
4. répartissez le capital (bouton « Proposer selon mon profil » ou saisie à la main).

Les montants se saisissent comme en France : `12 500,50`.
Pour arrêter : **Ctrl + C** dans le terminal.

## 2 bis. Ouvrir l'application depuis un autre ordinateur

**Même Wi-Fi (le plus simple, pour une démo en classe)**
1. Lancez l'application sur votre PC.
2. Dans le terminal, repérez la ligne `Network URL: http://192.168.x.x:8501`.
3. Sur l'autre ordinateur, tapez cette adresse dans le navigateur.
4. Si Windows demande l'autorisation du pare-feu pour Python, acceptez (réseau privé).

Votre PC doit rester allumé avec l'application lancée.

**Par internet (Streamlit Community Cloud, gratuit)**
1. Créez un compte sur github.com et déposez-y le dossier (sans `data/portefeuille.db` ni `.venv`).
2. Allez sur share.streamlit.io, connectez-vous avec GitHub, cliquez « Create app ».
3. Choisissez le dépôt, le fichier `app.py`, puis « Deploy ». Vous obtenez une adresse en `.streamlit.app`.

Attention : en ligne, la base de données **peut être effacée** quand l'application redémarre
(mise en veille après environ 12 h sans visite, ou mise à jour du code).
Téléchargez donc régulièrement la sauvegarde (*Réglages → Sauvegarde*)
et restaurez-la si besoin. Les téléchargements de cours depuis Yahoo Finance peuvent aussi être
refusés depuis les serveurs en ligne : dans ce cas, importez les cours en CSV.

## 3. Lancer les tests

- **Avec VS Code** : icône « fiole » (Tests) dans la barre de gauche, ou F5 → « Lancer les tests ».
- **Ou dans le terminal** : `pytest tests -v`

Les tests utilisent une base temporaire et des cours fictifs : ils ne touchent jamais à vos données.

## 4. Organisation des fichiers

| Fichier | Rôle | Algorithme |
|---|---|---|
| `app.py` | Point d'entrée : connexion, menu, enchaînement des écrans | Logigramme 1 |
| `ecrans.py` | Les écrans de l'interface | — |
| `style.py` | Couleurs, logo, mise en page CAP 500 | — |
| `profil.py` | Questionnaire du profil de risque | — |
| `textes.py` | Textes en langage simple : guide, lexique, explications des conseils | — |
| `config.py` | Paramètres : actions, capital, seuils, sécurité | — |
| `base.py` | Base de données SQLite (un portefeuille par compte), réglages, sauvegardes | — |
| `donnees.py` | Cours (yfinance), comptes, analystes, actualités | Logigramme 4 |
| `graphique.py` | Moyennes mobiles, RSI, MACD, Bollinger | A1 |
| `infos.py` | Objectif des analystes et actualités | A2 |
| `financier.py` | Les 5 ratios financiers | A3 |
| `hasard.py` | Simulation Monte-Carlo | A4 |
| `moteur.py` | Score, recommandation, phrase d'argumentation | A5, A6 |
| `portefeuille.py` | Ordres, valeur, vente automatique à −10 %, répartition | A7, A8, logigramme 3 |
| `auth.py` | Création de compte, connexion, blocage après 5 essais, mot de passe oublié | Logigramme 2 |
| `affichage.py` | Format des montants et des dates en français | — |
| `modele.py` | Structures de données communes | — |
| `assets/` | Logo (remplacez par `assets/logo.png` pour utiliser le vôtre) | — |
| `.streamlit/config.toml` | Thème de couleurs | — |
| `tests/` | Tests automatiques | — |

## 4 bis. Profils de risque

| Règle | Prudent | Équilibré | Dynamique |
|---|---|---|---|
| Achat conseillé si score ≥ | 0,8 | 0,5 | 0,3 |
| Vente conseillée si score ≤ | −0,3 | −0,5 | −0,7 |
| Part max. d'une action | 25 % | 40 % | 60 % |
| Liquidités minimum | 20 % | 10 % | 0 % |
| Risque accepté sur 1 semaine (A4) | 6 % | 10 % | 14 % |
| Alerte | −4 % | −8 % | −8 % |
| Vente automatique de tout | −6 % | −10 % | −10 % |

La perte maximale ne dépasse jamais 10 % (exigence du client). Les valeurs se modifient dans `config.py`.

## 5. Données à tenir à jour

| Fichier | Quoi | Quand |
|---|---|---|
| `data/comptes.csv` | CA, résultat net, BPA, dette nette, EBITDA, dividende | Une fois par an. **Les valeurs fournies sont approximatives : à vérifier dans les rapports annuels.** |
| `data/analystes.csv` | Objectif de cours des analystes | Chaque semaine (ABC Bourse, rubrique Analyses) |

Les cours et les actualités sont téléchargés automatiquement. Sans internet, l'application utilise les derniers cours
enregistrés ; on peut aussi importer un fichier CSV dans *Historique et réglages → Données*.

Une base de l'ancienne version (un seul compte) est convertie automatiquement : le compte et son portefeuille sont conservés.
La base de données (`data/portefeuille.db`) est créée automatiquement et sauvegardée chaque jour dans `data/sauvegardes/`
(7 dernières copies).
