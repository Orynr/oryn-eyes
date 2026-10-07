"""Teste filters.py et analysis.py avec des données simulées."""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import filters
import analysis

echecs = []

def check(label, condition):
    status = "OK" if condition else "FAIL"
    if not condition:
        echecs.append(label)
    print(f"[{status}] {label}")


# ==================================================================
# FILTERS — matchers par catégorie
# ==================================================================
print("=== match_cpu_amd ===")
check("Ryzen 5 3600 -> True", filters.match_cpu_amd("AMD Ryzen 5 3600 comme neuf"))
check("Ryzen 5 5600X -> True", filters.match_cpu_amd("Ryzen 5 5600X boite"))
check("Ryzen 7 2700X -> True", filters.match_cpu_amd("Ryzen 7 2700X"))
check("Ryzen 5 1600 (gen 1, hors range) -> False", not filters.match_cpu_amd("Ryzen 5 1600"))
check("Ryzen 3 3200G (mauvaise gamme) -> False", not filters.match_cpu_amd("Ryzen 3 3200G"))
check("RAM 3600 MHz -> False (pas un CPU)", not filters.match_cpu_amd("Kit RAM 3600 MHz Corsair"))

print("\n=== match_cpu_intel ===")
check("i5-9600K -> True", filters.match_cpu_intel("Intel Core i5-9600K"))
check("i7-12700K -> True", filters.match_cpu_intel("Core i7-12700K neuf"))
check("i9-14900K -> True", filters.match_cpu_intel("i9 14900K"))
check("i5-8400 (gen 8, hors range) -> False", not filters.match_cpu_intel("Core i5-8400"))
check("i3-10100 (mauvaise gamme) -> False", not filters.match_cpu_intel("Core i3-10100"))

print("\n=== match_gpu ===")
check("RTX 3060 -> True", filters.match_gpu("RTX 3060 12Go"))
check("RTX 3070 Ti -> True", filters.match_gpu("RTX 3070 Ti"))
check("RTX 4070 -> True", filters.match_gpu("RTX 4070 neuve"))
check("RTX 2080 -> True", filters.match_gpu("RTX 2080 Super"))
check("RTX 3090 (hors range 3000) -> False", not filters.match_gpu("RTX 3090"))
check("RTX 4080 (hors range 4000) -> False", not filters.match_gpu("RTX 4080"))
check("GTX 1660 (pas RTX) -> False", not filters.match_gpu("GTX 1660 Super"))

print("\n=== match_ram ===")
check("DDR4 16Go (2x8Go) -> True", filters.match_ram("Kit RAM DDR4 16Go (2x8Go) 3200MHz"))
check("DDR4 8Go simple -> True", filters.match_ram("Barrette DDR4 8Go"))
check("DDR4 4Go (trop petit) -> False", not filters.match_ram("DDR4 4Go"))
check("DDR4 8Go (2x4Go, chaque barrette trop petite) -> False",
      not filters.match_ram("DDR4 8Go (2x4Go)"))
check("DDR3 8Go (mauvaise génération) -> False", not filters.match_ram("DDR3 8Go"))

print("\n=== match_cm_amd / match_cm_intel ===")
check("Carte mère B550 -> True (AMD)", filters.match_cm_amd("Asus B550-F Gaming"))
check("Carte mère Z690 -> True (Intel)", filters.match_cm_intel("MSI Z690 Tomahawk"))
check("Carte mère B550 -> False (matcher Intel)", not filters.match_cm_intel("Asus B550-F Gaming"))

print("\n=== match_stockage ===")
check("SSD NVMe 500Go -> True", filters.match_stockage("SSD NVMe 500Go Samsung"))
check("HDD 2To -> True", filters.match_stockage("Disque dur HDD 2To Seagate"))
check("SSD NVMe 1To (hors range 256-512) -> False", not filters.match_stockage("SSD NVMe 1To"))
check("HDD 500Go (hors range 1-2To) -> False", not filters.match_stockage("HDD 500Go"))

print("\n=== match_alimentation ===")
check("650W -> True", filters.match_alimentation("Alimentation Corsair 650W"))
check("450W (hors range) -> False", not filters.match_alimentation("Alimentation 450W"))
check("900W (hors range) -> False", not filters.match_alimentation("Alimentation 900W"))

# ==================================================================
# FILTERS — détection de lots
# ==================================================================
print("\n=== identifier_modele ===")
check("Ryzen 5 3600 -> 'Ryzen 5 3600'",
      filters.identifier_modele("cpu_amd", "AMD Ryzen 5 3600 neuf") == "Ryzen 5 3600")
check("Ryzen 5 5600X -> 'Ryzen 5 5600X'",
      filters.identifier_modele("cpu_amd", "Ryzen 5 5600X") == "Ryzen 5 5600X")
check("RTX 3070 Ti -> contient 'RTX3070' et 'TI'",
      "3070" in filters.identifier_modele("gpu", "RTX 3070 Ti").replace(" ", ""))
check("Carte mère B550 -> 'B550'",
      filters.identifier_modele("cm_amd", "Asus B550-F Gaming") == "B550")
check("DDR4 16Go(2x8) -> 'DDR4 16Go'",
      filters.identifier_modele("ram", "Kit DDR4 16Go (2x8Go)") == "DDR4 16Go")
check("650W -> '650W'",
      filters.identifier_modele("alimentation", "Alim Corsair 650W") == "650W")
check("Modèle non reconnu -> None",
      filters.identifier_modele("cpu_amd", "Un vieux clavier") is None)

print("\n=== detecter_lot ===")
r1 = filters.detecter_lot("AMD Ryzen 5 3600 seul", "cpu_amd")
check("CPU seul -> normal", r1["type"] == "normal" and r1["quantite"] == 1)

r2 = filters.detecter_lot("Lot de 3 Ryzen 5 3600", "cpu_amd")
check("Lot de 3 CPU identiques -> lot_gros qty=3",
      r2["type"] == "lot_gros" and r2["quantite"] == 3)

r3 = filters.detecter_lot("Ryzen 5 3600 + carte mere B450 + ventirad", "cpu_amd")
check("CPU + carte mère + ventirad -> lot_parasite",
      r3["type"] == "lot_parasite")

r4 = filters.detecter_lot("3x DDR4 8Go", "ram")
check("3x RAM identiques -> lot_gros qty=3",
      r4["type"] == "lot_gros" and r4["quantite"] == 3)


# ==================================================================
# ANALYSIS — stats de base
# ==================================================================
print("\n=== calculer_stats / mediane ===")
prix = [25, 30, 35, 40, 45, 48, 55]
s = analysis.calculer_stats(prix)
check("médiane impaire correcte", analysis.mediane(prix) == 40)
check("min correct", s["min"] == 25)
check("max correct", s["max"] == 55)
check("count correct", s["count"] == 7)

prix_pair = [10, 20, 30, 40]
check("médiane paire = moyenne des 2 centraux", analysis.mediane(prix_pair) == 25)

check("stats sur liste vide -> None propre", analysis.calculer_stats([])["mediane"] is None)

print("\n=== pourcentage_vs_mediane / palier_alerte ===")
med = 100
check("pct -30 -> rouge", analysis.palier_alerte(analysis.pourcentage_vs_mediane(70, med)) == "rouge")
check("pct -20 -> orange", analysis.palier_alerte(analysis.pourcentage_vs_mediane(80, med)) == "orange")
check("pct -5 -> vert", analysis.palier_alerte(analysis.pourcentage_vs_mediane(95, med)) == "vert")
check("pct +10 -> gris", analysis.palier_alerte(analysis.pourcentage_vs_mediane(110, med)) == "gris")
check("pct +20 -> masque", analysis.palier_alerte(analysis.pourcentage_vs_mediane(120, med)) == "masque")
check("doit_etre_affiche False si masqué", not analysis.doit_etre_affiche(20))
check("doit_etre_affiche True si gris", analysis.doit_etre_affiche(10))

print("\n=== marge_estimee ===")
m = analysis.marge_estimee(100, 60)  # médiane 100, achat 60, frais 12 (config)
check(f"marge = médiane - prix - frais ({m})", m == 100 - 60 - 12)

print("\n=== valeur_marche ===")
prix2 = [40, 45, 50, 55, 60, 200]  # 200 = outlier très au-dessus
med2 = analysis.mediane(prix2)
vm = analysis.valeur_marche(prix2, med2)
check("sous_mediane <= total", vm["sous_mediane"] <= vm["total"])
check("sous_seuil <= total", vm["sous_seuil"] <= vm["total"])
check("total = somme complète (avec l'outlier)", vm["total"] == sum(prix2))

print("\n=== ohlc_quotidien ===")
obs = [
    {"horodatage": "2026-08-18T09:00:00", "prix": 50},
    {"horodatage": "2026-08-18T15:00:00", "prix": 45},
    {"horodatage": "2026-08-18T20:00:00", "prix": 48},
    {"horodatage": "2026-08-19T10:00:00", "prix": 47},
    {"horodatage": "2026-08-19T18:00:00", "prix": 42},
]
bougies = analysis.ohlc_quotidien(obs)
check("2 jours de bougies", len(bougies) == 2)
j1 = bougies[0]
check("jour 1 ouverture = premier prix vu", j1["ouverture"] == 50)
check("jour 1 cloture = dernier prix vu", j1["cloture"] == 48)
check("jour 1 haut = max", j1["haut"] == 50)
check("jour 1 bas = min", j1["bas"] == 45)

print("\n=== vitesse_rotation_moyenne ===")
hist = [
    {"premiere_vue": "2026-08-18T09:00:00", "derniere_vue": "2026-08-18T15:00:00"},  # 6h
    {"premiere_vue": "2026-08-17T09:00:00", "derniere_vue": "2026-08-19T09:00:00"},  # 48h
]
vr = analysis.vitesse_rotation_moyenne(hist)
check(f"moyenne 27h ({vr})", vr == 27.0)
check("liste vide -> None", analysis.vitesse_rotation_moyenne([]) is None)

print("\n=== deals_du_mois ===")
from datetime import datetime
ref = datetime(2026, 8, 20)
deals = [
    {"date": "2026-08-01T10:00:00", "pct": -35},  # rouge, dans les 30j
    {"date": "2026-08-10T10:00:00", "pct": -40},  # rouge, dans les 30j
    {"date": "2026-08-15T10:00:00", "pct": -10},  # vert, pas compté
    {"date": "2026-06-01T10:00:00", "pct": -50},  # rouge mais trop vieux
]
dm = analysis.deals_du_mois(deals, aujourdhui=ref)
check(f"2 deals rouges comptés ({dm['count']})", dm["count"] == 2)
check("fréquence = 15 jours", dm["frequence_jours"] == 15.0)

print("\n=== prix_unitaire ===")
check("lot de 3 à 90€ -> 30€/unité", analysis.prix_unitaire(90, 3) == 30)
check("pas de lot -> prix inchangé", analysis.prix_unitaire(50, 1) == 50)


print("\n" + "=" * 50)
if echecs:
    print(f"ECHECS ({len(echecs)}):")
    for e in echecs:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("TOUT PASSE.")
