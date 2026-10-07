"""
scraper_gputracker.py
---------------------
GPUTracker.eu — LA source de référence prix neuf : 117 magasins
européens agrégés (Amazon FR/DE, LDLC, Materiel.net, Cybertek,
GrosBill, RueDuCommerce, TopBiz, Mindfactory, Proshop, alternate,
pccomponentes...). HTML statique vérifié.

Deux modes d'accès :
  - GPU : une URL propre par chipset (facet), la plus fiable :
      /fr/search/category/1/cartes-graphiques/facet/2/chipset-graphique/nvidia-rtx-3070
  - Autres composants : la recherche texte de la catégorie :
      /fr/search/category/2/processeurs?searchTerm=ryzen%205%205600

Structure d'une offre dans le HTML (vérifiée) :
  <a href=".../si-click/1/OFFERID/slug">TITRE magasin.tld PRIX € En stock
  Dernière mise à jour: ...</a> puis un lien "Détails de l'offre" vers
  /fr/offer/OFFERID/slug. On parse les blocs autour de /fr/offer/.
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

BASE_URL = "https://www.gputracker.eu"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9",
    # cookie de préférence : offres livrables en France
    "Cookie": "globalPreferredLocation=fr",
}

# (?=[^a-z]|$) au lieu de \b final : sur GPUTracker le prix est souvent
# collé au domaine ("grosbill.com425 €"), un chiffre doit clore le match.
_SHOP_RE = re.compile(
    r"\b([a-z0-9\-]+\.(?:com|fr|de|es|it|at|dk|fi|pl|nl|be|lu|co\.uk|eu))(?=[^a-z]|$)")
_PRIX_RE = re.compile(r"(\d[\d\s.,]{0,9})\s*€")


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
    brut = m.group(1).replace(" ", "").replace("\u202f", "")
    # "1.234,56" -> "1234.56" ; "425" -> "425"
    if "," in brut:
        brut = brut.replace(".", "").replace(",", ".")
    try:
        return float(brut)
    except ValueError:
        return None


def _extraire_offre(texte_bloc, offer_id):
    """À partir du texte d'un bloc d'offre, construit le dict annonce."""
    prix = _parse_prix(texte_bloc)
    if prix is None:
        return None
    m_shop = _SHOP_RE.search(texte_bloc)
    magasin = m_shop.group(1) if m_shop else "?"
    en_stock = "pas en stock" not in texte_bloc.lower()
    # titre = texte avant le nom du magasin
    titre = texte_bloc.split(magasin)[0].strip() if m_shop else texte_bloc
    titre = re.sub(r"\s+", " ", titre).strip(" -|")
    return {
        "id": f"gpt_{offer_id}",
        "titre": titre[:180] or "(sans titre)",
        "prix": prix,
        "url": f"{BASE_URL}/fr/offer/{offer_id}",
        "magasin": magasin,
        "en_stock": en_stock,
    }


def _parser_bs4(html):
    soup = BeautifulSoup(html, "html.parser")
    offres = {}
    for a in soup.select('a[href*="/si-click/"]'):
        href = a.get("href", "")
        m = re.search(r"/si-click/\d+/(\d+)/", href)
        if not m:
            continue
        offre = _extraire_offre(a.get_text(" ", strip=True), m.group(1))
        if offre:
            offres[offre["id"]] = offre
    return list(offres.values())


def _parser_regex(html):
    offres = {}
    for m in re.finditer(
            r'<a[^>]+href="[^"]*/si-click/\d+/(?P<id>\d+)/[^"]*"[^>]*>(?P<body>.*?)</a>',
            html, re.DOTALL):
        body = re.sub(r"<[^>]+>", " ", m.group("body"))
        body = re.sub(r"\s+", " ", body).strip()
        offre = _extraire_offre(body, m.group("id"))
        if offre:
            offres[offre["id"]] = offre
    return list(offres.values())


def _fetch(session, url):
    """Retourne (offres, code_erreur)."""
    try:
        r = session.get(url, timeout=20)
    except requests.RequestException as e:
        print(f"[{maintenant()}] GPUTracker erreur réseau : {e}")
        return [], "erreur"
    if r.status_code in (403, 429):
        return [], "403"
    if r.status_code != 200:
        return [], "erreur"
    parseur = _parser_bs4 if _BS4 else _parser_regex
    return parseur(r.text), None


# ====================================================================
# COLLECTE PAR CATÉGORIE (contrat commun : (listings, bloque))
# ====================================================================

def _collecter_gpu(session, matcher):
    """GPU : une page par chipset (URLs facet vérifiées)."""
    vues = {}
    bloque = False
    for modele, facet in config.GPUTRACKER_GPU_FACETS.items():
        url = (f"{BASE_URL}/fr/search/category/1/cartes-graphiques"
               f"/facet/2/chipset-graphique/{facet}")
        offres, erreur = _fetch(session, url)
        if erreur == "403":
            bloque = True
            continue
        for o in offres:
            if o["id"] in vues or not o["en_stock"]:
                continue
            o["modele"] = modele  # le facet garantit le modèle : pas d'ambiguïté
            vues[o["id"]] = o
        time.sleep(1.5)
    return list(vues.values()), bloque


def _collecter_texte(session, cat_id, matcher):
    """Autres composants : recherche texte dans la catégorie GPUTracker."""
    mapping = {
        "cpu_amd": "cpu", "cpu_intel": "cpu", "ram": "ram",
        "stockage": "ssd", "alimentation": "alimentation",
        "cm_amd": "carte_mere", "cm_intel": "carte_mere",
    }
    cle = mapping.get(cat_id)
    if not cle:
        return [], False
    cat_num, cat_slug = config.GPUTRACKER_CATEGORIES[cle]

    vues = {}
    bloque = False
    termes = config.COMPOSANTS[cat_id]["search_terms"][:6]
    for terme in termes:
        url = (f"{BASE_URL}/fr/search/category/{cat_num}/{cat_slug}"
               f"?searchTerm={quote_plus(terme)}")
        offres, erreur = _fetch(session, url)
        if erreur == "403":
            bloque = True
            continue
        for o in offres:
            if o["id"] in vues or not o["en_stock"]:
                continue
            if not matcher(o["titre"]):
                continue
            o["modele"] = filters.identifier_modele(cat_id, o["titre"])
            vues[o["id"]] = o
        time.sleep(1.5)
    return list(vues.values()), bloque


def collecter_categorie(cat_id, session=None):
    """
    Prix NEUF pour une catégorie. Chaque offre porte le nom du magasin
    réel (amazon.fr, ldlc.com...) comme plateforme, pour que le
    dashboard montre la vraie répartition par marchand.
    """
    if session is None:
        session = creer_session()
    matcher = filters.get_matcher(config.COMPOSANTS[cat_id]["matcher"])

    if cat_id == "gpu":
        offres, bloque = _collecter_gpu(session, matcher)
    elif cat_id == "ventirad":
        return [], False   # pas de catégorie ventirad sur GPUTracker
    else:
        offres, bloque = _collecter_texte(session, cat_id, matcher)

    listings = []
    for o in offres:
        listings.append({
            "id": o["id"],
            "titre": o["titre"],
            "prix": o["prix"],
            "url": o["url"],
            "photo_url": "", "etat": "Neuf", "score_vendeur": None,
            "plateforme": o["magasin"],
            "source": "GPUTracker",
            "lot_type": "normal", "lot_quantite": 1,
            "modele": o.get("modele"),
            "horodatage": maintenant(),
        })
    return listings, bloque
