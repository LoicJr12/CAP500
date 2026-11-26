"""
Textes en langage simple : présentation des entreprises, explications des conseils, guide et lexique.
Tout ce qui est affiché pour aider une personne qui ne connaît pas la bourse est regroupé ici.
"""

SECTEURS = {
    "RMS.PA": "Luxe : sacs, foulards, maroquinerie",
    "AI.PA": "Gaz pour l'industrie et les hôpitaux",
    "TTE.PA": "Pétrole, gaz et électricité",
    "DSY.PA": "Logiciels de conception en 3D",
    "CAP.PA": "Conseil et services informatiques",
}

# Les 4 outils d'analyse : (titre simple, nom technique, question à laquelle l'outil répond)
OUTILS = {
    "graphique": ("Tendance du prix", "Analyse graphique",
                  "Le prix monte-t-il ou baisse-t-il ces dernières semaines ?"),
    "infos": ("Avis des experts et actualités", "Informations",
              "Les spécialistes et les journaux sont-ils optimistes ?"),
    "financier": ("Santé de l'entreprise", "Analyse financière",
                  "L'entreprise gagne-t-elle bien sa vie par rapport aux 4 autres ?"),
    "hasard": ("Risque simulé", "Prise en compte du hasard",
               "Sur 10 000 semaines imaginées, l'action monte-t-elle souvent ?"),
}

SENS_CONSEIL = {
    "Acheter": "Les signaux sont plutôt bons : c'est un moment favorable pour acheter.",
    "Vendre": "Les signaux sont plutôt mauvais : vendre permet de limiter le risque.",
    "Ne rien faire": "Les signaux sont partagés : le plus sage est d'attendre.",
}

PROFILS_SIMPLES = {
    "Prudent": "Vous voulez avant tout ne pas perdre d'argent.",
    "Équilibré": "Vous acceptez un peu de risque pour gagner davantage.",
    "Dynamique": "Vous visez le gain maximum et acceptez les hauts et les bas.",
}


def verdict(note: float) -> str:
    """Traduit une note de −2 à +2 en mots."""
    if note >= 1.5:
        return "Très favorable"
    if note >= 0.3:
        return "Favorable"
    if note > -0.3:
        return "Neutre"
    if note > -1.5:
        return "Défavorable"
    return "Très défavorable"


# Explication simple de chaque argument technique (recherche par mot-clé)
EXPLICATIONS = [
    ("tendance haussière", "Le prix est au-dessus de sa moyenne des dernières semaines : il est en train de monter."),
    ("tendance baissière", "Le prix est en dessous de sa moyenne des dernières semaines : il est en train de baisser."),
    ("survendue", "L'action a beaucoup baissé en peu de temps : elle pourrait remonter."),
    ("surachetée", "L'action a beaucoup monté en peu de temps : elle pourrait redescendre."),
    ("croisement haussier", "Un indicateur de tendance (MACD) vient de repasser à la hausse."),
    ("croisement baissier", "Un indicateur de tendance (MACD) vient de repasser à la baisse."),
    ("Bollinger basse", "Le prix est anormalement bas par rapport à ses variations habituelles."),
    ("Bollinger haute", "Le prix est anormalement haut par rapport à ses variations habituelles."),
    ("objectif des analystes", "Les experts des banques estiment le prix que l'action devrait atteindre."),
    ("actualité", "Articles de presse de la semaine sur l'entreprise."),
    ("chiffre d'affaires", "Le chiffre d'affaires, ce sont les ventes de l'entreprise sur une année."),
    ("marge nette", "Sur 100 € de ventes, ce que l'entreprise garde vraiment comme bénéfice."),
    ("PER", "Le PER compare le prix de l'action aux bénéfices : plus il est bas, moins l'action est chère."),
    ("endettement", "Le poids des dettes de l'entreprise par rapport à ce qu'elle gagne."),
    ("rendement sur 1 an", "Ce qu'a rapporté l'action en un an : hausse du prix + dividendes."),
    ("probabilité de hausse", "Résultat de 10 000 simulations de la semaine prochaine."),
    ("risque de perte", "Dans les 5 % de cas les plus défavorables, la perte pourrait atteindre ce niveau."),
]


def expliquer(argument: str) -> str:
    for mot, explication in EXPLICATIONS:
        if mot.lower() in argument.lower():
            return explication
    return ""


ETAPES = [
    ("Choisissez votre profil", "4 questions pour savoir quel niveau de risque vous convient."),
    ("Investissez vos 500 000 €", "Répartissez l'argent entre les 5 entreprises, ou laissez CAP 500 proposer."),
    ("Suivez et ajustez", "Chaque jour, consultez nos conseils et achetez ou vendez quand vous voulez."),
]

FAQ = [
    ("Est-ce de l'argent réel ?",
     "Non. Les 500 000 € sont virtuels : c'est une simulation pour apprendre à gérer un portefeuille. "
     "Les prix des actions, eux, sont les vrais prix de la Bourse de Paris."),
    ("Comment CAP 500 décide-t-il de ses conseils ?",
     "Pour chaque entreprise, 4 points sont étudiés : la tendance du prix, l'avis des experts et l'actualité, "
     "la santé financière de l'entreprise et une simulation du risque. Chaque point reçoit une note de −2 à +2. "
     "La note globale décide du conseil : acheter, vendre ou attendre."),
    ("Les conseils sont-ils garantis ?",
     "Non. Personne ne peut prévoir la Bourse avec certitude. Les conseils indiquent une tendance ; "
     "c'est toujours vous qui décidez."),
    ("Que se passe-t-il si je perds trop ?",
     "Une alerte s'affiche quand la perte approche de votre limite. Si la limite est atteinte "
     "(10 % au maximum), toutes vos actions sont vendues automatiquement pour vous protéger, "
     "puis les achats sont bloqués."),
    ("Puis-je utiliser CAP 500 à plusieurs ?",
     "Oui. Chaque personne crée son compte et dispose de son propre portefeuille de 500 000 €."),
    ("J'ai oublié mon mot de passe.",
     "Sur la page de connexion, ouvrez « Mot de passe oublié ? » et saisissez le code de récupération "
     "reçu à la création du compte."),
]

LEXIQUE = [
    ("Action", "Une petite part d'une entreprise. Si l'entreprise va bien, la valeur de l'action monte en général."),
    ("Cours", "Le prix d'une action à un moment donné."),
    ("Portefeuille", "L'ensemble de ce que vous possédez : vos actions et votre argent disponible."),
    ("Liquidités", "L'argent disponible, pas encore investi en actions."),
    ("Frais de courtage", "Ce que prend l'intermédiaire à chaque achat ou vente (ici 0,10 % du montant)."),
    ("CAC 40", "L'indice des 40 plus grandes entreprises françaises. Il sert de point de comparaison."),
    ("Dividende", "Une part des bénéfices que l'entreprise verse chaque année à ceux qui ont ses actions."),
    ("Chiffre d'affaires", "Le total des ventes de l'entreprise sur une année."),
    ("Marge nette", "Sur 100 € de ventes, le bénéfice qui reste une fois toutes les dépenses payées."),
    ("PER", "Prix de l'action divisé par le bénéfice par action. Un PER bas veut dire que l'action est peu chère."),
    ("Endettement", "Les dettes de l'entreprise comparées à ce qu'elle gagne chaque année."),
    ("Moyenne mobile", "La moyenne des prix sur les 20 ou 50 derniers jours. Elle lisse les variations."),
    ("RSI", "Un indicateur de 0 à 100. Au-dessus de 70 : l'action a beaucoup monté. Sous 30 : elle a beaucoup baissé."),
    ("MACD", "Un indicateur qui repère les changements de tendance (passage de la baisse à la hausse, et inversement)."),
    ("Bandes de Bollinger", "Une zone autour du prix moyen. Sortir de la zone signale un prix inhabituel."),
    ("Objectif des analystes", "Le prix que les experts des banques s'attendent à voir dans les 12 mois."),
    ("Simulation Monte-Carlo", "On imagine 10 000 semaines possibles à partir des variations passées pour mesurer le risque."),
    ("Profil de risque", "Votre façon d'investir : Prudent, Équilibré ou Dynamique. Il adapte les conseils et les limites."),
    ("Vente automatique", "Si votre perte atteint la limite de votre profil, toutes les actions sont vendues pour vous protéger."),
]
