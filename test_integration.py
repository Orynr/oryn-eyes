"""
Test d'intégration : simule 3 jours de cycles avec des données réalistes
(sans réseau), vérifie l'historique, la génération du dashboard, et que
le fichier généré contient bien les données injectées.
"""

import json
import os
import sys
sys.path.insert(0, ".")
from datetime import datetime, timedelta

import config
config.DATA_FILE = "test_historique.json"
config.DASHBOARD_FILE = "test_dashboard_genere.html"

import analysis
import pc_analyzer
import ventes_tracker
import dashboard_export
import sheets_export
import main as main_mod

OK = 0
FAIL = 0

def check(nom, cond):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print(f"  ÉCHEC : {nom}")

# nettoyage
for f in (config.DATA_FILE, config.DASHBOARD_FILE):
    if os.path.exists(f):
        os.remove(f)

# ---------- données factices réalistes ----------
def annonces_occ(jour_offset):
    base = [
        ("v1", "RTX 3060 Ventus 12Go", 195, "RTX 3060", "Vinted"),
        ("v2", "RTX 3060 Gaming OC", 215, "RTX 3060", "Vinted"),
        ("l1", "RTX 3060 comme neuve", 185, "RTX 3060", "Leboncoin"),
        ("m1", "MSI RTX 3060", 205, "RTX 3060", "Mon7up"),
        ("l9", "RTX 3060 phoenix", 129, "RTX 3060", "Leboncoin"),  # rouge -35%
        ("v3", "Ryzen 5 5600 box", 92, "Ryzen 5 5600", "Vinted"),
        ("l2", "Ryzen 5 5600 + ventirad stock", 98, "Ryzen 5 5600", "Leboncoin"),
        ("v4", "RAM DDR4 16Go 3200", 33, "DDR4 16Go", "Vinted"),
        ("v5", "SSD SATA 512Go", 29, "SSD SATA 512Go", "Vinted"),
        ("l3", "Alim 650W 80+ gold", 41, "650W", "Leboncoin"),
        ("m2", "Carte mère B550 Tomahawk", 66, "B550", "Mon7up"),
    ]
    out = []
    for id_, titre, prix, modele, plat in base:
        out.append({
            "id": f"{id_}_{jour_offset}", "titre": titre,
            "prix": prix + jour_offset * 2,  # léger drift de prix
            "modele": modele, "plateforme": plat, "url": "#",
            "etat": "Très bon état", "score_vendeur": 4.5,
            "lot_type": "normal", "lot_quantite": 1,
            "region": "Ile-de-France" if plat == "Leboncoin" else "",
            "livraison": "Livraison",
        })
    return out

def annonces_neuf():
    return [
        {"id": "g1", "titre": "RTX 3060 neuve", "prix": 289, "modele": "RTX 3060",
         "plateforme": "ldlc.com", "url": "#", "etat": "Neuf", "score_vendeur": None,
         "lot_type": "normal", "lot_quantite": 1, "region": "", "livraison": ""},
        {"id": "g2", "titre": "RTX 3060", "prix": 305, "modele": "RTX 3060",
         "plateforme": "amazon.fr", "url": "#", "etat": "Neuf", "score_vendeur": None,
         "lot_type": "normal", "lot_quantite": 1, "region": "", "livraison": ""},
        {"id": "i1", "titre": "Ryzen 5 5600", "prix": 132, "modele": "Ryzen 5 5600",
         "plateforme": "Idealo (min marché)", "url": "#", "etat": "Neuf",
         "score_vendeur": None, "lot_type": "normal", "lot_quantite": 1,
         "region": "", "livraison": ""},
    ]

# ---------- simulation de 3 jours ----------
data = main_mod.charger_historique()
check("historique initialisé", "observations" in data and "ventes_pc" in data)

t0 = datetime(2026, 8, 18, 9, 0, 0)
cache_occ = {}
cache_neuf = {}

for jour in range(3):
    for h in (9, 15, 21):
        tnow = t0 + timedelta(days=jour, hours=h - 9)
        occ = sheets_export.enrichir_listings(annonces_occ(jour))
        neuf = sheets_export.enrichir_listings(annonces_neuf())
        cache_occ = {"gpu": [a for a in occ if "RTX" in (a["modele"] or "")],
                     "cpu_amd": [a for a in occ if "Ryzen" in (a["modele"] or "")],
                     "ram": [a for a in occ if "DDR4" in (a["modele"] or "")],
                     "stockage": [a for a in occ if "SSD" in (a["modele"] or "")],
                     "alimentation": [a for a in occ if a["modele"] == "650W"],
                     "cm_amd": [a for a in occ if a["modele"] == "B550"]}
        cache_neuf = {"gpu": [a for a in neuf if "RTX" in (a["modele"] or "")],
                      "cpu_amd": [a for a in neuf if "Ryzen" in (a["modele"] or "")]}
        # patch horodatage pour simuler les jours passés
        occ_flat = [l for ls in cache_occ.values() for l in ls]
        neuf_flat = [l for ls in cache_neuf.values() for l in ls]
        dashboard_export.enregistrer_cycle(data, occ_flat, neuf_flat)
        # réécrit le t des observations pour dater correctement
        for m, obs in data["observations"].items():
            for flux in obs.values():
                if flux:
                    flux[-1]["t"] = tnow.isoformat(timespec="seconds")

check("observations RTX 3060 accumulées",
      len(data["observations"].get("RTX 3060", {}).get("occasion", [])) == 9)
check("deals loggés (rouge -35% chaque jour = ids distincts)",
      len(data["deals_log"]) >= 3)
check("valeur marché par plateforme",
      "Vinted" in list(data["valeur_marche"]["RTX 3060"].values())[0])

# ---------- pipeline PC ----------
medianes = main_mod.medianes_pour_net(cache_occ)
check("médianes extraites pour le net", medianes.get("RTX 3060") is not None)

pc_annonces_scan = [
    {"id": "pcv1", "titre": "PC Gamer RTX 3060 Ryzen 5 5600 16Go", "prix": 620,
     "description": "", "gpu_marque": "nvidia", "gpu_modele": "RTX 3060",
     "cpu_marque": "amd", "cpu_modele": "Ryzen 5 5600",
     "plateforme": "Vinted", "url": "#", "region": "", "livraison": "Livraison"},
    {"id": "pcl1", "titre": "PC Gamer", "prix": 480,
     "description": "rtx 3060, ryzen 5 5600, 16go ram, ssd 512go, alim 650w, b550",
     "gpu_marque": "nvidia", "gpu_modele": "RTX 3060",
     "cpu_marque": "amd", "cpu_modele": "Ryzen 5 5600",
     "plateforme": "Leboncoin", "url": "#", "region": "Ile-de-France",
     "livraison": "Main propre"},
]
pc_vus = data["pc_annonces"]
for a in pc_annonces_scan:
    net_info = pc_analyzer.valeur_nette_pc(a["titre"], a["description"], medianes)
    net = net_info["net"] if net_info else None
    pc_vus[a["id"]] = {**{k: a[k] for k in ("id", "titre", "prix", "gpu_marque",
                          "gpu_modele", "cpu_marque", "cpu_modele", "plateforme",
                          "url", "region", "livraison")},
                       "net": net, "ecart": round(a["prix"] - net, 2) if net else None,
                       "premiere_vue": "2026-08-19T10:00:00"}

check("net calculé pour les 2 PC",
      all(v["net"] is not None for v in pc_vus.values()))
check("PC LBC à 480 est sous-évalué (écart négatif)",
      pc_vus["pcl1"]["ecart"] < 0)

# ventes : cycle 1 puis disparition de pcv1
etat = ventes_tracker.assurer_etat(data)
tv = datetime(2026, 8, 20, 9, 0, 0)
ventes_tracker.comparer_et_compter(etat, list(pc_vus.values()), tv)
ventes_tracker.comparer_et_compter(etat, [pc_vus["pcl1"]], tv + timedelta(hours=3))
check("vente Vinted comptée", etat["jour"]["ventes_vinted"] == 1)
check("vente nvidia comptée", etat["jour"]["ventes_nvidia"] == 1)

# ---------- construction paquet + génération ----------
paquet = dashboard_export.construire_donnees(data, cache_occ, cache_neuf)
check("paquet : annonces occasion", len(paquet["composants"]["occasion"]) == 11)
check("paquet : annonces neuf", len(paquet["composants"]["neuf"]) == 3)
check("paquet : bougies RTX 3060 (3 jours)",
      len(paquet["historique_prix"]["RTX 3060"]["occasion"]) == 3)
check("paquet : plateformes occasion RTX 3060 = 3",
      len(paquet["historique_plateformes"]["RTX 3060"]["occasion"]) == 3)
check("paquet : évolution marché présente",
      len(paquet["evolution_marche"]["RTX 3060"]) >= 1)
check("paquet : PC annonces = 2", len(paquet["pc"]["annonces"]) == 2)
check("paquet : ventes_jour contient le jour courant",
      len(paquet["pc"]["ventes_jour"]) >= 1
      and paquet["pc"]["ventes_jour"][-1]["vinted"] == 1)
check("paquet : brut_net rempli", len(paquet["pc"]["brut_net"]) == 1
      and paquet["pc"]["brut_net"][0]["brut"] == 550)
check("paquet : rotation dict", isinstance(paquet["rotation"], dict))
check("paquet : demo=False", paquet["demo"] is False)

chemin = dashboard_export.generer_dashboard(paquet)
check("dashboard généré", os.path.exists(chemin))
with open(chemin, encoding="utf-8") as f:
    contenu = f.read()
check("données injectées (pas null)", '"demo":false' in contenu)
check("annonce réelle dans le fichier", "RTX 3060 Ventus" in contenu)
check("placeholder remplacé une seule fois",
      contenu.count("/*__DATA__*/") == 1 and contenu.count("/*__FIN_DATA__*/") == 1)

# ---------- persistance ----------
main_mod.sauvegarder_historique(data)
data2 = main_mod.charger_historique()
check("historique persiste et recharge",
      len(data2["observations"]["RTX 3060"]["occasion"]) == 9)
check("json historique < 5 Mo",
      os.path.getsize(config.DATA_FILE) < 5_000_000)

print(f"\n{OK} OK, {FAIL} échecs")
sys.exit(1 if FAIL else 0)
