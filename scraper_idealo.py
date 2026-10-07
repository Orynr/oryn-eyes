"""
scraper_idealo.py
-----------------
Idealo.fr — comparateur neuf en backup/croisement de GPUTracker.
HTML vérifié accessible. On passe par la recherche générale :

  https://www.idealo.fr/mvc/resultlist.php?q=rtx+3070   (redirige)
  ou plus simplement https://www.idealo.fr/prechcat.html?q=rtx+3070

Le HTML des listes produits contient des blocs avec le nom du produit
et "à partir de N €" (offre la moins chère agrégée). C'est exactement
la référence de prix neuf qu'on veut : le prix plancher du marché.

Chaque produit Idealo devient une "offre" avec plateforme "Idealo
(min marché)" — c'est un agrégat, pas un marchand unique.
"""

import re
import time
from datetime import datetime
from urllib.parse import quote_plus

import requests

import config
import filters

try:
    from bs4 import BeautifulSoup
    _BS4 = True
except ImportError:
    _BS4 = False

BASE_URL = "https://www.idealo.fr"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

_PRIX_RE = re.compile(r"(?:à\s*partir\s*de\s*)?(\d[\d\s\u202f.,]{0,9})\s*€")


def maintenant():
    return datetime.now().isoformat(timespec="seconds")


def creer_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _parse_prix(texte):
    m = re.search(r"à\s*partir\s*de\s*(\d[\d\s\u202f.,]{0,9})\s*€", texte or "")
    if not m:
        m = _PRIX_RE.search(texte or "")
    if not m:
        return None
    brut = m.group(1).replace(" ", "").replace("\u202f", "")
    if "," in brut:
        brut = brut.replace(".", "").replace(",", ".")
    try:
        return float(brut)
    except ValueError:
        return None


def _parser(html):
    """
    Extrait (titre, prix, url) des blocs produits. Idealo lie chaque
    produit vers /prix/ID/slug.html : on parse autour de ces liens.
    """
    produits = {}
    if _BS4:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select('a[href*="/prix/"]'):
            href = a.get("href", "")
            m = re.search(r"/prix/(\d+)/", href)
            if not m:
                continue
            # remonte au conteneur du produit pour capter le prix
            conteneur = a
            for _ in range(4):
                if conteneur.parent is None:
                    break
                conteneur = conteneur.parent
                if _parse_prix(conteneur.get_text(" ", strip=True)):
                    break
            texte = conteneur.get_text(" ", strip=True)
            prix = _parse_prix(texte)
            titre = a.get_text(" ", strip=True)
            if prix and titre and m.group(1) not in produits:
                produits[m.group(1)] = {
                    "id": f"ide_{m.group(1)}",
                    "titre": titre[:180],
                    "prix": prix,
                    "url": href if href.startswith("http") else BASE_URL + href,
                }
    else:
        for m in re.finditer(
                r'href="(?P<href>[^"]*/prix/(?P<id>\d+)/[^"]*)"[^>]*>(?P<titre>[^<]{5,180})<',
                html):
            pid = m.group("id")
            if pid in produits:
                continue
            fenetre = html[m.start():m.start() + 2500]
            prix = _parse_prix(re.sub(r"<[^>]+>", " ", fenetre))
            if prix:
                href = m.group("href")
                produits[pid] = {
                    "id": f"ide_{pid}",
                    "titre": m.group("titre").strip(),
                    "prix": prix,
                    "url": href if href.startswith("http") else BASE_URL + href,
                }
    return list(produits.values())


def rechercher(session, terme):
    url = f"{BASE_URL}/prechcat.html?q={quote_plus(terme)}"
    try:
        r = session.get(url, timeout=20, allow_redirects=True)
    except requests.RequestException as e:
        print(f"[{maintenant()}] Idealo erreur réseau : {e}")
        return [], "erreur"
    if r.status_code in (403, 429):
        return [], "403"
    if r.status_code != 200:
        return [], "erreur"
    return _parser(r.text), None


def collecter_categorie(cat_id, session=None):
    """Contrat commun (listings, bloque). Plateforme = "Idealo (min marché)"."""
    if session is None:
        session = creer_session()
    cat = config.COMPOSANTS[cat_id]
    matcher = filters.get_matcher(cat["matcher"])

    vues = {}
    bloque = False
    for terme in cat["search_terms"][:6]:
        produits, erreur = rechercher(session, terme)
        if erreur == "403":
            bloque = True
            continue
        for p in produits:
            if p["id"] in vues:
                continue
            if not matcher(p["titre"]):
                continue
            p.update({
                "photo_url": "", "etat": "Neuf", "score_vendeur": None,
                "plateforme": "Idealo (min marché)",
                "source": "Idealo",
                "lot_type": "normal", "lot_quantite": 1,
                "modele": filters.identifier_modele(cat_id, p["titre"]),
                "horodatage": maintenant(),
            })
            vues[p["id"]] = p
        time.sleep(2)
    return list(vues.values()), bloque
