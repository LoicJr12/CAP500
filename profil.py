"""
Profil de risque du client : 4 questions, 0 à 2 points chacune.
0 à 2 points : Prudent · 3 à 5 : Équilibré · 6 à 8 : Dynamique
"""
QUESTIONS = [
    ("Votre portefeuille perd 6 % en un mois. Que faites-vous ?", [
        ("Je vends pour arrêter les pertes", 0),
        ("J'attends que le marché remonte", 1),
        ("J'en profite pour acheter à bas prix", 2),
    ]),
    ("Quel est votre objectif sur un an ?", [
        ("Ne pas perdre d'argent", 0),
        ("Une croissance régulière", 1),
        ("Le gain le plus élevé possible", 2),
    ]),
    ("Quelle est votre expérience de la bourse ?", [
        ("Aucune", 0),
        ("Quelques opérations", 1),
        ("J'investis régulièrement", 2),
    ]),
    ("Quelle baisse passagère acceptez-vous sans vendre ?", [
        ("Moins de 5 %", 0),
        ("Entre 5 et 8 %", 1),
        ("Jusqu'à 10 %", 2),
    ]),
]


def calculer_profil(points: list) -> str:
    total = sum(points)
    if total <= 2:
        return "Prudent"
    if total <= 5:
        return "Équilibré"
    return "Dynamique"
