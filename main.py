"""
main.py
-------
Le seul fichier à lancer : `python main.py`.

Ce qu'il orchestre, chacun à son rythme :
  - COMPOSANTS OCCASION (Vinted, Leboncoin, Mon7up, PCC Reconditionné,
    eBay si clés) : fréquence par catégorie (config.COMPOSANTS)
  - COMPOSANTS NEUF (GPUTracker 117 magasins, Idealo, PC Componentes) :
    toutes les 6 h (les prix neufs bougent lentement)
  - PC GAMER (Vinted + Leboncoin) : scan toutes les 30 min,
    comptage des ventes toutes les 3 h, reset des compteurs à minuit
  - DASHBOARD : dashboard.html régénéré après chaque cycle -> F5 dans
    le navigateur pour voir les nouvelles données
  - Google Sheets / Excel : backups optionnels

Anti-blocage : si une plateforme renvoie des 403 répétés, la fréquence
de la catégorie est multipliée automatiquement (jamais de contournement,
juste un ralentissement).
"""

import json
import os
import time
from datetime import datetime, timedelta

import config
import analysis
import pc_analyzer
import ventes_tracker
import dashboard_export
import scraper_vinted
import scraper_leboncoin
import scraper_mon7up
import scraper_gputracker
import scraper_idealo
import scraper_pccomponentes
import scraper_ebay
import sheets_export
import excel_export

TICK_SECONDES = 60


def maintenant():
    return datetime.now()


def maintenant_iso():
    return maintenant().isoformat(timespec="seconds")


# --------------------------------------------------------------------
# PERSISTANCE LOCALE
# --------------------------------------------------------------------

def charger_historique():
    if os.path.exists(config.DATA_FILE):
        with open(config.DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault("vus", {})
    for cat_id in config.COMPOSANTS:
        data["vus"].setdefault(cat_id, {})
    data.setdefault("prochaine_verif", {})
    data.setdefault("compteur_blocages", {})
    data.setdefault("frequences_actuelles",
                    {cid: c["frequence"] for cid, c in config.COMPOSANTS.items()})
    data.setdefault("prochaine_verif_neuf", None)
    data.setdefault("prochain_scan_pc", None)
    dashboard_export.assurer_structures(data)
    return data


def sauvegarder_historique(data):
    with open(config.DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# --------------------------------------------------------------------
# RALENTISSEMENT AUTOMATIQUE
# --------------------------------------------------------------------

def gerer_blocage(data, cle, bloque, frequence_base):
    if bloque:
        data["compteur_blocages"][cle] = data["compteur_blocages"].get(cle, 0) + 1
        if data["compteur_blocages"][cle] >= config.BLOCAGES_AVANT_RALENTISSEMENT:
            actuelle = data["frequences_actuelles"].get(cle, frequence_base)
            nouvelle = min(actuelle * config.FACTEUR_RALENTISSEMENT,
                           config.FREQUENCE_MAX_SECONDES)
            if nouvelle != actuelle:
                print(f"[{maintenant_iso()}] {cle} : blocages répétés, "
                      f"fréquence {actuelle}s -> {nouvelle}s")
            data["frequences_actuelles"][cle] = nouvelle
            data["compteur_blocages"][cle] = 0
    else:
        data["compteur_blocages"][cle] = 0
        # retour progressif à la normale après une période calme
        actuelle = data["frequences_actuelles"].get(cle, frequence_base)
        if actuelle > frequence_base:
            data["frequences_actuelles"][cle] = max(frequence_base,
                                                     actuelle // config.FACTEUR_RALENTISSEMENT)


# --------------------------------------------------------------------
# COLLECTE OCCASION D'UNE CATÉGORIE (toutes plateformes actives)
# --------------------------------------------------------------------

def collecter_occasion(cat_id, sessions, data):
    listings = []
    bloque = False
    P = config.PLATEFORMES_OCCASION

    if P["vinted"]["actif"] and sessions.get("vinted"):
        l, b = scraper_vinted.collecter_categorie(cat_id, sessions["vinted"])
        listings += l; bloque = bloque or b
    if P["leboncoin"]["actif"] and sessions.get("leboncoin"):
        l, b = scraper_leboncoin.collecter_categorie(cat_id, sessions["leboncoin"])
        listings += l; bloque = bloque or b
    if P["mon7up"]["actif"]:
        l, b = scraper_mon7up.collecter_categorie(cat_id, sessions.get("mon7up"))
        listings += l; bloque = bloque or b
    if P["pcc_occasion"]["actif"]:
        l, b = scraper_pccomponentes.collecter_categorie_occasion(
            cat_id, sessions.get("pcc"))
        listings += l; bloque = bloque or b
    if P["ebay"]["actif"]:
        l, b = scraper_ebay.collecter_categorie(cat_id)
        listings += l; bloque = bloque or b

    # --- suivi rotation / disparitions (comme v1) ---
    vus = data["vus"].setdefault(cat_id, {})
    ids_cycle = set()
    for l in listings:
        lid = str(l.get("id"))
        ids_cycle.add(lid)
        if lid in vus:
            vus[lid]["derniere_vue"] = maintenant_iso()
        else:
            vus[lid] = {"modele": l.get("modele", ""), "prix": l["prix"],
                        "plateforme": l.get("plateforme", ""),
                        "premiere_vue": maintenant_iso(),
                        "derniere_vue": maintenant_iso()}
    disparues = []
    for lid in set(vus.keys()) - ids_cycle:
        info = vus.pop(lid)
        disparues.append({**info, "categorie": config.COMPOSANTS[cat_id]["label"]})
    dashboard_export.enregistrer_rotation(data, disparues)

    return sheets_export.enrichir_listings(listings), bloque, disparues


# --------------------------------------------------------------------
# COLLECTE NEUF (toutes catégories, toutes les 6 h)
# --------------------------------------------------------------------

def collecter_neuf_toutes_categories(sessions):
    P = config.PLATEFORMES_NEUF
    resultat = {}
    for cat_id in config.COMPOSANTS:
        listings = []
        if P["gputracker"]["actif"]:
            l, _ = scraper_gputracker.collecter_categorie(cat_id, sessions.get("gputracker"))
            listings += l
        if P["idealo"]["actif"]:
            l, _ = scraper_idealo.collecter_categorie(cat_id, sessions.get("idealo"))
            listings += l
        if P["pccomponentes"]["actif"]:
            l, _ = scraper_pccomponentes.collecter_categorie_neuf(cat_id, sessions.get("pcc"))
            listings += l
        resultat[cat_id] = sheets_export.enrichir_listings(listings)
        print(f"[{maintenant_iso()}]   Neuf {config.COMPOSANTS[cat_id]['label']} : "
              f"{len(resultat[cat_id])} offres")
    return resultat


# --------------------------------------------------------------------
# PIPELINE PC GAMER
# --------------------------------------------------------------------

def medianes_pour_net(cache_occ):
    """Extrait {modele: mediane_occasion} de toutes les annonces en cache."""
    par_modele = {}
    for ls in cache_occ.values():
        for l in ls:
            m = l.get("modele")
            if not m or l.get("alerte") == "masque":
                continue
            par_modele.setdefault(m, []).append(l.get("prix_unitaire") or l["prix"])
    return {m: analysis.mediane(px) for m, px in par_modele.items()}


def scanner_pc(sessions, data, cache_occ):
    """Scan PC (30 min) : collecte, qualification, net, suivi ventes."""
    annonces = []
    bloque = False
    if config.PLATEFORMES_OCCASION["vinted"]["actif"] and sessions.get("vinted"):
        l, b = scraper_vinted.collecter_pc(sessions["vinted"])
        annonces += l; bloque = bloque or b
    if config.PLATEFORMES_OCCASION["leboncoin"]["actif"] and sessions.get("leboncoin"):
        l, b = scraper_leboncoin.collecter_pc(sessions["leboncoin"])
        annonces += l; bloque = bloque or b

    medianes = medianes_pour_net(cache_occ)
    pc_vus = data["pc_annonces"]
    ids_cycle = set()
    for a in annonces:
        aid = str(a["id"])
        ids_cycle.add(aid)
        ancien = pc_vus.get(aid, {})
        net_info = pc_analyzer.valeur_nette_pc(a["titre"], a.get("description", ""), medianes)
        net = net_info["net"] if net_info else None
        pc_vus[aid] = {
            "id": aid, "titre": a["titre"], "prix": a["prix"],
            "gpu_marque": a["gpu_marque"], "gpu_modele": a["gpu_modele"],
            "cpu_marque": a["cpu_marque"], "cpu_modele": a["cpu_modele"],
            "plateforme": a["plateforme"], "url": a.get("url", "#"),
            "region": a.get("region", ""), "livraison": a.get("livraison", "?"),
            "net": net, "ecart": round(a["prix"] - net, 2) if net else None,
            "premiere_vue": ancien.get("premiere_vue") or maintenant_iso(),
        }
    # les annonces PC absentes du scan restent dans pc_vus jusqu'au cycle
    # ventes (3 h) qui les compte comme vendues, puis on purge ici :
    etat = ventes_tracker.assurer_etat(data)
    if ventes_tracker.cycle_du(etat, config.PC_CYCLE_VENTES_SECONDES):
        courantes = [pc_vus[i] for i in ids_cycle if i in pc_vus]
        disparues = ventes_tracker.comparer_et_compter(etat, courantes)
        # purge des annonces disparues du tableau live
        for aid in list(pc_vus.keys()):
            if aid not in ids_cycle:
                del pc_vus[aid]
        if disparues:
            print(f"[{maintenant_iso()}] PC : {len(disparues)} annonces disparues "
                  f"(comptées comme ventes)")

    print(f"[{maintenant_iso()}] PC gamer : {len(ids_cycle)} annonces qualifiées "
          f"en ligne ({sum(1 for a in pc_vus.values() if a.get('ecart') is not None and a['ecart'] < 0)} sous-évaluées)")
    return bloque


# --------------------------------------------------------------------
# BOUCLE PRINCIPALE
# --------------------------------------------------------------------

def creer_sessions():
    s = {}
    P = config.PLATEFORMES_OCCASION
    if P["vinted"]["actif"]:
        try: s["vinted"] = scraper_vinted.creer_session()
        except Exception as e: print(f"[{maintenant_iso()}] Session Vinted KO : {e}")
    if P["leboncoin"]["actif"]:
        try: s["leboncoin"] = scraper_leboncoin.creer_session()
        except Exception as e: print(f"[{maintenant_iso()}] Session Leboncoin KO : {e}")
    if P["mon7up"]["actif"]:
        s["mon7up"] = scraper_mon7up.creer_session()
    if P["pcc_occasion"]["actif"] or config.PLATEFORMES_NEUF["pccomponentes"]["actif"]:
        s["pcc"] = scraper_pccomponentes.creer_session()
    if config.PLATEFORMES_NEUF["gputracker"]["actif"]:
        s["gputracker"] = scraper_gputracker.creer_session()
    if config.PLATEFORMES_NEUF["idealo"]["actif"]:
        s["idealo"] = scraper_idealo.creer_session()
    return s


def run():
    print(f"[{maintenant_iso()}] Démarrage de la veille composants v2.")
    data = charger_historique()
    sessions = creer_sessions()

    classeur = None
    if config.GOOGLE_SHEETS_ACTIF:
        try:
            classeur = sheets_export.connecter()
            print(f"[{maintenant_iso()}] Google Sheets connecté (backup).")
        except Exception as e:
            print(f"[{maintenant_iso()}] Google Sheets indisponible ({e}) — "
                  f"le dashboard HTML reste la source principale.")

    cache_occ = {cat_id: [] for cat_id in config.COMPOSANTS}
    cache_neuf = {cat_id: [] for cat_id in config.COMPOSANTS}

    print(f"[{maintenant_iso()}] Dashboard : ouvre {config.DASHBOARD_FILE} "
          f"dans ton navigateur (F5 pour rafraîchir). Ctrl+C pour arrêter.\n")

    while True:
        au_moins_une_maj = False

        # ---------- OCCASION : catégories dues ----------
        for cat_id in config.COMPOSANTS:
            prochaine = data["prochaine_verif"].get(cat_id)
            if prochaine and datetime.fromisoformat(prochaine) > maintenant():
                continue

            enrichis, bloque, _ = collecter_occasion(cat_id, sessions, data)
            cache_occ[cat_id] = enrichis
            au_moins_une_maj = True

            base = config.COMPOSANTS[cat_id]["frequence"]
            gerer_blocage(data, cat_id, bloque, base)
            freq = data["frequences_actuelles"].get(cat_id, base)
            data["prochaine_verif"][cat_id] = (
                maintenant() + timedelta(seconds=freq)).isoformat(timespec="seconds")

            rouges = sum(1 for l in enrichis if l.get("alerte") == "rouge")
            print(f"[{maintenant_iso()}] {config.COMPOSANTS[cat_id]['label']} : "
                  f"{len(enrichis)} annonces occasion, {rouges} en alerte rouge.")

        # ---------- NEUF : toutes les 6 h ----------
        pn = data.get("prochaine_verif_neuf")
        if pn is None or datetime.fromisoformat(pn) <= maintenant():
            print(f"[{maintenant_iso()}] Rafraîchissement des prix NEUF "
                  f"(GPUTracker + Idealo + PCC)...")
            try:
                cache_neuf = collecter_neuf_toutes_categories(sessions)
            except Exception as e:
                print(f"[{maintenant_iso()}] Erreur neuf : {e}")
            data["prochaine_verif_neuf"] = (
                maintenant() + timedelta(seconds=config.FREQUENCE_NEUF_SECONDES)
            ).isoformat(timespec="seconds")
            au_moins_une_maj = True

        # ---------- PC GAMER : toutes les 30 min ----------
        if config.PC_ACTIF:
            pp = data.get("prochain_scan_pc")
            if pp is None or datetime.fromisoformat(pp) <= maintenant():
                try:
                    bloque_pc = scanner_pc(sessions, data, cache_occ)
                    gerer_blocage(data, "_pc", bloque_pc, config.PC_FREQUENCE_SECONDES)
                except Exception as e:
                    print(f"[{maintenant_iso()}] Erreur scan PC : {e}")
                freq_pc = data["frequences_actuelles"].get("_pc", config.PC_FREQUENCE_SECONDES)
                data["prochain_scan_pc"] = (
                    maintenant() + timedelta(seconds=freq_pc)).isoformat(timespec="seconds")
                au_moins_une_maj = True

        # ---------- HISTORIQUE + DASHBOARD + BACKUPS ----------
        if au_moins_une_maj:
            occ_flat = [l for ls in cache_occ.values() for l in ls]
            neuf_flat = [l for ls in cache_neuf.values() for l in ls]
            dashboard_export.enregistrer_cycle(data, occ_flat, neuf_flat)

            try:
                paquet = dashboard_export.construire_donnees(data, cache_occ, cache_neuf)
                dashboard_export.generer_dashboard(paquet)
            except Exception as e:
                print(f"[{maintenant_iso()}] Avertissement dashboard : {e}")

            if classeur is not None:
                try:
                    sheets_export.ecrire_brut_occasion(classeur, cache_occ)
                    sheets_export.ecrire_brut_neuf(classeur, cache_neuf)
                except Exception as e:
                    print(f"[{maintenant_iso()}] Avertissement Google Sheets : {e}")

            try:
                excel_export.generer_backup(cache_occ)
            except Exception as e:
                print(f"[{maintenant_iso()}] Avertissement backup Excel : {e}")

            sauvegarder_historique(data)

        time.sleep(TICK_SECONDES)


if __name__ == "__main__":
    run()
