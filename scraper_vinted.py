"""
scraper_vinted.py
------------------
Version généralisée du script Vinted d'origine (validé et testé sur
Ryzen 5 3600). Au lieu d'une seule recherche fixe, il boucle sur
toutes les catégories définies dans config.py, applique le bon
matcher (filters.py) et la détection de lots à chaque résultat.

L'appel réseau réel (session.get vers vinted.fr) est la seule partie
qui n'a pas pu être testée dans cet environnement — vinted.fr n'est
pas joignable depuis le sandbox où ce code a été écrit. La logique de
parsing/filtrage autour, elle, est validée par test_filters_analysis.py.
"""

import requests
import time
from datetime import datetime

import config
import filters

BASE_URL = "https://www.vinted.fr"
API_URL = f"{BASE_URL}/api/v2/catalog/items"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": f"{BASE_URL}/catalog",
}


def maintenant():
    return datetime.now().isoformat(timespec="seconds")


def creer_session():
    """Session avec cookies initiaux, comme un navigateur qui visite la page d'accueil."""
    session = requests.Session()
    session.headers.update(HEADERS)
    session.get(BASE_URL, timeout=15)
    return session


def rechercher(session, terme, par_page=50):
    """
    Une requête de recherche Vinted. Retourne (items, code_erreur).
    code_erreur est None si tout va bien, sinon "403" ou "erreur".
    """
    params = {
        "search_text": terme,
        "order": "newest_first",
        "per_page": par_page,
        "currency": "EUR",
    }
    try:
        r = session.get(API_URL, params=params, timeout=15)
    except requests.RequestException as e:
        print(f"[{maintenant()}] Erreur réseau sur '{terme}' : {e}")
        return [], "erreur"

    if r.status_code == 403:
        return [], "403"
    if r.status_code != 200:
        print(f"[{maintenant()}] '{terme}' -> HTTP {r.status_code}")
        return [], "erreur"

    try:
        return r.json().get("items", []), None
    except ValueError:
        return [], "erreur"


def _extraire(item):
    """Normalise un item brut de l'API en dict propre."""
    prix_info = item.get("price", {})
    prix = prix_info.get("amount") if isinstance(prix_info, dict) else prix_info
    try:
        prix = float(prix)
    except (TypeError, ValueError):
        return None

    photo = item.get("photo") or {}
    photo_url = photo.get("url", "") if isinstance(photo, dict) else ""
    url = item.get("url") or f"{BASE_URL}/items/{item.get('id')}"

    user = item.get("user") or {}
    score = user.get("feedback_reputation")  # peut être None selon la réponse API
    if score is not None:
        try:
            score = round(float(score) * 5, 1)  # l'API renvoie parfois un ratio 0-1
        except (TypeError, ValueError):
            score = None

    return {
        "id": item.get("id"),
        "titre": item.get("title", "(titre indisponible)"),
        "prix": prix,
        "url": url,
        "photo_url": photo_url,
        "etat": item.get("status", ""),
        "score_vendeur": score,
        "plateforme": "Vinted",
    }


def collecter_categorie(categorie_id, session):
    """
    Lance toutes les recherches configurées pour une catégorie, filtre
    avec le bon matcher, détecte les lots, et renvoie une liste
    d'annonces propres (dédoublonnées par id).

    Retourne (listings, bloque) où bloque=True si au moins une
    recherche a été bloquée (403).
    """
    cat = config.COMPOSANTS[categorie_id]
    matcher = filters.get_matcher(cat["matcher"])

    vues = {}
    bloque = False

    for terme in cat["search_terms"]:
        items, erreur = rechercher(session, terme)
        if erreur == "403":
            bloque = True
            continue

        for item in items:
            listing = _extraire(item)
            if listing is None or listing["id"] in vues:
                continue
            if not matcher(listing["titre"]):
                continue

            lot = filters.detecter_lot(listing["titre"], categorie_id)
            if lot["type"] == "lot_parasite":
                continue  # prix inutilisable, on exclut des stats

            listing["lot_type"] = lot["type"]
            listing["lot_quantite"] = lot["quantite"]
            listing["modele"] = filters.identifier_modele(categorie_id, listing["titre"])
            listing["horodatage"] = maintenant()
            vues[listing["id"]] = listing

        time.sleep(1)  # rythme poli entre deux recherches de la même catégorie

    return list(vues.values()), bloque


# ====================================================================
# PC GAMER — pour l'onglet Vente PC (mêmes règles que Leboncoin)
# ====================================================================

import pc_analyzer


def collecter_pc(session):
    """
    Annonces de PC gamer complets sur Vinted. Retourne
    (annonces_qualifiees, bloque). Vinted ne fournit ni la description
    complète ni la région dans la liste : la qualification se fait sur
    le titre seul, la région est vide (le donut IDF s'appuie sur
    Leboncoin qui, lui, donne la localisation).
    """
    vues = {}
    bloque = False

    for terme in config.PC_SEARCH_TERMS:
        items, erreur = rechercher(session, terme, par_page=96)
        if erreur == "403":
            bloque = True
            continue

        for item in items:
            listing = _extraire(item)
            if listing is None or listing["id"] in vues:
                continue
            listing["id"] = f"vin_{listing['id']}"
            if not pc_analyzer.est_annonce_pc(listing["titre"]):
                continue

            quali = pc_analyzer.qualifier_pc(listing["titre"])
            if not quali["qualifie"]:
                continue

            listing.update(quali)
            listing["description"] = ""
            listing["region"] = ""
            listing["livraison"] = "Livraison"   # Vinted = envoi intégré par défaut
            listing["horodatage"] = maintenant()
            vues[listing["id"]] = listing

        time.sleep(1)

    return list(vues.values()), bloque
