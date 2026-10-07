"""
scraper_leboncoin.py
--------------------
Leboncoin via son API interne, identifiée ensemble dans les DevTools :

  POST https://api.leboncoin.fr/finder/search
  payload {"filters": {"enums": {"ad_type": ["offer"]},
                        "keywords": {"text": "rtx 3070"}},
           "limit": 50, "sort_by": "time"}

Protégé par DataDome (comme Vinted). Approche identique et honnête :
headers de navigateur + cookies récupérés en visitant la page
d'accueil, ralentissement automatique en cas de blocage, aucun
contournement. Peut fonctionner comme Vinted, ou se faire bloquer —
c'est le point "à tester en réel" convenu.

Deux usages :
  - collecter_categorie(cat_id) : composants (mêmes matchers que Vinted)
  - collecter_pc()              : annonces de PC gamer complets, avec
                                  région (donut IDF) et livraison.
"""

import time
from datetime import datetime

import requests

import config
import filters
import pc_analyzer

BASE_URL = "https://www.leboncoin.fr"
API_URL = "https://api.leboncoin.fr/finder/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
}


def maintenant():
    return datetime.now().isoformat(timespec="seconds")


def creer_session():
    """Visite la home pour obtenir les cookies (dont DataDome) avant l'API."""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(BASE_URL, timeout=15,
                    headers={"Accept": "text/html,application/xhtml+xml"})
    except requests.RequestException:
        pass
    return session


def rechercher(session, terme, limite=50):
    """
    Une recherche via finder/search. Retourne (ads, code_erreur).
    code_erreur : None | "403" | "erreur".
    """
    payload = {
        "filters": {
            "enums": {"ad_type": ["offer"]},
            "keywords": {"text": terme},
        },
        "limit": limite,
        "sort_by": "time",
    }
    try:
        r = session.post(API_URL, json=payload, timeout=15)
    except requests.RequestException as e:
        print(f"[{maintenant()}] Leboncoin erreur réseau '{terme}' : {e}")
        return [], "erreur"

    if r.status_code in (403, 429):
        return [], "403"
    if r.status_code != 200:
        print(f"[{maintenant()}] Leboncoin '{terme}' -> HTTP {r.status_code}")
        return [], "erreur"

    try:
        return r.json().get("ads", []) or [], None
    except ValueError:
        return [], "erreur"


def _prix(ad):
    """Le prix LBC est une liste [x] ou un nombre selon les versions d'API."""
    p = ad.get("price")
    if isinstance(p, list) and p:
        p = p[0]
    if isinstance(p, dict):
        p = p.get("value") or p.get("amount")
    try:
        return float(p)
    except (TypeError, ValueError):
        return None


def _livraison(ad):
    """
    "Livraison" / "Main propre" / "?" — codé défensivement car le champ
    varie selon les versions de l'API. On teste toutes les formes connues.
    """
    opts = ad.get("options") or {}
    if isinstance(opts, dict):
        if opts.get("shipping") or opts.get("has_shipping"):
            return "Livraison"
    for attr in ad.get("attributes") or []:
        key = str(attr.get("key", "")).lower()
        val = str(attr.get("value", "")).lower()
        if "shipp" in key or "livraison" in key or "delivery" in key:
            if val in ("true", "1", "oui", "yes") or "colis" in val or "envoi" in val:
                return "Livraison"
            if val in ("false", "0", "non", "no"):
                return "Main propre"
    if ad.get("shippable") is True:
        return "Livraison"
    if ad.get("shippable") is False:
        return "Main propre"
    return "?"


def _region(ad):
    loc = ad.get("location") or {}
    return loc.get("region_name") or loc.get("region") or ""


def _extraire(ad):
    prix = _prix(ad)
    if prix is None:
        return None
    return {
        "id": f"lbc_{ad.get('list_id') or ad.get('id')}",
        "titre": ad.get("subject") or ad.get("title") or "(sans titre)",
        "description": ad.get("body") or "",
        "prix": prix,
        "url": ad.get("url") or f"{BASE_URL}/ad/{ad.get('list_id')}",
        "photo_url": "",
        "etat": "",
        "score_vendeur": None,
        "plateforme": "Leboncoin",
        "region": _region(ad),
        "livraison": _livraison(ad),
    }


# ====================================================================
# COMPOSANTS — même contrat que scraper_vinted.collecter_categorie
# ====================================================================

def collecter_categorie(cat_id, session):
    cat = config.COMPOSANTS[cat_id]
    matcher = filters.get_matcher(cat["matcher"])

    vues = {}
    bloque = False

    for terme in cat["search_terms"]:
        ads, erreur = rechercher(session, terme)
        if erreur == "403":
            bloque = True
            continue

        for ad in ads:
            listing = _extraire(ad)
            if listing is None or listing["id"] in vues:
                continue
            if not matcher(listing["titre"]):
                continue
            # exclut les PC complets remontés dans une recherche composant
            if pc_analyzer.est_annonce_pc(listing["titre"], listing["description"]):
                continue

            lot = filters.detecter_lot(listing["titre"], cat_id)
            if lot["type"] == "lot_parasite":
                continue

            listing["lot_type"] = lot["type"]
            listing["lot_quantite"] = lot["quantite"]
            listing["modele"] = filters.identifier_modele(cat_id, listing["titre"])
            listing["horodatage"] = maintenant()
            vues[listing["id"]] = listing

        time.sleep(2)  # rythme poli, DataDome est plus sensible que Vinted

    return list(vues.values()), bloque


# ====================================================================
# PC GAMER — pour l'onglet Vente PC
# ====================================================================

def collecter_pc(session):
    """
    Annonces de PC gamer complets. Retourne (annonces_qualifiees, bloque).
    Chaque annonce contient gpu_marque/gpu_modele/cpu_marque/cpu_modele
    (pc_analyzer), la région et la livraison.
    """
    vues = {}
    bloque = False

    for terme in config.PC_SEARCH_TERMS:
        ads, erreur = rechercher(session, terme, limite=100)
        if erreur == "403":
            bloque = True
            continue

        for ad in ads:
            listing = _extraire(ad)
            if listing is None or listing["id"] in vues:
                continue
            if not pc_analyzer.est_annonce_pc(listing["titre"], listing["description"]):
                continue

            quali = pc_analyzer.qualifier_pc(listing["titre"], listing["description"])
            if not quali["qualifie"]:
                continue

            listing.update(quali)
            listing["horodatage"] = maintenant()
            vues[listing["id"]] = listing

        time.sleep(2)

    return list(vues.values()), bloque
