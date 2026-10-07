"""Tests de pc_analyzer et ventes_tracker (logique pure)."""

import sys
sys.path.insert(0, ".")
from datetime import datetime

import pc_analyzer as pa
import ventes_tracker as vt

OK = 0
FAIL = 0


def check(nom, cond):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print(f"  ÉCHEC : {nom}")


# ================= QUALIFICATION GPU =================
check("RTX 3060 qualifiant", pa.detecter_gpu("PC Gamer RTX 3060 12Go") == ("nvidia", "RTX 3060"))
check("RTX 3060 Ti qualifiant", pa.detecter_gpu("rtx3060ti") == ("nvidia", "RTX 3060 TI"))
check("RTX 4070 qualifiant", pa.detecter_gpu("GeForce RTX 4070 Super")[0] == "nvidia")
check("RTX 3050 exclu", pa.detecter_gpu("PC RTX 3050") == (None, None))
check("RTX 2080 exclu", pa.detecter_gpu("tour rtx 2080 ti") == (None, None))
check("RX 6700 XT qualifiant", pa.detecter_gpu("PC gamer RX 6700 XT") == ("amd", "RX 6700 XT"))
check("RX 5700 XT qualifiant", pa.detecter_gpu("config rx5700xt") == ("amd", "RX 5700 XT"))
check("RX 6500 XT exclu", pa.detecter_gpu("pc rx 6500 xt") == (None, None))
check("RX 6500 exclu", pa.detecter_gpu("pc rx 6500 4go") == (None, None))
check("RX 6600 qualifiant", pa.detecter_gpu("pc rx 6600") == ("amd", "RX 6600"))
check("RX 7900 XTX qualifiant", pa.detecter_gpu("rx 7900 xtx")[1] == "RX 7900 XTX")
check("pas de GPU", pa.detecter_gpu("PC bureautique i5") == (None, None))

# ================= QUALIFICATION CPU =================
check("Ryzen 5 5600 ok", pa.detecter_cpu("pc ryzen 5 5600") == ("amd", "Ryzen 5 5600"))
check("Ryzen 5 3600 ok", pa.detecter_cpu("Ryzen 5 3600") == ("amd", "Ryzen 5 3600"))
check("Ryzen 7 5800X3D ok", pa.detecter_cpu("ryzen 7 5800x3d")[1] == "Ryzen 7 5800X3D")
check("Ryzen 5 2600 exclu (pas dans la liste)", pa.detecter_cpu("ryzen 5 2600") == (None, None))
check("Ryzen 5 7600 exclu", pa.detecter_cpu("ryzen 5 7600") == (None, None))
check("i5-12400F ok", pa.detecter_cpu("core i5 12400f") == ("intel", "Core i5-12400F"))
check("i9-9900K ok (gen 9)", pa.detecter_cpu("i9 9900k") == ("intel", "Core i9-9900K"))
check("i7-8700K exclu (gen 8)", pa.detecter_cpu("i7 8700k") == (None, None))
check("i5-14600K ok", pa.detecter_cpu("i5-14600k")[0] == "intel")

# ================= QUALIFICATION PC (les DEUX requis) =================
q = pa.qualifier_pc("PC Gamer RTX 3060 Ryzen 5 5600 16Go")
check("PC complet qualifié", q["qualifie"] and q["gpu_marque"] == "nvidia" and q["cpu_marque"] == "amd")
q = pa.qualifier_pc("PC Gamer RTX 3060 16Go SSD")
check("GPU seul -> non qualifié", not q["qualifie"])
q = pa.qualifier_pc("PC Ryzen 5 5600 16Go")
check("CPU seul -> non qualifié", not q["qualifie"])
q = pa.qualifier_pc("PC Gamer", "Config : RX 6700 XT + i5 12400F + 32Go DDR4")
check("qualification via description", q["qualifie"] and q["gpu_marque"] == "amd")

# ================= DÉTECTION COMPOSANTS =================
check("RAM 16Go", pa.detecter_ram("PC avec 16 Go de RAM DDR4") == "DDR4 16Go")
check("RAM 2x8", pa.detecter_ram("ram 2x8go ddr4") == "DDR4 16Go")
check("RAM 32Go", pa.detecter_ram("32go ram") == "DDR4 32Go")
check("SSD 500Go", pa.detecter_stockage("ssd 500go") == "SSD SATA 512Go")
check("SSD NVMe 1To", pa.detecter_stockage("ssd nvme 1to") == "SSD NVMe 1To")
check("Alim 650W", pa.detecter_alimentation("alimentation 650w gold") == "650W")
check("Alim via contexte", pa.detecter_alimentation("650w 80+ bronze") == "650W")
check("CM B550", pa.detecter_carte_mere("carte mère B550m tomahawk") == "B550")

# ================= VALEUR NETTE =================
MEDIANES = {
    "RTX 3060": 210.0, "Ryzen 5 5600": 95.0, "DDR4 16Go": 32.0,
    "DDR4 32Go": 60.0, "SSD SATA 512Go": 28.0, "SSD NVMe 1To": 55.0,
    "650W": 40.0, "B550": 65.0, "550W": 35.0,
}
r = pa.valeur_nette_pc(
    "PC Gamer RTX 3060 Ryzen 5 5600",
    "16go ram ddr4, ssd 500go, alim 650w, carte mère b550", MEDIANES)
attendu = 210 + 95 + 32 + 28 + 40 + 65 + 50  # + boîtier forfait 50
check(f"net tout détecté = {attendu}", r and r["net"] == attendu)
check("détail GPU détecté", r["detail"]["gpu"]["source"] == "detecte")
check("détail CM détectée", r["detail"]["carte_mere"]["source"] == "detecte")

r2 = pa.valeur_nette_pc("PC Gamer RTX 3060 Ryzen 5 5600", "", MEDIANES)
# défauts : RAM 16Go médiane (32) + SSD 512 (28) + alim moyenne (40+35)/2=37.5 + CM 50 + boîtier 50
attendu2 = 210 + 95 + 32 + 28 + 37.5 + 50 + 50
check(f"net avec défauts = {attendu2}", r2 and r2["net"] == attendu2)
check("RAM par défaut", r2["detail"]["ram"]["source"] == "defaut")

r3 = pa.valeur_nette_pc("PC RTX 3050 i3", "", MEDIANES)
check("PC non qualifié -> None", r3 is None)

r4 = pa.valeur_nette_pc("PC RTX 3070 Ryzen 5 5600", "", MEDIANES)
check("GPU sans médiane -> None", r4 is None)

# ================= EST ANNONCE PC =================
check("titre pc gamer", pa.est_annonce_pc("PC Gamer complet RTX 3060"))
check("tour gamer", pa.est_annonce_pc("Tour gamer RGB"))
check("unité centrale", pa.est_annonce_pc("Unité centrale i5"))
check("carte seule non-PC", not pa.est_annonce_pc("Carte graphique RTX 3060 Ventus"))
check("PC via description", pa.est_annonce_pc("Config complète",
      "pc gamer avec rtx 3060 et ryzen 5 5600"))

# ================= VENTES TRACKER =================
data = {}
etat = vt.assurer_etat(data)
check("état initial créé", "snapshot" in etat and etat["jour"]["ventes_vinted"] == 0)

t0 = datetime(2026, 8, 20, 9, 0, 0)
annonces_t0 = [
    {"id": "a1", "plateforme": "Vinted", "gpu_marque": "nvidia", "prix": 700,
     "premiere_vue": "2026-08-19T10:00:00", "region": "", "livraison": "Livraison", "titre": "PC 1"},
    {"id": "a2", "plateforme": "Leboncoin", "gpu_marque": "amd", "prix": 650,
     "premiere_vue": "2026-08-18T10:00:00", "region": "Ile-de-France", "livraison": "?", "titre": "PC 2"},
    {"id": "a3", "plateforme": "Leboncoin", "gpu_marque": "nvidia", "prix": 900,
     "premiere_vue": "2026-07-01T10:00:00", "region": "Bretagne", "livraison": "Main propre", "titre": "PC 3"},
]
check("cycle dû au départ", vt.cycle_du(etat, 3 * 3600, t0))
vt.comparer_et_compter(etat, annonces_t0, t0)
check("snapshot rempli", len(etat["snapshot"]) == 3)
check("pas de vente au 1er cycle", etat["jour"]["ventes_vinted"] == 0)

t1 = datetime(2026, 8, 20, 12, 0, 0)
check("cycle dû après 3h", vt.cycle_du(etat, 3 * 3600, t1))
check("cycle PAS dû après 1h", not vt.cycle_du(etat, 3 * 3600, datetime(2026, 8, 20, 10, 0, 0)))
# a1 (Vinted/nvidia, récent) et a3 (LBC/nvidia, vieux de 50j) disparaissent
disparues = vt.comparer_et_compter(etat, [annonces_t0[1]], t1)
check("2 disparues détectées", len(disparues) == 2)
check("vente Vinted comptée", etat["jour"]["ventes_vinted"] == 1)
check("vente LBC comptée", etat["jour"]["ventes_leboncoin"] == 1)
check("2 ventes nvidia", etat["jour"]["ventes_nvidia"] == 2)
check("0 vente amd", etat["jour"]["ventes_amd"] == 0)
check("1 seule vente 'estimée' (a3 trop vieille)", etat["jour"]["ventes_estimees"] == 1)
check("2 prix vendus enregistrés", len(etat["jour"]["prix_vendus"]) == 2)

# reset 24h : passage au jour suivant
t2 = datetime(2026, 8, 21, 12, 5, 0)
vt.comparer_et_compter(etat, [], t2)
check("jour archivé", len(etat["historique_jours"]) == 1)
h = etat["historique_jours"][0]
check("archive date 2026-08-20", h["date"] == "2026-08-20")
check("archive vinted=1 lbc=2 (a2 disparue au cycle t2 compte pour le 20? non, le 21)",
      h["vinted"] == 1 and h["nvidia"] == 2)
check("compteurs remis à zéro puis a2 comptée le 21",
      etat["jour"]["ventes_leboncoin"] == 1 and etat["jour"]["ventes_amd"] == 1)

# bougies
hist = [
    {"date": "2026-08-18", "prix_ouverture": 700, "prix_cloture": 720, "prix_min": 690, "prix_max": 740},
    {"date": "2026-08-19", "prix_ouverture": 720, "prix_cloture": 710, "prix_min": 700, "prix_max": 730},
    {"date": "2026-08-24", "prix_ouverture": 730, "prix_cloture": 750, "prix_min": 725, "prix_max": 760},
]
bj = vt.bougies_jour(hist)
check("3 bougies jour", len(bj) == 3 and bj[0]["o"] == 700)
bs = vt.bougies_semaine(hist)
check("2 bougies semaine (S34, S35)", len(bs) == 2)
check("semaine 1 : h=740 l=690 c=710", bs[0]["h"] == 740 and bs[0]["l"] == 690 and bs[0]["c"] == 710)

print(f"\n{OK} OK, {FAIL} échecs")
sys.exit(1 if FAIL else 0)
