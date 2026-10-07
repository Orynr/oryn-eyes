"""
filters.py
----------
Deux responsabilités :

1. Les "matchers" — une fonction par catégorie qui décide si le titre
   d'une annonce correspond vraiment au composant recherché (et pas à
   un faux positif du moteur de recherche Vinted). Ce sont ces
   fonctions que config.py référence par leur nom.

2. La détection de lots — distinguer un lot "parasite" (CPU + carte
   mère + ventirad vendus ensemble, prix inutilisable) d'un lot "en
   gros" (3x le même composant, prix unitaire calculable et à garder).

Toute cette logique est pure (aucun appel réseau) : elle est donc
testée intégralement dans test_filters.py, sans dépendre de Vinted.
"""

import re

# --------------------------------------------------------------------
# OUTILS COMMUNS
# --------------------------------------------------------------------

def _clean(title):
    return title.lower().strip()


def _extract_numbers(text, pattern):
    """Retourne tous les entiers matchés par `pattern` (1 groupe capturant)."""
    return [int(m) for m in re.findall(pattern, text)]


# --------------------------------------------------------------------
# DÉTECTION DE LOTS
# --------------------------------------------------------------------

# Mots qui signalent un lot EN GROS (même composant, plusieurs exemplaires)
LOT_GROS_PATTERN = re.compile(
    r"\b(lot\s*de\s*(\d+)|(\d+)\s*x\b|x\s*(\d+)\b|(\d+)\s*unit[ée]s?|(\d+)\s*pi[eè]ces?)",
    re.IGNORECASE,
)

# Mots-clés par famille de composant, utilisés pour repérer un lot
# PARASITE : plusieurs familles différentes mentionnées dans le même titre.
FAMILLES_COMPOSANTS = {
    "cpu": [r"\bryzen\b", r"\bcore i[3579]\b", r"\bcpu\b", r"\bprocesseur\b"],
    "carte_mere": [r"\bcarte\s*m[eè]re\b", r"\bmotherboard\b", r"\b[abhxz]\d{3}\b"],
    "ventirad": [r"\bventirad\b", r"\bwatercooling\b", r"\baio\b", r"\bcooler\b"],
    "gpu": [r"\brtx\b", r"\bgtx\b", r"\bcarte\s*graphique\b"],
    "ram": [r"\bddr[34]\b", r"\bbarrette\b"],
    "boitier": [r"\bbo[iî]tier\b", r"\bcase\b"],
    "alimentation": [r"\balimentation\b", r"\bpsu\b"],
    "stockage": [r"\bssd\b", r"\bhdd\b", r"\bdisque\s*dur\b"],
}


def detecter_lot(title, categorie_recherchee):
    """
    Analyse le titre d'une annonce et renvoie un dict :
      {
        "type": "normal" | "lot_gros" | "lot_parasite",
        "quantite": int,          # 1 si "normal"
      }

    - "lot_gros"     : même composant en plusieurs exemplaires -> à garder,
                       le prix unitaire sera calculé par analysis.py
                       (prix_annonce / quantite).
    - "lot_parasite" : plusieurs familles de composants différentes
                       mélangées (ex: CPU + carte mère + ventirad) -> à
                       exclure des statistiques, le prix ne représente
                       rien d'exploitable pour un seul composant.
    """
    t = _clean(title)

    familles_presentes = set()
    for famille, patterns in FAMILLES_COMPOSANTS.items():
        for p in patterns:
            if re.search(p, t):
                familles_presentes.add(famille)
                break

    # Deux familles différentes ou plus (hors la catégorie qu'on cherche
    # elle-même comptée une fois) => lot parasite.
    if len(familles_presentes) >= 2:
        return {"type": "lot_parasite", "quantite": 1}

    # Sinon, cherche une quantité explicite (lot en gros du même composant)
    m = LOT_GROS_PATTERN.search(t)
    if m:
        quantite = next((int(g) for g in m.groups()[1:] if g), None)
        if quantite and quantite >= 2:
            return {"type": "lot_gros", "quantite": quantite}

    return {"type": "normal", "quantite": 1}


# --------------------------------------------------------------------
# MATCHERS PAR CATÉGORIE
# --------------------------------------------------------------------

def match_cpu_amd(title):
    """Ryzen 5 (gen 3000-5000) ou Ryzen 7 (gen 2000-5000)."""
    t = _clean(title)
    m5 = re.search(r"ryzen\s*5\D{0,3}(\d{4})", t)
    if m5:
        gen = int(str(m5.group(1))[0])
        if gen in (3, 4, 5):
            return True
    m7 = re.search(r"ryzen\s*7\D{0,3}(\d{4})", t)
    if m7:
        gen = int(str(m7.group(1))[0])
        if gen in (2, 3, 4, 5):
            return True
    return False


def match_cpu_intel(title):
    """Core i5 / i7 / i9, générations 9 à 14."""
    t = _clean(title)
    for serie in ("5", "7", "9"):
        m = re.search(rf"i{serie}\D{{0,3}}(\d{{4,5}})", t)
        if m:
            num = str(m.group(1))
            # gen 9 = 4 chiffres (9700K), gen 10-14 = 5 chiffres (12700K)
            gen = int(num[:2]) if len(num) == 5 else int(num[0])
            if gen == 9 or 10 <= gen <= 14:
                return True
    return False


def match_gpu(title):
    """RTX 2000 (toutes), RTX 3060-3080, RTX 4060-4070."""
    t = _clean(title)
    for m in re.finditer(r"rtx\D{0,2}(\d{4})", t):
        n = int(m.group(1))
        if 2000 <= n <= 2089:
            return True
        if 3060 <= n <= 3080:
            return True
        if 4060 <= n <= 4070:
            return True
    return False


def match_ram(title):
    """DDR4, capacité par barrette >= 8 Go."""
    t = _clean(title)
    if "ddr3" in t or "ddr5" in t:
        return False
    if "ddr4" not in t:
        return False

    # Cas "2x8go" / "4 x 8 go" -> capacité par barrette = second nombre
    m_kit = re.search(r"(\d+)\s*x\s*(\d+)\s*go", t)
    if m_kit:
        return int(m_kit.group(2)) >= 8

    # Cas capacité simple "16go" -> on suppose 1 barrette de cette capacité
    m_simple = re.search(r"(\d+)\s*go\b", t)
    if m_simple:
        return int(m_simple.group(1)) >= 8

    return False


CHIPSETS_AMD_AM4 = {"a320", "b350", "x370", "b450", "x470", "a520", "b550", "x570"}
CHIPSETS_INTEL = {
    "h310", "b360", "h370", "b365", "z370", "z390",           # LGA1151
    "h410", "b460", "h470", "b560", "h570", "z490", "z590",   # LGA1200
    "h610", "b660", "h670", "b760", "z690", "z790",           # LGA1700
}


def match_cm_amd(title):
    t = _clean(title)
    return any(re.search(rf"\b{c}\b", t) for c in CHIPSETS_AMD_AM4)


def match_cm_intel(title):
    t = _clean(title)
    return any(re.search(rf"\b{c}\b", t) for c in CHIPSETS_INTEL)


def match_stockage(title):
    """SSD NVMe/SATA 256-512Go, HDD 1-2To."""
    t = _clean(title)

    def capacite_go():
        m_to = re.search(r"(\d+(?:[.,]\d+)?)\s*to\b", t)
        if m_to:
            return float(m_to.group(1).replace(",", ".")) * 1000
        m_go = re.search(r"(\d+)\s*go\b", t)
        if m_go:
            return float(m_go.group(1))
        return None

    cap = capacite_go()
    if cap is None:
        return False

    if "nvme" in t or "sata" in t or "ssd" in t:
        return 256 <= cap <= 512
    if "hdd" in t or "disque dur" in t:
        return 1000 <= cap <= 2000
    return False


def match_alimentation(title):
    """550W à 850W."""
    t = _clean(title)
    m = re.search(r"(\d{3,4})\s*w\b", t)
    if m:
        return 550 <= int(m.group(1)) <= 850
    return False


def match_ventirad(title):
    """Pas de contrainte de référence : le terme de recherche suffit déjà."""
    t = _clean(title)
    return "ventirad" in t or "watercooling" in t or "aio" in t


# --------------------------------------------------------------------
# IDENTIFICATION DU MODÈLE PRÉCIS
# --------------------------------------------------------------------
# Utilisé pour remplir la colonne "modèle" de chaque annonce, qui sert
# ensuite de clé au menu déroulant dans Google Sheets (sélectionner
# "RTX 3070" ou "Tous les GPU" filtre sur cette colonne).

def _modele_cpu_amd(title):
    t = _clean(title)
    m5 = re.search(r"(ryzen\s*5\D{0,3}\d{4}\w{0,2})", t)
    if m5:
        return "Ryzen 5 " + re.sub(r"ryzen\s*5\D{0,3}", "", m5.group(1)).upper()
    m7 = re.search(r"(ryzen\s*7\D{0,3}\d{4}\w{0,2})", t)
    if m7:
        return "Ryzen 7 " + re.sub(r"ryzen\s*7\D{0,3}", "", m7.group(1)).upper()
    return None


def _modele_cpu_intel(title):
    t = _clean(title)
    for serie in ("5", "7", "9"):
        m = re.search(rf"(i{serie}\D{{0,3}}\d{{4,5}}\w{{0,2}})", t)
        if m:
            num = re.sub(rf"i{serie}\D{{0,3}}", "", m.group(1))
            return f"Core i{serie}-{num.upper()}"
    return None


def _modele_gpu(title):
    t = _clean(title)
    m = re.search(r"(rtx\D{0,2}\d{4}\s*(ti|super)?)", t)
    if m:
        return m.group(1).upper().replace("  ", " ").strip()
    return None


def _modele_ram(title):
    t = _clean(title)
    m_kit = re.search(r"(\d+)\s*x\s*(\d+)\s*go", t)
    if m_kit:
        total = int(m_kit.group(1)) * int(m_kit.group(2))
        return f"DDR4 {total}Go"
    m_simple = re.search(r"(\d+)\s*go\b", t)
    if m_simple:
        return f"DDR4 {m_simple.group(1)}Go"
    return None


def _modele_cm_amd(title):
    t = _clean(title)
    for c in CHIPSETS_AMD_AM4:
        if re.search(rf"\b{c}\b", t):
            return c.upper()
    return None


def _modele_cm_intel(title):
    t = _clean(title)
    for c in CHIPSETS_INTEL:
        if re.search(rf"\b{c}\b", t):
            return c.upper()
    return None


def _modele_stockage(title):
    t = _clean(title)
    m_to = re.search(r"(\d+(?:[.,]\d+)?)\s*to\b", t)
    m_go = re.search(r"(\d+)\s*go\b", t)
    cap = f"{m_to.group(1)}To" if m_to else (f"{m_go.group(1)}Go" if m_go else "?")
    if "nvme" in t:
        return f"SSD NVMe {cap}"
    if "sata" in t or "ssd" in t:
        return f"SSD SATA {cap}"
    if "hdd" in t or "disque dur" in t:
        return f"HDD {cap}"
    return None


def _modele_alimentation(title):
    t = _clean(title)
    m = re.search(r"(\d{3,4})\s*w\b", t)
    return f"{m.group(1)}W" if m else None


def _modele_ventirad(title):
    return "Ventirad"  # pas de sous-catégorie par référence, cf. cahier des charges


IDENTIFIANTS_MODELE = {
    "cpu_amd": _modele_cpu_amd,
    "cpu_intel": _modele_cpu_intel,
    "gpu": _modele_gpu,
    "ram": _modele_ram,
    "cm_amd": _modele_cm_amd,
    "cm_intel": _modele_cm_intel,
    "stockage": _modele_stockage,
    "alimentation": _modele_alimentation,
    "ventirad": _modele_ventirad,
}


def identifier_modele(categorie_id, title):
    """Renvoie le libellé du modèle précis (ex: 'RTX 3070'), ou None."""
    fn = IDENTIFIANTS_MODELE.get(categorie_id)
    return fn(title) if fn else None


MATCHERS = {
    "match_cpu_amd": match_cpu_amd,
    "match_cpu_intel": match_cpu_intel,
    "match_gpu": match_gpu,
    "match_ram": match_ram,
    "match_cm_amd": match_cm_amd,
    "match_cm_intel": match_cm_intel,
    "match_stockage": match_stockage,
    "match_alimentation": match_alimentation,
    "match_ventirad": match_ventirad,
}


def get_matcher(nom):
    return MATCHERS[nom]
