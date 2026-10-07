"""
analysis.py
-----------
Tous les calculs statistiques. Aucune de ces fonctions ne fait
d'appel réseau : elles prennent des données déjà collectées et
renvoient des nombres. C'est ce qui les rend testables sans Vinted
(voir test_analysis.py).
"""

from collections import defaultdict
from datetime import datetime, timedelta

import config


# --------------------------------------------------------------------
# STATISTIQUES DE BASE
# --------------------------------------------------------------------

def mediane(valeurs):
    if not valeurs:
        return None
    s = sorted(valeurs)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return round((s[mid - 1] + s[mid]) / 2, 2)


def calculer_stats(prix):
    """min / max / moyenne / médiane / total / nombre d'annonces."""
    if not prix:
        return {"min": None, "max": None, "moyenne": None, "mediane": None,
                "total": 0, "count": 0}
    return {
        "min": min(prix),
        "max": max(prix),
        "moyenne": round(sum(prix) / len(prix), 2),
        "mediane": mediane(prix),
        "total": round(sum(prix), 2),
        "count": len(prix),
    }


def pourcentage_vs_mediane(prix, med):
    """Écart en % entre un prix et la médiane. None si pas de médiane."""
    if not med:
        return None
    return round(((prix - med) / med) * 100, 1)


# --------------------------------------------------------------------
# ALERTES COULEUR
# --------------------------------------------------------------------
# 🔴 rouge  : pct <= SEUIL_ROUGE  (ex. -30% et moins)
# 🟠 orange : SEUIL_ROUGE < pct <= SEUIL_ORANGE
# 🟢 vert   : SEUIL_ORANGE < pct <= 0
# ⚪ gris   : 0 < pct <= SEUIL_MASQUAGE
# masque   : pct > SEUIL_MASQUAGE -> l'annonce ne doit pas être affichée

def palier_alerte(pct):
    if pct is None:
        return "gris"
    if pct > config.SEUIL_MASQUAGE:
        return "masque"
    if pct <= config.SEUIL_ROUGE:
        return "rouge"
    if pct <= config.SEUIL_ORANGE:
        return "orange"
    if pct <= 0:
        return "vert"
    return "gris"


def doit_etre_affiche(pct):
    return palier_alerte(pct) != "masque"


# --------------------------------------------------------------------
# MARGE ESTIMÉE
# --------------------------------------------------------------------

def marge_estimee(med, prix):
    if med is None:
        return None
    return round(med - prix - config.MARGE_FRAIS_ESTIMES, 2)


# --------------------------------------------------------------------
# VALEUR DE MARCHÉ — combien coûterait d'acheter tout le stock dispo
# --------------------------------------------------------------------

def valeur_marche(prix, med):
    """
    Renvoie la somme des prix des annonces :
      - sous_mediane : jusqu'à la médiane incluse
      - sous_seuil   : jusqu'à +SEUIL_MASQUAGE% de la médiane
      - total        : absolument toutes les annonces (même masquées)
    """
    if not prix:
        return {"sous_mediane": 0, "sous_seuil": 0, "total": 0}
    if not med:
        total = round(sum(prix), 2)
        return {"sous_mediane": total, "sous_seuil": total, "total": total}

    plafond = med * (1 + config.SEUIL_MASQUAGE / 100)
    sous_mediane = sum(p for p in prix if p <= med)
    sous_seuil = sum(p for p in prix if p <= plafond)
    total = sum(prix)
    return {
        "sous_mediane": round(sous_mediane, 2),
        "sous_seuil": round(sous_seuil, 2),
        "total": round(total, 2),
    }


# --------------------------------------------------------------------
# BOUGIES JAPONAISES — agrégation quotidienne
# --------------------------------------------------------------------

def ohlc_quotidien(observations):
    """
    observations : liste de dicts {"horodatage": "YYYY-MM-DDTHH:MM:SS", "prix": float}
    Retourne une liste triée par date de dicts :
      {"date": "YYYY-MM-DD", "ouverture":, "cloture":, "haut":, "bas":}
    Une bougie par jour où au moins une observation existe.
    """
    par_jour = defaultdict(list)
    for obs in observations:
        jour = obs["horodatage"][:10]
        par_jour[jour].append(obs)

    bougies = []
    for jour in sorted(par_jour.keys()):
        obs_du_jour = sorted(par_jour[jour], key=lambda o: o["horodatage"])
        prix = [o["prix"] for o in obs_du_jour]
        bougies.append({
            "date": jour,
            "ouverture": prix[0],
            "cloture": prix[-1],
            "haut": max(prix),
            "bas": min(prix),
        })
    return bougies


# --------------------------------------------------------------------
# VITESSE DE ROTATION — temps moyen avant disparition d'une annonce
# --------------------------------------------------------------------

def vitesse_rotation_moyenne(historique):
    """
    historique : liste de dicts {"premiere_vue": iso, "derniere_vue": iso}
    Retourne la durée moyenne en ligne, en heures (None si pas de données).
    """
    durees = []
    for h in historique:
        try:
            d1 = datetime.fromisoformat(h["premiere_vue"])
            d2 = datetime.fromisoformat(h["derniere_vue"])
            durees.append((d2 - d1).total_seconds() / 3600)
        except (KeyError, ValueError, TypeError):
            continue
    if not durees:
        return None
    return round(sum(durees) / len(durees), 1)


# --------------------------------------------------------------------
# DEALS DU MOIS — fréquence des bonnes affaires
# --------------------------------------------------------------------

def deals_du_mois(deals, aujourdhui=None):
    """
    deals : liste de dicts {"date": "YYYY-MM-DD", "pct": float}
    Compte les deals rouges des 30 derniers jours et estime la fréquence.
    """
    if aujourdhui is None:
        aujourdhui = datetime.now()
    il_y_a_30j = aujourdhui - timedelta(days=30)

    rouges = []
    for d in deals:
        try:
            date_deal = datetime.fromisoformat(d["date"])
        except (KeyError, ValueError, TypeError):
            continue
        if date_deal >= il_y_a_30j and palier_alerte(d.get("pct")) == "rouge":
            rouges.append(d)

    count = len(rouges)
    frequence_jours = round(30 / count, 1) if count > 0 else None
    return {"count": count, "frequence_jours": frequence_jours}


# --------------------------------------------------------------------
# PRIX UNITAIRE POUR LES LOTS
# --------------------------------------------------------------------

def prix_unitaire(prix_total, quantite):
    if not quantite or quantite < 1:
        return prix_total
    return round(prix_total / quantite, 2)
