# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Langue du projet

Tout est en français : identifiants, docstrings, commentaires, textes d'interface, messages d'erreur.
Garder cette convention (ex. `passer_ordre`, `reglages`, `cours`, `liquidites`) ; ne pas renommer en anglais.
L'interface est écrite pour une personne qui ne connaît rien à la bourse : textes courts, sans jargon.

## Commandes

Python 3.11+ requis (le dépôt n'embarque pas de venv).

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt

streamlit run app.py          # lance l'appli sur http://localhost:8501
pytest tests -v               # toute la suite (76 tests)
pytest tests/test_securite.py -v                              # un fichier
pytest tests/test_portefeuille.py::test_vente_automatique -v  # un seul test
pytest tests/test_interface.py -k repartition                 # par motif
```

VS Code : F5 → « Lancer l'application (Streamlit) » ou « Lancer les tests » (voir `.vscode/launch.json`).
Pas de linter ni de CI configurés dans le dépôt.

## Architecture

Streamlit mono-page + SQLite, sans framework ni ORM. Modules plats à la racine, un module = une
responsabilité, communication par fonctions au niveau module (pas de classes de service).

### Chaîne de dépendances

```
app.py  (orchestration, logigramme 1)
  └─ ecrans.py        tous les écrans + cache Streamlit (seul module qui appelle st.*, hors style.py)
       ├─ moteur.py   A5/A6 : score pondéré + phrase d'argumentation
       │    └─ graphique.py (A1) · infos.py (A2) · financier.py (A3) · hasard.py (A4)
       ├─ portefeuille.py  A7 ordres · A8 protection perte · répartition · historique
       ├─ auth.py     comptes, connexion, blocage (logigramme 2)
       ├─ donnees.py  yfinance, CSV, Google Actualités (logigramme 4)
       └─ base.py     SQLite, réglages, sauvegardes, import/export
style.py · textes.py · affichage.py · modele.py · horloge.py · config.py  = feuilles, sans dépendance métier
```

`config.py` est la source unique des paramètres (5 actions, capital de 500 000 €, profils de risque,
seuils de sécurité). Changer une règle métier = modifier `config.py`, pas le code appelant.

### Le pipeline d'analyse

Les 4 outils renvoient chacun `(note ∈ [−2, +2], arguments)` où chaque `Argument` porte son texte en
français, sa contribution et son outil d'origine (`modele.Argument`). `moteur.calculer_score` pondère
les notes (0,40 / 0,25 / 0,20 / 0,15 par défaut), `recommander` applique les seuils du profil
(« Vendre » seulement si l'action est détenue, règle RG9), `construire_phrase` reprend les 3 arguments
les plus lourds pour expliquer le conseil. Ajouter un outil d'analyse = nouveau module renvoyant
`(note, arguments)` + une clé dans `CLES_POIDS` + un poids dans `config.REGLAGES_DEFAUT`.

`moteur.raisons` est la source unique du classement des arguments : la phrase d'argumentation (A6),
la raison courte affichée à côté de chaque pastille (`ecrans.raison_courte`) et les récapitulatifs
de confirmation s'en servent tous, pour que l'explication corresponde toujours au conseil montré.
Même exigence de cohérence côté répartition : `portefeuille.repartition_conseillee` ne propose que
les entreprises dont le conseil est « Acheter » (score ≥ `seuil_achat`), donc la proposition peut
être vide — ne pas « réparer » cela en élargissant le filtre sans revoir le discours affiché.

### Modèle de données et isolation des comptes

Tout est dans `data/portefeuille.db`. Les tables **par compte** sont scopées par le couple
`(utilisateur_id, portefeuille)` : `utilisateurs.portefeuille` est un numéro de génération incrémenté
à chaque remise à zéro ou restauration, ce qui archive l'ancien portefeuille au lieu de le supprimer.
Toute requête métier passe par `base.portefeuille_courant(uid)`.

Les tables `cours` et `actualites` sont **globales et partagées par tous les comptes** (pas de
`utilisateur_id`) : un import CSV de prix change la valorisation de tout le monde. L'import est donc
réservé au compte principal (`base.est_administrateur`, le plus petit `id`).

`base.connexion()` ouvre en WAL avec `foreign_keys = ON` et une attente de `config.ATTENTE_BASE_S` :
plusieurs personnes peuvent lire pendant qu'une autre écrit. La conversion d'une ancienne base
renomme et supprime des tables : elle passe par `ouvrir(contraintes=False)`.

Deux triggers SQLite interdisent `UPDATE`/`DELETE` sur `ordres` (traçabilité). Un ordre ne se corrige
pas : on ouvre un nouveau portefeuille. L'état financier est donc toujours **recalculé** depuis les
ordres (`positions`, `liquidites` = `CAPITAL` + somme des mouvements) — ne jamais introduire de
colonne « solde » dénormalisée.

Accès DB uniquement via `with base.ouvrir() as con:` (commit + close). `base.initialiser()` est
idempotent et convertit au passage une base de l'ancienne version mono-compte.

### Réglages en couches

`base.lire_reglages(uid)` empile, dans cet ordre : `config.REGLAGES_DEFAUT` → `config.PROFILS[profil]`
→ valeurs stockées en base pour ce compte. Choisir un profil (`base.choisir_profil`) supprime les
seuils réglés à la main pour que ceux du profil reprennent la main. Lire les réglages par cette
fonction, jamais la table `reglages` directement.

### Cache Streamlit

Deux caches dans `ecrans.py`, tous deux `ttl=3600` :
- `actualiser_donnees(jour)` — téléchargements réseau, clé = la date du jour ;
- `calculer_analyses(reglages_json, jeton)` — clé = les réglages sérialisés + l'heure du dernier
  rafraîchissement, donc toute modification de réglage invalide naturellement les analyses.

Ces caches sont **globaux au serveur**, pas par utilisateur. Après toute écriture qui change les
calculs (ordre, réglage, import), appeler `calculer_analyses.clear()` ; `tout_recalculer()` vide les
deux. La simulation Monte-Carlo est semée sur la date (`graine = AAAAMMJJ + i`) pour rester stable sur
la journée — indispensable aux tests.

### Heure de référence

Aucun module n'appelle `datetime.now()` ni `date.today()` : tout passe par `horloge.maintenant()` et
`horloge.aujourdhui()`, fixés sur Europe/Paris, parce que la référence est la Bourse de Paris et que
le serveur peut être ailleurs (Streamlit Cloud est en UTC). Les valeurs sont **naïves mais calculées
à Paris** : la base compare des chaînes ISO entre elles, sans mélange naïf / aware qui lèverait une
`TypeError`. `horloge.de_utc` convertit les dates des flux d'actualités. `tzdata` est requis sous
Windows. Garder cette règle pour tout nouveau code.

### Sessions et rafraîchissement de page

Streamlit vide `st.session_state` à chaque rechargement, donc un F5 déconnectait la personne. Un
jeton (`secrets.token_urlsafe(32)`) est placé dans l'adresse sous la clé `ecrans.CLE_JETON` et
enregistré **haché** dans la table `sessions` ; `ecrans.reprendre_session()` le relit au début de
`app.py` avant tout rendu. Fenêtre glissante de `config.INACTIVITE_MIN`, prolongée en base au plus
une fois toutes les `config.PROLONGATION_SESSION_MIN` minutes pour ne pas écrire à chaque clic.
`auth.fermer_session` à la déconnexion, `auth.fermer_autres_sessions` au changement de mot de passe.
Limite assumée et documentée dans `auth.py` : le jeton est visible dans l'URL.

### Conventions d'interface

- Navigation par `st.session_state["page"]` + `ecrans.aller_a` ; `PAGES`/`ICONES` en tête de `ecrans.py`.
  « Investir mon capital » disparaît du menu une fois le capital investi (`pages_du_menu`).
- Messages inter-reruns via `ecrans.flash(type, texte)` puis `afficher_flash()` au prochain rendu.
- Actions destructrices ou financières : toujours un état `*_en_attente` en session + écran de
  confirmation (`preparer_ordre`/`confirmer_ordre`, `repartition_en_attente`, saisie de « RECOMMENCER »).
- Tout nombre affiché passe par `affichage.py` (format français : `12 500,50 €`, espaces insécables,
  signe moins typographique) ; toute saisie numérique par `ecrans.champ_nombre` → `affichage.lire_nombre`
  (accepte virgule et espaces). Ne pas utiliser `st.number_input`.
- Le CSS et les composants HTML vivent dans `style.py`. Tout `unsafe_allow_html=True` recevant une
  donnée non maîtrisée (identifiant, titre d'actualité, lien) doit passer par `style.echapper`.
- `deconnecter()` vide entièrement `st.session_state`.

### Effets de bord au rendu

Afficher une page écrit en base : `ecran_accueil` appelle `enregistrer_historique` (un point par jour)
et `app.py` appelle `portefeuille.controler_perte` à chaque rerun, ce qui peut déclencher la vente
automatique (A8) et poser des ordres. En tenir compte avant de déplacer ces appels.

## Tests

`tests/conftest.py` monkeypatche `config.DB_PATH` et `config.DOSSIER_SAUVEGARDES` vers `tmp_path`
(fixture `base_temporaire`, autouse) : la vraie base n'est jamais touchée. Fixtures utiles : `uid`
(compte « client » / `MotDePasse2026`), `cours_fictifs` (séries déterministes pour les 5 actions + CAC 40).
`tests/test_interface.py` pilote l'appli réelle avec `streamlit.testing.v1.AppTest` et neutralise les
téléchargements par monkeypatch — aucun test ne touche le réseau. Un nouveau module de calcul doit
rester testable sans réseau et sans Streamlit.

## Données à tenir à jour

`data/comptes.csv` (comptes annuels, `;` et décimale `,`, lignes `#` ignorées) et
`data/analystes.csv` (objectifs de cours). Ils alimentent A3 et A2 ; valeurs approximatives à vérifier
dans les rapports annuels, la colonne `source` indique la provenance de chaque ligne.
Un exercice peut être renseigné par morceaux : `financier._dernieres_valeurs` reprend, pour chaque
donnée vide, la dernière valeur connue (sinon une seule case vide supprimerait un ratio), et
`ecrans.etat_comptes` affiche dans *Réglages → Données* l'exercice le plus récent et les données
manquantes. Un `dette_ebitda` peut donc croiser deux exercices : c'est assumé et signalé à l'écran. Les cours et actualités se téléchargent seuls, avec repli sur les derniers
cours connus et import CSV manuel (`donnees.importer_csv_cours`) si le réseau refuse.

## Correspondance algorithmes ↔ code

A1 `graphique.note_graphique` · A2 `infos.note_infos` · A3 `financier.note_financiere` ·
A4 `hasard.simuler`/`note_hasard` · A5 `moteur.recommander` · A6 `moteur.construire_phrase` ·
A7 `portefeuille.passer_ordre` · A8 `portefeuille.controler_perte`.
Logigramme 1 `app.py` · 2 `auth.py` + `ecrans.ecran_connexion` · 3 `portefeuille.repartir` ·
4 `donnees` + `ecrans.actualiser_donnees`. Les références RG/A/logigramme viennent des dossiers de
conception et de spécification : les conserver dans les docstrings.
