"""
Tests des parsers de scrapers sur des fixtures HTML reproduisant les
structures RÉELLES vérifiées (web_fetch pendant le développement).
Aucun appel réseau.
"""

import sys
sys.path.insert(0, ".")

import scraper_gputracker as gpt
import scraper_mon7up as m7
import scraper_idealo as ide
import scraper_pccomponentes as pcc
import scraper_leboncoin as lbc

OK = 0
FAIL = 0

def check(nom, cond):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print(f"  ÉCHEC : {nom}")


# ================= GPUTRACKER =================
HTML_GPT = """
<div class="offers">
<a href="https://www.gputracker.eu/si-click/1/4591282/gigabyte-geforce-rtx-3070-gaming">
Gigabyte GeForce RTX 3070 GAMING OC 8G LHR-Seconde Vie-Etat Satisfaisant grosbill.com425 €En stock Dernière mise à jour: il y a 12 heures</a>
<a href="/fr/offer/4591282/gigabyte">Détails de l'offre</a>
<a href="https://www.gputracker.eu/si-click/1/4758020/gigabyte-aorus">
Gigabyte AORUS GeForce RTX 3070 MASTER 8 Go GDDR6 Rév 2.0 pccomponentes.fr455 €En stock</a>
<a href="https://www.gputracker.eu/si-click/1/4657183/evga-rtx3070">
EVGA GeForce RTX 3070 FTW3 ULTRA LHR Grafikkarte alternate.de699 €Pas en stock Dernière mise à jour: il y a 2 heures</a>
<a href="https://www.gputracker.eu/si-click/1/1674894/zotac-prix-mille">
Zotac RTX 3070 Bundle special amazon.de1.505,99 €En stock</a>
</div>
"""
offres = gpt._parser_bs4(HTML_GPT)
check("GPUTracker : 4 offres parsées", len(offres) == 4)
o1 = next(o for o in offres if o["id"] == "gpt_4591282")
check("GPUTracker : prix 425", o1["prix"] == 425.0)
check("GPUTracker : magasin grosbill.com", o1["magasin"] == "grosbill.com")
check("GPUTracker : en stock", o1["en_stock"] is True)
check("GPUTracker : titre nettoyé", o1["titre"].startswith("Gigabyte GeForce RTX 3070"))
o3 = next(o for o in offres if o["id"] == "gpt_4657183")
check("GPUTracker : 'Pas en stock' détecté", o3["en_stock"] is False)
o4 = next(o for o in offres if o["id"] == "gpt_1674894")
check("GPUTracker : prix 1.505,99 -> 1505.99", o4["prix"] == 1505.99)
offres_rx = gpt._parser_regex(HTML_GPT)
check("GPUTracker : parser regex = même résultat", len(offres_rx) == 4)

# ================= MON7UP =================
HTML_M7 = """
<div class="annonces">
<a href="/annonce/msi-geforce-rtx-4090-suprim-x-24g-3387">
MSI GeForce RTX 4090 SUPRIM X 24G Occasion 1100 € Nice</a>
<a href="/annonce/rtx-3070-founders-edition-2214">
RTX 3070 Founders Edition Occasion 310 € Lyon</a>
<a href="https://www.mon7up.fr/annonce/ryzen-5-5600-neuf-887">
Ryzen 5 5600 Neuf 105 € Paris</a>
<a href="/autre-page">Pas une annonce</a>
</div>
"""
anns = m7._parser_bs4(HTML_M7)
check("Mon7up : 3 annonces", len(anns) == 3)
a1 = next(a for a in anns if a["id"] == "m7_2214")
check("Mon7up : prix 310", a1["prix"] == 310.0)
check("Mon7up : titre sans 'Occasion'", "Occasion" not in a1["titre"]
      and "RTX 3070" in a1["titre"])
check("Mon7up : URL absolue", a1["url"].startswith("https://www.mon7up.fr/annonce/"))
anns_rx = m7._parser_regex(HTML_M7)
check("Mon7up : parser regex = 3 annonces", len(anns_rx) == 3)

# ================= IDEALO =================
HTML_IDE = """
<div class="resultlist">
 <div class="offerList-item">
  <a href="/prix/201234567/nvidia-geforce-rtx-3070.html">MSI GeForce RTX 3070 Ventus 2X</a>
  <div class="price">à partir de 449,00 €</div>
 </div>
 <div class="offerList-item">
  <a href="/prix/201234568/amd-ryzen-5-5600.html">AMD Ryzen 5 5600</a>
  <div class="price">à partir de 128,90 €</div>
 </div>
</div>
"""
prods = ide._parser(HTML_IDE)
check("Idealo : 2 produits", len(prods) == 2)
p1 = next(p for p in prods if p["id"] == "ide_201234567")
check("Idealo : prix 449.00", p1["prix"] == 449.0)
check("Idealo : titre", "RTX 3070" in p1["titre"])
check("Idealo : URL absolue", p1["url"].startswith("https://www.idealo.fr/prix/"))

# ================= PC COMPONENTES =================
HTML_PCC = """
<div>
<a href="/zotac-gaming-geforce-rtx-3070-twin-edge-lhr-8-go-gddr6">
Zotac Gaming Geforce RTX 3070 Twin Edge LHR 8 Go GDDR6 Reconditionné 455,21€</a>
<a href="/gigabyte-aorus-geforce-rtx-3070-master-8-go">
Gigabyte AORUS GeForce RTX 3070 MASTER 8 Go GDDR6 649,90€</a>
<a href="/search/?query=autre">lien de recherche 12€</a>
</div>
"""
prods_pcc = pcc._parser(HTML_PCC)
check("PCC : 2 produits (lien search exclu)", len(prods_pcc) == 2)
r1 = next(p for p in prods_pcc if "zotac" in p["id"])
check("PCC : reconditionné détecté", r1["reconditionne"] is True)
check("PCC : prix 455.21", r1["prix"] == 455.21)
n1 = next(p for p in prods_pcc if "gigabyte" in p["id"])
check("PCC : neuf détecté", n1["reconditionne"] is False)
check("PCC : prix 649.90", n1["prix"] == 649.9)

# ================= LEBONCOIN (extraction annonce API) =================
AD = {
    "list_id": 2901882345,
    "subject": "PC Gamer RTX 3060 Ryzen 5 5600",
    "body": "PC monté par mes soins, 16go ram, ssd 512go",
    "price": [650],
    "url": "https://www.leboncoin.fr/ad/informatique/2901882345",
    "location": {"region_name": "Ile-de-France", "city": "Pantin"},
    "attributes": [{"key": "shippable", "value": "true"}],
}
l = lbc._extraire(AD)
check("LBC : id préfixé", l["id"] == "lbc_2901882345")
check("LBC : prix liste [650] -> 650", l["prix"] == 650.0)
check("LBC : région IDF", l["region"] == "Ile-de-France")
check("LBC : livraison via attribut shippable", l["livraison"] == "Livraison")
AD2 = {**AD, "list_id": 1, "price": {"value": 420}, "attributes": [],
       "options": {"shipping": True}}
l2 = lbc._extraire(AD2)
check("LBC : prix dict -> 420", l2["prix"] == 420.0)
check("LBC : livraison via options.shipping", l2["livraison"] == "Livraison")
AD3 = {**AD, "list_id": 2, "price": 300, "attributes": [], "shippable": False}
l3 = lbc._extraire(AD3)
check("LBC : prix nu -> 300", l3["prix"] == 300.0)
check("LBC : main propre via shippable=False", l3["livraison"] == "Main propre")
AD4 = {**AD, "list_id": 3, "price": None}
check("LBC : prix None -> annonce ignorée", lbc._extraire(AD4) is None)

print(f"\n{OK} OK, {FAIL} échecs")
sys.exit(1 if FAIL else 0)
