"""
scraper_pccomponentes.py
------------------------
PC Componentes (pccomponentes.fr) — vérifié accessible. Deux usages :

  - NEUF : référence de prix (produits standards)
  - RECONDITIONNÉ : compte comme OCCASION dans le dashboard (les
    produits portent la mention "Reconditionné" dans le titre)

Recherche : https://www.pccomponentes.fr/search/?query=rtx3070
Le HTML contient des liens produits avec titre + prix "455,21€" +
éventuellement "Reconditionné". On parse ces blocs.
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

BASE_URL = "https://www.pccomponentes.fr"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# Lookbehind : ne pas démarrer au milieu d'un nombre ("GDDR6 649,90€" ne
# doit pas donner "6 649,90"). Milliers PCC = point uniquement ("1.099,00€").
_PRIX_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*€")


def maintenant():
    return datetime.now().isoformat(timespec="seconds")


def creer_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _parse_prix(texte):
    m = _PRIX_RE.search(texte or "")
    if not m:
        return None
    brut = m.group(1).replace(".", "")
    brut = brut.replace(",", ".")
    try:
        return float(brut)
    except ValueError:
        return None


def _slug_id(href):
    """L'URL produit PCC est un slug sans id numérique : on hashe le slug."""
    slug = href.rstrip("/").split("/")[-1][:80]
    return slug or None


def _parser(html):
    produits = {}
    if _BS4:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/search" in href or href.count("/") > 4 or len(href) < 15:
                continue
            texte = a.get_text(" ", strip=True)
            prix = _parse_prix(texte)
            if prix is None or len(texte) < 20:
                continue
            slug = _slug_id(href)
            if not slug or slug in produits:
                continue
            recond = "reconditionn" in texte.lower()
            titre = _PRIX_RE.split(texte)[0].strip()
            titre = re.sub(r"\s+", " ", titre)[:180]
            produits[slug] = {
                "id": f"pcc_{slug}",
                "titre": titre,
                "prix": prix,
                "url": href if href.startswith("http") else BASE_URL + href,
                "reconditionne": recond,
            }
    else:
        for m in re.finditer(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<body>.*?)</a>',
                             html, re.DOTALL):
            body = re.sub(r"<[^>]+>", " ", m.group("body"))
            body = re.sub(r"\s+", " ", body).strip()
            prix = _parse_prix(body)
            if prix is None or len(body) < 20:
                continue
            slug = _slug_id(m.group("href"))
            if not slug or slug in produits:
                continue
            titre = _PRIX_RE.split(body)[0].strip()[:180]
            produits[slug] = {
                "id": f"pcc_{slug}",
                "titre": titre,
                "prix": prix,
                "url": m.group("href") if m.group("href").startswith("http")
                       else BASE_URL + m.group("href"),
                "reconditionne": "reconditionn" in body.lower(),
            }
    return list(produits.values())


def rechercher(session, terme):
    url = f"{BASE_URL}/search/?query={quote_plus(terme)}"
    try:
        r = session.get(url, timeout=20)
    except requests.RequestException as e:
        print(f"[{maintenant()}] PC Componentes erreur réseau : {e}")
        return [], "erreur"
    if r.status_code in (403, 429):
        return [], "403"
    if r.status_code != 200:
        return [], "erreur"
    return _parser(r.text), None


def _collecter(cat_id, session, veut_reconditionne):
    cat = config.COMPOSANTS[cat_id]
    matcher = filters.get_matcher(cat["matcher"])

    vues = {}
    bloque = False
    for terme in cat["search_terms"][:5]:
        produits, erreur = rechercher(session, terme.replace(" ", ""))
        if erreur == "403":
            bloque = True
            continue
        for p in produits:
            if p["id"] in vues:
                continue
            if p["reconditionne"] != veut_reconditionne:
                continue
            if not matcher(p["titre"]):
                continue
            lot = filters.detecter_lot(p["titre"], cat_id)
            if lot["type"] == "lot_parasite":
                continue
            p.update({
                "photo_url": "", "etat": "Reconditionné" if veut_reconditionne else "Neuf",
                "score_vendeur": None,
                "plateforme": "PCC Reconditionné" if veut_reconditionne else "pccomponentes.fr",
                "source": "PC Componentes",
                "lot_type": lot["type"], "lot_quantite": lot["quantite"],
                "modele": filters.identifier_modele(cat_id, p["titre"]),
                "horodatage": maintenant(),
            })
            vues[p["id"]] = p
        time.sleep(1.5)
    return list(vues.values()), bloque


def collecter_categorie_occasion(cat_id, session=None):
    """Produits RECONDITIONNÉS -> flux occasion du dashboard."""
    if session is None:
        session = creer_session()
    return _collecter(cat_id, session, veut_reconditionne=True)


def collecter_categorie_neuf(cat_id, session=None):
    """Produits NEUFS -> référence de prix."""
    if session is None:
        session = creer_session()
    return _collecter(cat_id, session, veut_reconditionne=False)
