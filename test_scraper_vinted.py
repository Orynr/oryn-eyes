"""
Teste collecter_categorie() sans réseau réel : on remplace
scraper_vinted.rechercher() par une fausse fonction qui renvoie des
items déjà préparés, comme si Vinted avait répondu.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import scraper_vinted

echecs = []

def check(label, condition):
    status = "OK" if condition else "FAIL"
    if not condition:
        echecs.append(label)
    print(f"[{status}] {label}")


FAUX_ITEMS = {
    "ryzen 5": [
        {"id": 1, "title": "AMD Ryzen 5 3600 comme neuf", "price": {"amount": "45.0"},
         "photo": {"url": "http://x/1.jpg"}, "url": "http://vinted/1",
         "user": {"feedback_reputation": 0.96}},
        {"id": 2, "title": "Ryzen 5 3600 + carte mere B450 + ventirad", "price": {"amount": "90.0"},
         "photo": None, "url": "http://vinted/2", "user": {}},  # lot parasite -> exclu
        {"id": 3, "title": "Kit RAM DDR4 16Go 3600 MHz", "price": {"amount": "40.0"},
         "photo": None, "url": "http://vinted/3", "user": {}},  # faux positif -> exclu par matcher
        {"id": 4, "title": "Lot de 3 Ryzen 5 3600", "price": {"amount": "90.0"},
         "photo": None, "url": "http://vinted/4", "user": {}},  # lot gros -> gardé
    ],
    "ryzen 7": [
        {"id": 5, "title": "Ryzen 7 3700X TBE", "price": 65,
         "photo": None, "url": "http://vinted/5", "user": {}},
        {"id": 1, "title": "AMD Ryzen 5 3600 comme neuf (doublon)", "price": {"amount": "45.0"},
         "photo": None, "url": "http://vinted/1", "user": {}},  # même id que ci-dessus -> dédoublonné
    ],
}


def fausse_recherche(session, terme, par_page=50):
    return FAUX_ITEMS.get(terme, []), None


# monkeypatch : on remplace la vraie fonction réseau
scraper_vinted.rechercher = fausse_recherche

listings, bloque = scraper_vinted.collecter_categorie("cpu_amd", session=None)

check("pas de blocage signalé", bloque is False)
# ryzen 5: id1 (ok), id2 (lot parasite, exclu), id3 (faux positif RAM, exclu),
#          id4 (lot gros, ok) / ryzen 7: id5 (ok), id1 (doublon, déjà vu)
# -> 3 annonces uniques valides : 1, 4, 5
check("3 annonces valides après filtrage/dédoublonnage", len(listings) == 3)

ids = {l["id"] for l in listings}
check("id 2 (lot parasite) exclu", 2 not in ids)
check("id 3 (RAM, faux positif) exclu", 3 not in ids)
check("id 1 présent une seule fois malgré le doublon", list(l["id"] for l in listings).count(1) == 1)

lot4 = next(l for l in listings if l["id"] == 4)
check("id 4 détecté comme lot_gros x3", lot4["lot_type"] == "lot_gros" and lot4["lot_quantite"] == 3)

l1 = next(l for l in listings if l["id"] == 1)
check("prix extrait correctement (dict amount)", l1["prix"] == 45.0)

l5 = next(l for l in listings if l["id"] == 5)
check("prix extrait correctement (nombre direct)", l5["prix"] == 65)


print("\n" + "=" * 50)
if echecs:
    print(f"ECHECS ({len(echecs)}):")
    for e in echecs:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("TOUT PASSE.")
