"""
dashboard_export.py
-------------------
Construit le paquet de données du dashboard et génère dashboard.html :

  dashboard_template.html  (interface, jamais modifié à la main)
        + données JSON (composants, historiques, PC, deals...)
        = dashboard.html    (le fichier que tu ouvres dans Chrome)

Le template contient le placeholder /*__DATA__*/null/*__FIN_DATA__*/ ;
on y injecte le JSON. Résultat : un fichier autonome, double-clic,
aucun serveur, aucun internet requis pour l'affichage.
"""

import json
import os
from datetime import datetime

import config
import analysis
import ventes_tracker


def _maintenant_iso():
    return datetime.now().isoformat(timespec="seconds")


def _jour():
    return datetime.now().strftime("%Y-%m-%d")


def _date_courte(jour_iso):
    """"2026-08-20" -> "20/08" pour l'affichage."""
    try:
        return f"{jour_iso[8:10]}/{jour_iso[5:7]}"
    except (TypeError, IndexError):
        return str(jour_iso)


# ====================================================================
# MISE À JOUR DE L'HISTORIQUE (appelé par main.py après chaque cycle)
# ====================================================================

def assurer_structures(data):
    data.setdefault("observations", {})        # modele -> {"occasion":[{t,med}], "neuf":[...]}
    data.setdefault("plateformes_jour", {})    # modele -> {"occasion": {plat: {jour: med}}, "neuf": ...}
    data.setdefault("valeur_marche", {})       # modele -> {jour: {plat: somme}}
    data.setdefault("deals_log", [])
    data.setdefault("deals_ids", [])
    data.setdefault("rotation_duree", {})      # modele -> [heures]
    data.setdefault("pc_annonces", {})         # id -> annonce PC enrichie
    ventes_tracker.assurer_etat(data)
    return data


def _purger_vieux(data):
    """Limite la profondeur d'historique (HISTORIQUE_MAX_JOURS)."""
    limite = config.HISTORIQUE_MAX_JOURS
    for modele, obs in data["observations"].items():
        for flux in ("occasion", "neuf"):
            if flux in obs and len(obs[flux]) > limite * 30:
                obs[flux] = obs[flux][-limite * 30:]
    for modele, flux in data["plateformes_jour"].items():
        for f, plats in flux.items():
            for plat, jours in plats.items():
                if len(jours) > limite:
                    for k in sorted(jours)[:-limite]:
                        del jours[k]
    for modele, jours in data["valeur_marche"].items():
        if len(jours) > limite:
            for k in sorted(jours)[:-limite]:
                del jours[k]
    data["deals_log"] = data["deals_log"][-500:]
    data["deals_ids"] = data["deals_ids"][-2000:]
    for m, durees in data["rotation_duree"].items():
        data["rotation_duree"][m] = durees[-200:]


def enregistrer_cycle(data, listings_occ, listings_neuf):
    """
    À appeler après chaque cycle de scrape d'une catégorie.
    Alimente observations (OHLC), plateformes_jour, valeur_marche,
    deals_log.
    """
    assurer_structures(data)
    t = _maintenant_iso()
    jour = _jour()

    for flux, listings in (("occasion", listings_occ), ("neuf", listings_neuf)):
        par_modele = {}
        for l in listings:
            m = l.get("modele")
            if not m or l.get("alerte") == "masque":
                continue
            par_modele.setdefault(m, []).append(l)

        for m, ls in par_modele.items():
            prix = [l.get("prix_unitaire") or l["prix"] for l in ls]
            med = analysis.mediane(prix)
            if med:
                obs = data["observations"].setdefault(m, {"occasion": [], "neuf": []})
                obs.setdefault(flux, []).append({"t": t, "med": med})

            plats = {}
            for l in ls:
                plats.setdefault(l.get("plateforme", "?"), []).append(
                    l.get("prix_unitaire") or l["prix"])
            pj = data["plateformes_jour"].setdefault(m, {"occasion": {}, "neuf": {}})
            for plat, px in plats.items():
                valeur = analysis.mediane(px) if flux == "occasion" else min(px)
                pj.setdefault(flux, {}).setdefault(plat, {})[jour] = round(valeur, 2)

            if flux == "occasion":
                vm = data["valeur_marche"].setdefault(m, {})
                vm.setdefault(jour, {})
                for plat, px in plats.items():
                    vm[jour][plat] = round(sum(px), 2)

    # deals : chaque annonce rouge/orange pas encore vue
    for l in listings_occ:
        if l.get("alerte") not in ("rouge", "orange"):
            continue
        lid = str(l.get("id"))
        if lid in data["deals_ids"]:
            continue
        data["deals_ids"].append(lid)
        data["deals_log"].append({
            "date": datetime.now().strftime("%d/%m %H:%M"),
            "modele": l.get("modele") or "?",
            "titre": l.get("titre", ""),
            "prix": l.get("prix_unitaire") or l["prix"],
            "pct": l.get("pct_vs_mediane"),
            "marge": l.get("marge_estimee"),
            "plateforme": l.get("plateforme", ""),
            "alerte": l["alerte"],
            "url": l.get("url", "#"),
        })

    _purger_vieux(data)


def enregistrer_rotation(data, disparues):
    """Alimente rotation_duree à partir des annonces disparues (main.py)."""
    assurer_structures(data)
    for d in disparues:
        try:
            d1 = datetime.fromisoformat(d["premiere_vue"])
            d2 = datetime.fromisoformat(d["derniere_vue"])
            heures = (d2 - d1).total_seconds() / 3600
        except (KeyError, ValueError, TypeError):
            continue
        m = d.get("modele") or "?"
        data["rotation_duree"].setdefault(m, []).append(round(heures, 1))


# ====================================================================
# CONSTRUCTION DU PAQUET DASHBOARD
# ====================================================================

def _ohlc(observations):
    bougies = analysis.ohlc_quotidien(
        [{"horodatage": o["t"], "prix": o["med"]} for o in observations])
    return [{"date": _date_courte(b["date"]), "o": b["ouverture"], "c": b["cloture"],
             "h": b["haut"], "l": b["bas"]} for b in bougies][-30:]


def _series_plateformes(pj_flux):
    """{plat: {jour: val}} -> dates alignées + {plat: [val|None]}"""
    jours = sorted({j for plat in pj_flux.values() for j in plat})[-30:]
    series = {}
    for plat, vals in pj_flux.items():
        series[plat] = [vals.get(j) for j in jours]
    return [_date_courte(j) for j in jours], series


def construire_donnees(data, cache_occ, cache_neuf):
    """
    data : historique.json chargé
    cache_occ / cache_neuf : {cat_id: [listings enrichis]} du dernier état
    Retourne le dict complet injecté dans le dashboard.
    """
    assurer_structures(data)

    occ_flat, neuf_flat = [], []
    for cat_id, ls in cache_occ.items():
        occ_flat.extend(ls)
    for cat_id, ls in cache_neuf.items():
        neuf_flat.extend(ls)

    def _annonce_min(l):
        return {
            "id": str(l.get("id")), "titre": l.get("titre", ""),
            "prix": l["prix"], "modele": l.get("modele"),
            "plateforme": l.get("plateforme", ""), "url": l.get("url", "#"),
            "etat": l.get("etat", ""), "score_vendeur": l.get("score_vendeur"),
            "lot_type": l.get("lot_type", "normal"),
            "lot_quantite": l.get("lot_quantite", 1),
            "region": l.get("region", ""), "livraison": l.get("livraison", ""),
        }

    historique_prix = {}
    historique_plateformes = {}
    for m, obs in data["observations"].items():
        historique_prix[m] = {
            "occasion": _ohlc(obs.get("occasion", [])),
            "neuf": _ohlc(obs.get("neuf", [])),
        }
    dates_ref = {}
    for m, flux in data["plateformes_jour"].items():
        historique_plateformes[m] = {}
        for f in ("occasion", "neuf"):
            dates, series = _series_plateformes(flux.get(f, {}))
            historique_plateformes[m][f] = series
            dates_ref.setdefault(m, dates)

    evolution_marche = {}
    for m, jours in data["valeur_marche"].items():
        evolution_marche[m] = [
            {"date": _date_courte(j), **plats}
            for j, plats in sorted(jours.items())][-30:]

    rotation = {m: analysis.vitesse_rotation_moyenne(
                    [{"premiere_vue": "2000-01-01T00:00:00",
                      "derniere_vue": "2000-01-01T00:00:00"}]) or None
                for m in ()}  # placeholder, remplacé juste dessous
    rotation = {}
    for m, durees in data["rotation_duree"].items():
        if durees:
            rotation[m] = round(sum(durees) / len(durees), 1)

    # ---- PC ----
    etat_pc = data["ventes_pc"]
    pc_annonces = list(data["pc_annonces"].values())
    hist_jours = list(etat_pc.get("historique_jours", []))
    # le jour en cours est ajouté comme dernier point "live"
    j = etat_pc.get("jour", {})
    if etat_pc.get("jour_courant"):
        hist_jours = hist_jours + [{
            "date": etat_pc["jour_courant"],
            "vinted": j.get("ventes_vinted", 0),
            "leboncoin": j.get("ventes_leboncoin", 0),
            "nvidia": j.get("ventes_nvidia", 0),
            "amd": j.get("ventes_amd", 0),
            "vendu_estime": j.get("ventes_estimees", 0),
            "prix_ouverture": (j.get("prix_vendus") or [None])[0],
            "prix_cloture": (j.get("prix_vendus") or [None])[-1],
            "prix_min": min(j["prix_vendus"]) if j.get("prix_vendus") else None,
            "prix_max": max(j["prix_vendus"]) if j.get("prix_vendus") else None,
        }]
    ventes_jour = [{
        "date": _date_courte(h["date"]),
        "vinted": h.get("vinted", 0), "leboncoin": h.get("leboncoin", 0),
        "nvidia": h.get("nvidia", 0), "amd": h.get("amd", 0),
        "vendu_estime": h.get("vendu_estime", 0),
    } for h in hist_jours][-30:]

    # brut vs net : médianes quotidiennes des annonces PC (recalculées à
    # chaque génération sur les annonces courantes -> stockées par jour)
    data.setdefault("pc_brut_net", {})
    prix_pc = [a["prix"] for a in pc_annonces if a.get("prix")]
    nets_pc = [a["net"] for a in pc_annonces if a.get("net")]
    if prix_pc:
        data["pc_brut_net"][_jour()] = {
            "brut": analysis.mediane(prix_pc),
            "net": analysis.mediane(nets_pc) if nets_pc else None,
        }
    if len(data["pc_brut_net"]) > config.HISTORIQUE_MAX_JOURS:
        for k in sorted(data["pc_brut_net"])[:-config.HISTORIQUE_MAX_JOURS]:
            del data["pc_brut_net"][k]
    brut_net = [{"date": _date_courte(j2), "brut": v.get("brut"), "net": v.get("net")}
                for j2, v in sorted(data["pc_brut_net"].items())][-30:]

    paquet = {
        "genere_le": _maintenant_iso(),
        "demo": False,
        "seuils": {"rouge": config.SEUIL_ROUGE, "orange": config.SEUIL_ORANGE,
                    "masquage": config.SEUIL_MASQUAGE},
        "frais": config.MARGE_FRAIS_ESTIMES,
        "composants": {
            "occasion": [_annonce_min(l) for l in occ_flat],
            "neuf": [_annonce_min(l) for l in neuf_flat],
        },
        "historique_prix": historique_prix,
        "historique_plateformes": historique_plateformes,
        "evolution_marche": evolution_marche,
        "deals_log": data["deals_log"][-200:],
        "rotation": rotation,
        "pc": {
            "annonces": pc_annonces,
            "ventes_jour": ventes_jour,
            "bougies_ventes_jour": ventes_tracker.bougies_jour(hist_jours),
            "bougies_ventes_semaine": ventes_tracker.bougies_semaine(hist_jours),
            "brut_net": brut_net,
        },
    }
    return paquet


# ====================================================================
# GÉNÉRATION DU FICHIER
# ====================================================================

def generer_dashboard(paquet):
    """Injecte le paquet dans le template et écrit config.DASHBOARD_FILE."""
    chemin_tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               config.DASHBOARD_TEMPLATE)
    with open(chemin_tpl, "r", encoding="utf-8") as f:
        tpl = f.read()

    debut = tpl.find("/*__DATA__*/")
    fin = tpl.find("/*__FIN_DATA__*/")
    if debut == -1 or fin == -1:
        raise RuntimeError("Placeholder /*__DATA__*/ introuvable dans le template")

    js = json.dumps(paquet, ensure_ascii=False, separators=(",", ":"))
    contenu = tpl[:debut] + "/*__DATA__*/" + js + tpl[fin:]

    with open(config.DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(contenu)
    return config.DASHBOARD_FILE
