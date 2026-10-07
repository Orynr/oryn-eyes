"""
Tests de main.py v2 : persistance, ralentissement/rétablissement,
suivi des disparitions dans collecter_occasion (plateformes désactivées
pour ne faire aucun appel réseau).
"""

import os
import sys
sys.path.insert(0, ".")

import config
config.DATA_FILE = "test_historique_main.json"
# Désactive tout le réseau : collecter_occasion ne touche alors que l'historique
for p in config.PLATEFORMES_OCCASION.values():
    p["actif"] = False

import main

OK = 0
FAIL = 0

def check(nom, cond):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print(f"  ÉCHEC : {nom}")

if os.path.exists(config.DATA_FILE):
    os.remove(config.DATA_FILE)

# ---------- chargement / structure ----------
data = main.charger_historique()
check("structure vus par catégorie", set(data["vus"]) == set(config.COMPOSANTS))
check("fréquences initiales", data["frequences_actuelles"]["gpu"] == 300)
check("structures dashboard présentes", "observations" in data and "ventes_pc" in data)

# ---------- ralentissement + rétablissement progressif ----------
main.gerer_blocage(data, "gpu", True, 300)
check("1er blocage : pas encore ralenti", data["frequences_actuelles"]["gpu"] == 300)
main.gerer_blocage(data, "gpu", True, 300)
check("2e blocage : 300 -> 600", data["frequences_actuelles"]["gpu"] == 600)
main.gerer_blocage(data, "gpu", True, 300)
main.gerer_blocage(data, "gpu", True, 300)
check("4e blocage : 600 -> 1200", data["frequences_actuelles"]["gpu"] == 1200)
for _ in range(10):
    main.gerer_blocage(data, "gpu", True, 300)
check("plafond respecté (3600)", data["frequences_actuelles"]["gpu"] == 3600)
main.gerer_blocage(data, "gpu", False, 300)
check("succès : rétablissement progressif 3600 -> 1800",
      data["frequences_actuelles"]["gpu"] == 1800)
main.gerer_blocage(data, "gpu", False, 300)
main.gerer_blocage(data, "gpu", False, 300)
main.gerer_blocage(data, "gpu", False, 300)
check("retour à la base (300), jamais en dessous",
      data["frequences_actuelles"]["gpu"] == 300)

# ---------- suivi disparitions (aucune plateforme active = 0 annonce) ----------
data["vus"]["gpu"]["fake1"] = {
    "modele": "RTX 3060", "prix": 200, "plateforme": "Vinted",
    "premiere_vue": "2026-08-19T10:00:00", "derniere_vue": "2026-08-19T12:00:00"}
enrichis, bloque, disparues = main.collecter_occasion("gpu", {}, data)
check("0 annonce (plateformes off)", enrichis == [])
check("annonce fantôme détectée disparue", len(disparues) == 1
      and disparues[0]["modele"] == "RTX 3060")
check("rotation enregistrée (2h)",
      data["rotation_duree"]["RTX 3060"] == [2.0])

# ---------- médianes pour le net ----------
cache = {"gpu": [{"modele": "RTX 3060", "prix": 200, "prix_unitaire": 200,
                   "alerte": "vert"},
                  {"modele": "RTX 3060", "prix": 220, "prix_unitaire": 220,
                   "alerte": "gris"},
                  {"modele": "RTX 3060", "prix": 500, "prix_unitaire": 500,
                   "alerte": "masque"}]}
med = main.medianes_pour_net(cache)
check("médiane net ignore les masqués", med["RTX 3060"] == 210)

# ---------- persistance ----------
main.sauvegarder_historique(data)
data2 = main.charger_historique()
check("rechargement fidèle", data2["rotation_duree"]["RTX 3060"] == [2.0])

os.remove(config.DATA_FILE)
print(f"\n{OK} OK, {FAIL} échecs")
sys.exit(1 if FAIL else 0)
