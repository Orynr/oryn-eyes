"""
scraper_ebay.py
----------------
Utilise l'API officielle eBay Browse (pas de scraping, pas de risque
de blocage). Nécessite un compte développeur gratuit sur
developer.ebay.com et de renseigner EBAY_CLIENT_ID / EBAY_CLIENT_SECRET
dans config.py.

IMPORTANT — honnêteté sur ce qui est vérifié : cette API n'est pas
joignable depuis l'environnement où ce code a été écrit (pas d'accès
réseau à api.ebay.com dans ce sandbox), donc ce module n'a pas pu être
testé en conditions réelles. La structure (OAuth client-credentials +
endpoint /buy/browse/v1/item_summary/search) suit la documentation
officielle stable d'eBay, mais la première exécution chez toi sera la
vraie validation — exactement comme pour Vinted au départ.

Tant que EBAY_CLIENT_ID/SECRET sont vides dans config.py, ce module se
désactive proprement : il renvoie une liste vide sans planter le reste
du programme.
"""

import requests
import time
from datetime import datetime

import config
import filters

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

_token_cache = {"valeur": None, "expire_a": 0}


def maintenant():
    return datetime.now().isoformat(timespec="seconds")


def est_configure():
    return bool(config.EBAY_CLIENT_ID and config.EBAY_CLIENT_SECRET)


def _obtenir_token():
    """Récupère (et met en cache) un token OAuth client-credentials."""
    if _token_cache["valeur"] and time.time() < _token_cache["expire_a"]:
        return _token_cache["valeur"]

    try:
        r = requests.post(
            TOKEN_URL,
            auth=(config.EBAY_CLIENT_ID, config.EBAY_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"[{maintenant()}] eBay : échec obtention token ({e})")
        return None

    _token_cache["valeur"] = data.get("access_token")
    _token_cache["expire_a"] = time.time() + data.get("expires_in", 7000) - 60
    return _token_cache["valeur"]


def rechercher(terme, limite=50):
    """Une requête de recherche eBay. Retourne (items, erreur)."""
    token = _obtenir_token()
    if not token:
        return [], "auth"

    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": config.EBAY_MARKETPLACE,
    }
    params = {"q": terme, "limit": limite}

    try:
        r = requests.get(SEARCH_URL, headers=headers, params=params, timeout=15)
    except requests.RequestException as e:
        print(f"[{maintenant()}] eBay : erreur réseau sur '{terme}' ({e})")
        return [], "erreur"

    if r.status_code == 401:
        _token_cache["valeur"] = None  # token expiré/invalide, on le regénérera
        return [], "auth"
    if r.status_code != 200:
        print(f"[{maintenant()}] eBay '{terme}' -> HTTP {r.status_code}")
        return [], "erreur"

    try:
        return r.json().get("itemSummaries", []), None
    except ValueError:
        return [], "erreur"


def _extraire(item):
    try:
        prix = float(item["price"]["value"])
    except (KeyError, TypeError, ValueError):
        return None

    return {
        "id": item.get("itemId"),
        "titre": item.get("title", "(titre indisponible)"),
        "prix": prix,
        "url": item.get("itemWebUrl", ""),
        "photo_url": (item.get("image") or {}).get("imageUrl", ""),
        "etat": item.get("condition", ""),
        "score_vendeur": None,  # nécessite un appel supplémentaire à l'API vendeur
        "plateforme": "eBay",
    }


def collecter_categorie(categorie_id, session=None):
    """
    Même interface que scraper_vinted.collecter_categorie() pour que
    main.py puisse traiter les deux plateformes de façon identique.
    Si eBay n'est pas configuré, renvoie ([], False) sans erreur.
    """
    if not est_configure():
        return [], False

    cat = config.COMPOSANTS[categorie_id]
    matcher = filters.get_matcher(cat["matcher"])

    vues = {}
    bloque = False

    for terme in cat["search_terms"]:
        items, erreur = rechercher(terme)
        if erreur in ("auth", "erreur"):
            bloque = bloque or (erreur == "auth")
            continue

        for item in items:
            listing = _extraire(item)
            if listing is None or listing["id"] in vues:
                continue
            if not matcher(listing["titre"]):
                continue

            lot = filters.detecter_lot(listing["titre"], categorie_id)
            if lot["type"] == "lot_parasite":
                continue

            listing["lot_type"] = lot["type"]
            listing["lot_quantite"] = lot["quantite"]
            listing["modele"] = filters.identifier_modele(categorie_id, listing["titre"])
            listing["horodatage"] = maintenant()
            vues[listing["id"]] = listing

        time.sleep(0.5)

    return list(vues.values()), bloque
