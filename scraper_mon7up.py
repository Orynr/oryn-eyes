"""
scraper_mon7up.py
-----------------
Mon7up (mon7up.fr) — marketplace française 100 % composants PC
d'occasion entre particuliers. Vérifié accessible : HTML statique,
URLs propres :

  https://www.mon7up.fr/recherche?categorie=carte-graphique&research=RTX+3070

Le HTML des cartes d'annonces contient : lien /annonce/slug-id,
titre, état (Occasion/Neuf), prix "N €", ville. On parse avec
BeautifulSoup, et en secours avec une regex sur les liens /annonce/.
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

BASE_URL = "https://www.mon7up.fr"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# Catégorie Mon7up correspondant à chaque catégorie du projet
CATEGORIES_MON7UP = {
    "cpu_amd": "processeur",
    "cpu_intel": "processeur",
    "gpu": "carte-graphique",
    "ram": "memoire-vive-ram",
    "cm_amd": "carte-mere",
    "cm_intel": "carte-mere",
    "stockage": "stockage-hdd---ssd",
    "alimentation": "alimentation",
    "ventirad": "refroidissement-aio---ventirad",
}

_PRIX_RE = re.compile(r"(\d[\d\s]{0,6})\s*€")


def maintenant():
    return datetime.now().isoformat(timespec="seconds")


def _url_recherche(categorie_mon7up, terme):
    url = f"{BASE_URL}/recherche?categorie={categorie_mon7up}"
    if terme:
        url += f"&research={quote_plus(terme)}"
    return url


def _parse_prix(texte):
    m = _PRIX_RE.search(texte or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(" ", ""))
    except ValueError:
        return None


def _parser_bs4(html):
    """Parse les cartes d'annonces via les liens /annonce/."""
    soup = BeautifulSoup(html, "html.parser")
    annonces = []
    for a in soup.select('a[href*="/annonce/"]'):
        href = a.get("href", "")
        m_id = re.search(r"/annonce/.*?-(\d+)$", href)
        if not m_id:
            continue
        texte = a.get_text(" ", strip=True)
        prix = _parse_prix(texte)
        if prix is None:
            continue
        # titre = texte avant le prix, nettoyé des mentions d'état
        titre = _PRIX_RE.split(texte)[0]
        titre = re.sub(r"\b(Occasion|Neuf|VIP)\b", "", titre).strip(" -|")
        annonces.append({
            "id": f"m7_{m_id.group(1)}",
            "titre": titre or "(sans titre)",
            "prix": prix,
            "url": href if href.startswith("http") else BASE_URL + href,
        })
    return annonces


def _parser_regex(html):
    """Secours sans bs4 : regex sur les blocs <a href="/annonce/...">."""
    annonces = []
    for m in re.finditer(
            r'<a[^>]+href="(?P<href>[^"]*/annonce/[^"]*?-(?P<id>\d+))"[^>]*>(?P<body>.*?)</a>',
            html, re.DOTALL):
        body = re.sub(r"<[^>]+>", " ", m.group("body"))
        body = re.sub(r"\s+", " ", body).strip()
        prix = _parse_prix(body)
        if prix is None:
            continue
        titre = _PRIX_RE.split(body)[0]
        titre = re.sub(r"\b(Occasion|Neuf|VIP)\b", "", titre).strip(" -|")
        href = m.group("href")
        annonces.append({
            "id": f"m7_{m.group('id')}",
            "titre": titre or "(sans titre)",
            "prix": prix,
            "url": href if href.startswith("http") else BASE_URL + href,
        })
    return annonces


def rechercher(session, categorie_mon7up, terme):
    """Retourne (annonces_brutes, code_erreur)."""
    try:
        r = session.get(_url_recherche(categorie_mon7up, terme), timeout=15)
    except requests.RequestException as e:
        print(f"[{maintenant()}] Mon7up erreur réseau : {e}")
        return [], "erreur"
    if r.status_code in (403, 429):
        return [], "403"
    if r.status_code != 200:
        return [], "erreur"
    parseur = _parser_bs4 if _BS4 else _parser_regex
    return parseur(r.text), None


def creer_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def collecter_categorie(cat_id, session=None):
    """Même contrat que les autres scrapers occasion : (listings, bloque)."""
    if session is None:
        session = creer_session()

    cat = config.COMPOSANTS[cat_id]
    categorie_m7 = CATEGORIES_MON7UP.get(cat_id)
    if not categorie_m7:
        return [], False
    matcher = filters.get_matcher(cat["matcher"])

    vues = {}
    bloque = False

    # Une recherche par terme, plus une passe "catégorie entière" pour les
    # petites catégories (le catalogue Mon7up est modeste, on ratisse tout).
    termes = list(cat["search_terms"])[:4] + [""]
    for terme in termes:
        brutes, erreur = rechercher(session, categorie_m7, terme)
        if erreur == "403":
            bloque = True
            continue

        for b in brutes:
            if b["id"] in vues:
                continue
            if not matcher(b["titre"]):
                continue
            lot = filters.detecter_lot(b["titre"], cat_id)
            if lot["type"] == "lot_parasite":
                continue

            b.update({
                "photo_url": "", "etat": "", "score_vendeur": None,
                "plateforme": "Mon7up",
                "lot_type": lot["type"], "lot_quantite": lot["quantite"],
                "modele": filters.identifier_modele(cat_id, b["titre"]),
                "horodatage": maintenant(),
            })
            vues[b["id"]] = b

        time.sleep(1.5)

    return list(vues.values()), bloque
