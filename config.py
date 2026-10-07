"""
config.py
---------
Tous les paramètres du projet sont ici. C'est le SEUL fichier que tu
modifies au quotidien : composants suivis, seuils, fréquences, accès
Google Sheets / eBay, et réglages de l'onglet Vente PC.
"""

# ====================================================================
# GOOGLE SHEETS (backup optionnel — le dashboard HTML est la vraie interface)
# ====================================================================
GOOGLE_SHEETS_ACTIF = False   # True si tu veux garder le Sheet en parallèle
GOOGLE_SHEET_ID = "1FuV-0uHinmtd2XLTsjGkpFPXFA-pMBHY0de5fBa78T0"
GOOGLE_KEY_FILE = "vinted-watch-3841e3f84afb.json"

# ====================================================================
# EBAY (optionnel)
# ====================================================================
# Laisse vide pour désactiver eBay proprement (le script tourne sans).
# Clés à obtenir sur developer.ebay.com (compte gratuit, "Browse API").
EBAY_CLIENT_ID = ""
EBAY_CLIENT_SECRET = ""
EBAY_MARKETPLACE = "EBAY_FR"

# ====================================================================
# SEUILS D'ALERTE — basés sur l'écart à la médiane du composant
# ====================================================================
SEUIL_ROUGE = -30       # en dessous de -30% vs médiane -> rouge : achète
SEUIL_ORANGE = -15      # entre -30% et -15%            -> orange : regarde
# entre -15% et la médiane                               -> vert : correct
# entre la médiane et +15%                               -> gris : au-dessus
SEUIL_MASQUAGE = 15     # au-dessus de +15% vs médiane  -> masqué (pas affiché)

MARGE_FRAIS_ESTIMES = 12   # € forfaitaires (frais plateforme + livraison)

# ====================================================================
# ANTI-BLOCAGE — le script ralentit tout seul s'il se fait bloquer
# ====================================================================
BLOCAGES_AVANT_RALENTISSEMENT = 2
FACTEUR_RALENTISSEMENT = 2
FREQUENCE_MAX_SECONDES = 3600

# ====================================================================
# COMPOSANTS SUIVIS
# ====================================================================
COMPOSANTS = {
    "cpu_amd": {
        "label": "CPU AMD",
        "search_terms": ["ryzen 5", "ryzen 7"],
        "frequence": 300,
        "matcher": "match_cpu_amd",
    },
    "cpu_intel": {
        "label": "CPU Intel",
        "search_terms": ["core i5", "core i7", "core i9"],
        "frequence": 300,
        "matcher": "match_cpu_intel",
    },
    "gpu": {
        "label": "GPU",
        "search_terms": ["rtx 2060", "rtx 2070", "rtx 2080", "rtx 3060",
                          "rtx 3070", "rtx 3080", "rtx 4060", "rtx 4070",
                          "geforce 3060", "geforce 3070", "nvidia 3060"],
        "frequence": 300,
        "matcher": "match_gpu",
    },
    "ram": {
        "label": "RAM",
        "search_terms": ["ram ddr4"],
        "frequence": 300,
        "matcher": "match_ram",
    },
    "cm_amd": {
        "label": "CM AMD",
        "search_terms": ["carte mere a320", "carte mere b350", "carte mere x370",
                          "carte mere b450", "carte mere x470", "carte mere a520",
                          "carte mere b550", "carte mere x570"],
        "frequence": 900,
        "matcher": "match_cm_amd",
    },
    "cm_intel": {
        "label": "CM Intel",
        "search_terms": ["carte mere h310", "carte mere b360", "carte mere h370",
                          "carte mere b365", "carte mere z370", "carte mere z390",
                          "carte mere h410", "carte mere b460", "carte mere h470",
                          "carte mere b560", "carte mere h570", "carte mere z490",
                          "carte mere z590", "carte mere h610", "carte mere b660",
                          "carte mere h670", "carte mere b760", "carte mere z690",
                          "carte mere z790"],
        "frequence": 900,
        "matcher": "match_cm_intel",
    },
    "stockage": {
        "label": "Stockage",
        "search_terms": ["ssd nvme", "ssd sata", "disque dur"],
        "frequence": 900,
        "matcher": "match_stockage",
    },
    "alimentation": {
        "label": "Alimentation",
        "search_terms": ["alimentation pc"],
        "frequence": 1800,
        "matcher": "match_alimentation",
    },
    "ventirad": {
        "label": "Ventirad",
        "search_terms": ["ventirad"],
        "frequence": 1800,
        "matcher": "match_ventirad",
    },
}

# Termes GPUTracker : URL par chipset (facet). Clé = nom modèle affiché.
GPUTRACKER_GPU_FACETS = {
    "RTX 2060": "nvidia-rtx-2060",
    "RTX 3060": "nvidia-rtx-3060",
    "RTX 3060 TI": "nvidia-rtx-3060-ti",
    "RTX 3070": "nvidia-rtx-3070",
    "RTX 3070 TI": "nvidia-rtx-3070-ti",
    "RTX 3080": "nvidia-rtx-3080",
    "RTX 3080 TI": "nvidia-rtx-3080-ti",
    "RTX 4060": "nvidia-rtx-4060",
    "RTX 4060 TI": "nvidia-rtx-4060-ti",
    "RTX 4070": "nvidia-rtx-4070",
    "RTX 4070 TI": "nvidia-rtx-4070-ti",
}
# Catégories GPUTracker pour recherche texte (CPU / RAM / SSD / alim / CM)
GPUTRACKER_CATEGORIES = {
    "cpu": ("2", "processeurs"),
    "ram": ("11", "memoire-vive-ram"),
    "ssd": ("4", "ssd"),
    "alimentation": ("6", "alimentations"),
    "carte_mere": ("8", "cartes-meres"),
    "gpu": ("1", "cartes-graphiques"),
}

# ====================================================================
# PLATEFORMES OCCASION
# ====================================================================
PLATEFORMES_OCCASION = {
    "vinted":        {"actif": True,  "label": "Vinted"},
    "leboncoin":     {"actif": True,  "label": "Leboncoin"},   # à tester en réel (DataDome)
    "mon7up":        {"actif": True,  "label": "Mon7up"},
    "ebay":          {"actif": False, "label": "eBay"},        # True quand EBAY_CLIENT_ID/SECRET remplis
    "pcc_occasion":  {"actif": True,  "label": "PCC Reconditionné"},
}

# ====================================================================
# PLATEFORMES NEUF (référence de prix)
# ====================================================================
PLATEFORMES_NEUF = {
    "gputracker":     {"actif": True,  "label": "GPUTracker"},   # 117 magasins agrégés
    "idealo":         {"actif": True,  "label": "Idealo"},       # backup / croisement
    "pccomponentes":  {"actif": True,  "label": "PC Componentes"},
}
# Fréquence du neuf (les prix neufs bougent lentement) :
FREQUENCE_NEUF_SECONDES = 6 * 3600   # toutes les 6 heures

# ====================================================================
# ONGLET VENTE PC — analyse du marché des PC gamer montés
# ====================================================================
PC_ACTIF = True
PC_SEARCH_TERMS = ["pc gamer", "pc gaming"]
PC_FREQUENCE_SECONDES = 1800          # scan des annonces PC toutes les 30 min
PC_CYCLE_VENTES_SECONDES = 3 * 3600   # comparaison ventes toutes les 3 h
# reset des compteurs de ventes chaque jour à minuit (automatique)

# GPU qualifiants — un PC est retenu s'il a un GPU ET un CPU de ces listes.
# NVIDIA : à partir de la RTX 3060 (séries 30/40/50 incluses)
PC_GPU_NVIDIA_MIN = 3060
# AMD : à partir de la RX 5700 XT ; RX 6400 / 6500 / 6500 XT exclues
PC_GPU_AMD_OK = {
    "5700 xt", "6600", "6600 xt", "6650 xt", "6700", "6700 xt", "6750 xt",
    "6800", "6800 xt", "6900 xt", "6950 xt",
    "7600", "7600 xt", "7700 xt", "7800 xt", "7900 gre", "7900 xt", "7900 xtx",
    "9060 xt", "9070", "9070 gre", "9070 xt",
}
PC_GPU_AMD_EXCLUS = {"6400", "6500", "6500 xt"}

# CPU qualifiants = exactement les modèles suivis dans COMPOSANTS
PC_CPU_AMD_OK = {
    "3600", "3600x", "3600xt", "4500", "4600g", "5500", "5600", "5600g", "5600x",
    "2700", "2700x", "3700x", "3800x", "4700g", "5700g", "5700x", "5800x", "5800x3d",
}
# Intel : i5/i7/i9 générations 9 à 14 (validé par regex dans pc_analyzer)

# Valeurs par défaut pour le calcul de la valeur NETTE d'un PC quand un
# composant n'est pas détecté dans l'annonce :
PC_DEFAUTS_NET = {
    "ram_modele": "DDR4 16Go",     # médiane de ce modèle si RAM absente
    "ssd_modele": "SSD SATA 512Go",# médiane de ce modèle si stockage absent
    "alim_fallback": 45,           # € si aucune médiane d'alim dispo
    "ram_fallback": 30,            # € si aucune médiane RAM dispo
    "ssd_fallback": 30,            # € si aucune médiane SSD dispo
    "boitier_forfait": 50,         # € toujours ajoutés (boîtier)
    "carte_mere_forfait": 50,      # € ajoutés si CM non détectée / pas de médiane
}

# ====================================================================
# DASHBOARD
# ====================================================================
DASHBOARD_FILE = "dashboard.html"          # le fichier que tu ouvres dans Chrome
DASHBOARD_TEMPLATE = "dashboard_template.html"
HISTORIQUE_MAX_JOURS = 90                  # profondeur d'historique conservée

# ====================================================================
# FICHIERS LOCAUX
# ====================================================================
DATA_FILE = "historique.json"       # mémoire persistante (annonces vues, historique)
EXCEL_BACKUP_FILE = "backup_local.xlsx"
