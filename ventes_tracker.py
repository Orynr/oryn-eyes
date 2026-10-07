"""
ventes_tracker.py
-----------------
Suivi des VENTES de PC gamer (annonces disparues) sur Vinted et
Leboncoin.

Principe validé avec Omar :
  - le scan des annonces PC tourne toutes les 30 min (main.py) ;
  - toutes les 3 h, on compare le stock actuel au snapshot d'il y a 3 h :
    les annonces qui ont disparu sont comptées comme "vendues"
    (par plateforme, et par marque de GPU nvidia/amd) ;
  - chaque jour à minuit, les compteurs du jour sont archivés comme un
    point d'historique (les courbes du dashboard) puis remis à zéro.

Distinction "vendu" vs "supprimé" :
  L'API ne dit pas pourquoi une annonce disparaît. On applique le
  filtre convenu : une annonce disparue est comptée "vendue" ;
  elle est EN PLUS comptée "vendu_estime" (courbe séparée) uniquement
  si elle est restée en ligne moins de VENTE_MAX_JOURS jours — une
  annonce très ancienne qui disparaît est plus probablement retirée.

Toutes les fonctions sont pures vis-à-vis du réseau : elles ne
travaillent que sur le dict d'état (persisté dans historique.json par
main.py) et la liste d'annonces du scan courant. Testables à 100 %.
"""

from datetime import datetime

VENTE_MAX_JOURS = 21   # au-delà, une disparition est considérée "retrait probable"


def _etat_initial():
    return {
        # snapshot du dernier cycle de comparaison (3 h)
        "snapshot": {},            # {id: {"plateforme","gpu_marque","prix","premiere_vue","region","livraison","titre"}}
        "dernier_cycle": None,     # iso du dernier cycle 3 h
        "jour_courant": None,      # "YYYY-MM-DD" du cycle de compteurs en cours
        # compteurs du jour (reset à minuit)
        "jour": {
            "ventes_vinted": 0, "ventes_leboncoin": 0,
            "ventes_nvidia": 0, "ventes_amd": 0,
            "ventes_estimees": 0,           # disparues en < VENTE_MAX_JOURS
            "prix_vendus": [],              # prix des annonces disparues (bougies)
        },
        # historique archivé, un point par jour
        "historique_jours": [],    # [{"date","vinted","leboncoin","nvidia","amd","vendu_estime","prix_min","prix_max","prix_ouverture","prix_cloture","nb"}]
    }


def assurer_etat(data):
    """Garantit la présence de la structure ventes_pc dans historique.json."""
    if "ventes_pc" not in data:
        data["ventes_pc"] = _etat_initial()
    return data["ventes_pc"]


def _jour(dt=None):
    return (dt or datetime.now()).strftime("%Y-%m-%d")


def _duree_jours(premiere_vue_iso, maintenant):
    try:
        d = datetime.fromisoformat(premiere_vue_iso)
        return (maintenant - d).total_seconds() / 86400
    except (ValueError, TypeError):
        return 0


def archiver_jour_si_necessaire(etat, maintenant=None):
    """
    Si on a changé de jour depuis le dernier cycle, archive les
    compteurs du jour écoulé dans historique_jours et repart à zéro.
    Retourne True si un archivage a eu lieu.
    """
    maintenant = maintenant or datetime.now()
    jour_actuel = _jour(maintenant)

    if etat["jour_courant"] is None:
        etat["jour_courant"] = jour_actuel
        return False

    if etat["jour_courant"] == jour_actuel:
        return False

    j = etat["jour"]
    prix = sorted(j["prix_vendus"])
    point = {
        "date": etat["jour_courant"],
        "vinted": j["ventes_vinted"],
        "leboncoin": j["ventes_leboncoin"],
        "nvidia": j["ventes_nvidia"],
        "amd": j["ventes_amd"],
        "vendu_estime": j["ventes_estimees"],
        "nb": len(prix),
        "prix_ouverture": j["prix_vendus"][0] if j["prix_vendus"] else None,
        "prix_cloture": j["prix_vendus"][-1] if j["prix_vendus"] else None,
        "prix_min": prix[0] if prix else None,
        "prix_max": prix[-1] if prix else None,
    }
    etat["historique_jours"].append(point)
    etat["historique_jours"] = etat["historique_jours"][-120:]  # 4 mois max

    etat["jour"] = _etat_initial()["jour"]
    etat["jour_courant"] = jour_actuel
    return True


def cycle_du(etat, cycle_secondes, maintenant=None):
    """True si le cycle de comparaison (3 h) est dû."""
    maintenant = maintenant or datetime.now()
    if etat["dernier_cycle"] is None:
        return True
    try:
        dernier = datetime.fromisoformat(etat["dernier_cycle"])
    except (ValueError, TypeError):
        return True
    return (maintenant - dernier).total_seconds() >= cycle_secondes


def comparer_et_compter(etat, annonces_actuelles, maintenant=None):
    """
    Le cœur du tracker. À appeler quand cycle_du() est True.

    annonces_actuelles : liste de dicts d'annonces PC qualifiées du scan
      courant, chacune avec au minimum :
        {"id", "plateforme", "gpu_marque", "prix", "premiere_vue",
         "region", "livraison", "titre"}

    1. Toute annonce présente dans le snapshot mais absente du scan
       courant = disparue = vente comptée (plateforme + marque GPU).
       Si en ligne < VENTE_MAX_JOURS -> aussi comptée "vendu_estime".
    2. Le snapshot est remplacé par le scan courant.

    Retourne la liste des annonces disparues (pour log/debug).
    """
    maintenant = maintenant or datetime.now()
    archiver_jour_si_necessaire(etat, maintenant)

    ids_actuels = {str(a["id"]) for a in annonces_actuelles}
    disparues = []

    for aid, info in list(etat["snapshot"].items()):
        if aid in ids_actuels:
            continue
        disparues.append(info)

        plateforme = (info.get("plateforme") or "").lower()
        if "vinted" in plateforme:
            etat["jour"]["ventes_vinted"] += 1
        elif "leboncoin" in plateforme:
            etat["jour"]["ventes_leboncoin"] += 1

        marque = info.get("gpu_marque")
        if marque == "nvidia":
            etat["jour"]["ventes_nvidia"] += 1
        elif marque == "amd":
            etat["jour"]["ventes_amd"] += 1

        if _duree_jours(info.get("premiere_vue"), maintenant) < VENTE_MAX_JOURS:
            etat["jour"]["ventes_estimees"] += 1

        if info.get("prix"):
            etat["jour"]["prix_vendus"].append(float(info["prix"]))

    # nouveau snapshot = scan courant (en conservant premiere_vue connue)
    nouveau = {}
    for a in annonces_actuelles:
        aid = str(a["id"])
        ancienne = etat["snapshot"].get(aid, {})
        nouveau[aid] = {
            "plateforme": a.get("plateforme"),
            "gpu_marque": a.get("gpu_marque"),
            "prix": a.get("prix"),
            "premiere_vue": ancienne.get("premiere_vue") or a.get("premiere_vue")
                            or maintenant.isoformat(timespec="seconds"),
            "region": a.get("region"),
            "livraison": a.get("livraison"),
            "titre": a.get("titre"),
        }
    etat["snapshot"] = nouveau
    etat["dernier_cycle"] = maintenant.isoformat(timespec="seconds")
    return disparues


# ====================================================================
# AGRÉGATIONS POUR LE DASHBOARD
# ====================================================================

def bougies_semaine(historique_jours):
    """
    Agrège l'historique quotidien en bougies hebdomadaires (ISO week).
    Retourne [{"date": "S33", "o","c","h","l"}].
    """
    from collections import OrderedDict
    semaines = OrderedDict()
    for j in historique_jours:
        if j.get("prix_ouverture") is None:
            continue
        try:
            dt = datetime.fromisoformat(j["date"])
        except (ValueError, TypeError):
            continue
        cle = f"S{dt.isocalendar()[1]:02d}"
        s = semaines.setdefault(cle, {"o": j["prix_ouverture"], "c": j["prix_cloture"],
                                       "h": j["prix_max"], "l": j["prix_min"]})
        s["c"] = j["prix_cloture"]
        s["h"] = max(s["h"], j["prix_max"])
        s["l"] = min(s["l"], j["prix_min"])
    return [{"date": k, **v} for k, v in semaines.items()]


def bougies_jour(historique_jours):
    """Bougies quotidiennes des prix des PC vendus."""
    out = []
    for j in historique_jours:
        if j.get("prix_ouverture") is None:
            continue
        out.append({"date": j["date"][5:],  # MM-DD
                    "o": j["prix_ouverture"], "c": j["prix_cloture"],
                    "h": j["prix_max"], "l": j["prix_min"]})
    return out
