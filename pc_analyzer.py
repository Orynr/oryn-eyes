"""
pc_analyzer.py
--------------
Analyse des annonces de PC gamer montés (Vinted + Leboncoin).

Trois responsabilités, toutes pures (aucun appel réseau, donc testables) :

1. QUALIFICATION — un PC entre dans l'analyse uniquement s'il a
   À LA FOIS un GPU qualifiant ET un CPU qualifiant (config.py).
   Sans les deux, c'est potentiellement un PC bureautique : exclu.

2. DÉTECTION DES COMPOSANTS — parse le titre + la description d'une
   annonce pour identifier GPU, CPU, RAM, stockage, alimentation,
   carte mère. Sert au calcul de la valeur nette.

3. VALEUR NETTE — combien coûterait de monter ce PC soi-même en
   occasion : somme des médianes des composants détectés, complétée
   par les valeurs par défaut de config.PC_DEFAUTS_NET pour les
   composants absents de l'annonce.
"""

import re

import config


def _clean(text):
    return (text or "").lower().strip()


# ====================================================================
# 1. QUALIFICATION GPU
# ====================================================================

# NVIDIA : RTX >= config.PC_GPU_NVIDIA_MIN (3060), toutes séries 30/40/50.
_RTX_PATTERN = re.compile(r"rtx\D{0,2}(\d{4})\s*(ti|super)?", re.IGNORECASE)
# AMD : RX suivi du modèle, éventuellement XT / XTX / GRE.
_RX_PATTERN = re.compile(r"\brx\D{0,2}(\d{4})\s*(xtx|xt|gre)?", re.IGNORECASE)


def detecter_gpu(text):
    """
    Retourne (marque, modele) du premier GPU QUALIFIANT trouvé, ou
    (None, None) si aucun GPU qualifiant.
      marque : "nvidia" | "amd"
      modele : "RTX 3060 TI", "RX 6700 XT", ...
    Les GPU non qualifiants (RTX < 3060, RX 6500...) sont ignorés
    mais leur présence est signalée par detecter_gpu_quelconque().
    """
    t = _clean(text)

    for m in _RTX_PATTERN.finditer(t):
        num = int(m.group(1))
        suffixe = (m.group(2) or "").upper()
        if num >= config.PC_GPU_NVIDIA_MIN:
            modele = f"RTX {num}" + (f" {suffixe}" if suffixe else "")
            return "nvidia", modele

    for m in _RX_PATTERN.finditer(t):
        num = m.group(1)
        suffixe = (m.group(2) or "").lower()
        cle = f"{num} {suffixe}".strip()
        if cle in config.PC_GPU_AMD_EXCLUS:
            continue
        if cle in config.PC_GPU_AMD_OK:
            modele = f"RX {num}" + (f" {suffixe.upper()}" if suffixe else "")
            return "amd", modele

    return None, None


def detecter_gpu_quelconque(text):
    """True si le texte mentionne un GPU, qualifiant ou non."""
    t = _clean(text)
    return bool(_RTX_PATTERN.search(t) or _RX_PATTERN.search(t)
                or re.search(r"\bgtx\D{0,2}\d{3,4}\b", t))


# ====================================================================
# 2. QUALIFICATION CPU
# ====================================================================

_RYZEN_PATTERN = re.compile(r"ryzen\s*[579]\D{0,3}(\d{4})(x3d|xt|x|g)?", re.IGNORECASE)
_INTEL_PATTERN = re.compile(r"i([579])\D{0,3}(\d{4,5})(k?f?s?)", re.IGNORECASE)


def detecter_cpu(text):
    """
    Retourne (marque, modele) du premier CPU QUALIFIANT, ou (None, None).
      marque : "amd" | "intel"
    AMD  : le numéro+suffixe doit être dans config.PC_CPU_AMD_OK.
    Intel: i5/i7/i9 générations 9 à 14.
    """
    t = _clean(text)

    for m in _RYZEN_PATTERN.finditer(t):
        num = m.group(1)
        suffixe = (m.group(2) or "").lower()
        cle = f"{num}{suffixe}"
        if cle in config.PC_CPU_AMD_OK:
            serie = "5" if num[0] in "345" and cle in {
                "3600", "3600x", "3600xt", "4500", "4600g",
                "5500", "5600", "5600g", "5600x"} else "7"
            return "amd", f"Ryzen {serie} {num.upper()}{suffixe.upper()}"

    for m in _INTEL_PATTERN.finditer(t):
        serie, num, suffixe = m.group(1), m.group(2), (m.group(3) or "")
        gen = int(num[:2]) if len(num) == 5 else int(num[0])
        if gen == 9 or 10 <= gen <= 14:
            return "intel", f"Core i{serie}-{num}{suffixe.upper()}"

    return None, None


# ====================================================================
# 3. QUALIFICATION D'UNE ANNONCE PC
# ====================================================================

def qualifier_pc(titre, description=""):
    """
    Analyse une annonce de PC. Retourne un dict :
      {
        "qualifie": bool,             # GPU qualifiant ET CPU qualifiant
        "gpu_marque": "nvidia"|"amd"|None,
        "gpu_modele": str|None,
        "cpu_marque": str|None,
        "cpu_modele": str|None,
      }
    Le titre et la description sont concaténés : sur Leboncoin, les
    détails sont souvent dans la description.
    """
    texte = f"{titre or ''} {description or ''}"
    gpu_marque, gpu_modele = detecter_gpu(texte)
    cpu_marque, cpu_modele = detecter_cpu(texte)
    return {
        "qualifie": bool(gpu_marque and cpu_marque),
        "gpu_marque": gpu_marque,
        "gpu_modele": gpu_modele,
        "cpu_marque": cpu_marque,
        "cpu_modele": cpu_modele,
    }


# ====================================================================
# 4. DÉTECTION DES AUTRES COMPOSANTS (pour la valeur nette)
# ====================================================================

def detecter_ram(text):
    """Retourne un modèle RAM normalisé ("DDR4 16Go") ou None."""
    t = _clean(text)
    m_kit = re.search(r"(\d+)\s*x\s*(\d+)\s*go\W{0,12}(?:de\s*)?(?:ram|ddr)", t)
    if not m_kit:
        m_kit = re.search(r"(?:ram|ddr[45]?)\D{0,10}(\d+)\s*x\s*(\d+)\s*go", t)
    if m_kit:
        total = int(m_kit.group(1)) * int(m_kit.group(2))
        return f"DDR4 {total}Go"
    m = re.search(r"(\d{1,3})\s*go\W{0,10}(?:de\s*)?(?:ram|ddr[45]?)", t)
    if not m:
        m = re.search(r"(?:ram|ddr[45]?)\D{0,10}(\d{1,3})\s*go", t)
    if m:
        cap = int(m.group(1))
        if cap in (8, 16, 32, 64):
            return f"DDR4 {cap}Go"
    return None


def detecter_stockage(text):
    """Retourne un modèle stockage normalisé ("SSD SATA 512Go") ou None."""
    t = _clean(text)
    m_to = re.search(r"(?:ssd|nvme)\D{0,12}(\d)\s*to\b", t)
    if m_to:
        return f"SSD NVMe {m_to.group(1)}To"
    m_go = re.search(r"(?:ssd|nvme)\D{0,12}(\d{3,4})\s*g[bo]\b", t)
    if m_go:
        cap = int(m_go.group(1))
        cap_norm = 256 if cap <= 300 else 512
        typ = "NVMe" if "nvme" in t else "SATA"
        return f"SSD {typ} {cap_norm}Go"
    if re.search(r"\bhdd\b|\bdisque\s*dur\b", t):
        m = re.search(r"(\d)\s*to\b", t)
        if m:
            return f"HDD {m.group(1)}To"
    return None


def detecter_alimentation(text):
    """Retourne un modèle alim normalisé ("650W") ou None."""
    t = _clean(text)
    m = re.search(r"(?:alim\w*|psu)\D{0,15}(\d{3,4})\s*w\b", t)
    if not m:
        m = re.search(r"(\d{3,4})\s*w\W{0,10}(?:alim\w*|psu|80\s*\+|gold|bronze)", t)
    if m:
        w = int(m.group(1))
        if 300 <= w <= 1600:
            return f"{w}W"
    return None


def detecter_carte_mere(text):
    """Retourne le chipset ("B550") ou None."""
    t = _clean(text)
    for c in ("a320", "b350", "x370", "b450", "x470", "a520", "b550", "x570",
              "h310", "b360", "h370", "b365", "z370", "z390",
              "h410", "b460", "h470", "b560", "h570", "z490", "z590",
              "h610", "b660", "h670", "b760", "z690", "z790"):
        if re.search(rf"\b{c}m?\b", t):
            return c.upper()
    return None


# ====================================================================
# 5. VALEUR NETTE D'UN PC
# ====================================================================

def _mediane_ou(medianes, cle, fallback):
    """medianes[cle] si dispo et > 0, sinon fallback."""
    v = medianes.get(cle)
    if v:
        return float(v), True
    return float(fallback), False


def valeur_nette_pc(titre, description, medianes_composants):
    """
    Calcule combien coûterait de monter ce PC soi-même en occasion.

    medianes_composants : dict {modele_normalise: mediane_occasion}
      Ex : {"RTX 3060": 210, "Ryzen 5 5600": 95, "DDR4 16Go": 32,
            "SSD SATA 512Go": 28, "650W": 40, "B550": 65}

    Défauts (config.PC_DEFAUTS_NET) si un composant n'est pas détecté :
      RAM absente        -> médiane "DDR4 16Go" (ou ram_fallback)
      Stockage absent    -> médiane "SSD SATA 512Go" (ou ssd_fallback)
      Alim absente       -> médiane des alims connues (ou alim_fallback)
      Boîtier            -> boitier_forfait (toujours, jamais dans les annonces)
      Carte mère absente -> carte_mere_forfait

    Retourne :
      {"net": float, "detail": {composant: {"source": "detecte"|"defaut",
                                             "modele": str, "valeur": float}}}
      ou None si le GPU ou le CPU qualifiant n'a pas de médiane connue
      (sans leur prix, la valeur nette ne veut rien dire).
    """
    d = config.PC_DEFAUTS_NET
    texte = f"{titre or ''} {description or ''}"
    detail = {}
    total = 0.0

    quali = qualifier_pc(titre, description)
    if not quali["qualifie"]:
        return None

    # --- GPU (obligatoire, médiane requise) ---
    med_gpu = medianes_composants.get(quali["gpu_modele"])
    if not med_gpu:
        # tolérance : "RTX 3060 TI" absent -> essaie "RTX 3060"
        base = re.sub(r"\s+(TI|SUPER|XT|XTX|GRE)$", "", quali["gpu_modele"] or "")
        med_gpu = medianes_composants.get(base)
    if not med_gpu:
        return None
    detail["gpu"] = {"source": "detecte", "modele": quali["gpu_modele"], "valeur": float(med_gpu)}
    total += float(med_gpu)

    # --- CPU (obligatoire, médiane requise) ---
    med_cpu = medianes_composants.get(quali["cpu_modele"])
    if not med_cpu:
        return None
    detail["cpu"] = {"source": "detecte", "modele": quali["cpu_modele"], "valeur": float(med_cpu)}
    total += float(med_cpu)

    # --- RAM ---
    ram = detecter_ram(texte)
    if ram and medianes_composants.get(ram):
        detail["ram"] = {"source": "detecte", "modele": ram,
                         "valeur": float(medianes_composants[ram])}
    else:
        v, trouve = _mediane_ou(medianes_composants, d["ram_modele"], d["ram_fallback"])
        detail["ram"] = {"source": "defaut", "modele": ram or d["ram_modele"], "valeur": v}
    total += detail["ram"]["valeur"]

    # --- Stockage ---
    sto = detecter_stockage(texte)
    if sto and medianes_composants.get(sto):
        detail["stockage"] = {"source": "detecte", "modele": sto,
                              "valeur": float(medianes_composants[sto])}
    else:
        v, _ = _mediane_ou(medianes_composants, d["ssd_modele"], d["ssd_fallback"])
        detail["stockage"] = {"source": "defaut", "modele": sto or d["ssd_modele"], "valeur": v}
    total += detail["stockage"]["valeur"]

    # --- Alimentation ---
    alim = detecter_alimentation(texte)
    if alim and medianes_composants.get(alim):
        detail["alimentation"] = {"source": "detecte", "modele": alim,
                                  "valeur": float(medianes_composants[alim])}
    else:
        alims = [v for k, v in medianes_composants.items()
                 if re.fullmatch(r"\d{3,4}W", k) and v]
        v = round(sum(alims) / len(alims), 2) if alims else float(d["alim_fallback"])
        detail["alimentation"] = {"source": "defaut", "modele": alim or "alim médiane", "valeur": v}
    total += detail["alimentation"]["valeur"]

    # --- Carte mère ---
    cm = detecter_carte_mere(texte)
    if cm and medianes_composants.get(cm):
        detail["carte_mere"] = {"source": "detecte", "modele": cm,
                                "valeur": float(medianes_composants[cm])}
    else:
        detail["carte_mere"] = {"source": "defaut", "modele": cm or "forfait",
                                "valeur": float(d["carte_mere_forfait"])}
    total += detail["carte_mere"]["valeur"]

    # --- Boîtier (forfait, jamais détaillé dans les annonces) ---
    detail["boitier"] = {"source": "defaut", "modele": "forfait",
                         "valeur": float(d["boitier_forfait"])}
    total += detail["boitier"]["valeur"]

    return {"net": round(total, 2), "detail": detail}


# ====================================================================
# 6. UTILITAIRE : est-ce une annonce de PC complet (pas un composant) ?
# ====================================================================

_PC_KEYWORDS = re.compile(
    r"\bpc\s*(gamer|gaming|fixe|complet)\b|\btour\s*gamer\b|\bunit[ée]\s*centrale\b|"
    r"\bordinateur\s*(gamer|gaming|fixe)\b|\bsetup\s*complet\b",
    re.IGNORECASE,
)


def est_annonce_pc(titre, description=""):
    """
    True si l'annonce ressemble à un PC complet monté (et pas à une
    carte graphique seule remontée par la recherche "pc gamer").
    Heuristique : mot-clé PC dans le titre, OU (mot-clé PC dans la
    description ET au moins GPU+CPU mentionnés).
    """
    if _PC_KEYWORDS.search(titre or ""):
        return True
    if _PC_KEYWORDS.search(description or ""):
        texte = f"{titre or ''} {description or ''}"
        gpu, _ = detecter_gpu(texte)
        cpu, _ = detecter_cpu(texte)
        return bool(gpu and cpu)
    return False
