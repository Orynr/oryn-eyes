import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import scraper_ebay

echecs = []

def check(label, condition):
    status = "OK" if condition else "FAIL"
    if not condition:
        echecs.append(label)
    print(f"[{status}] {label}")


# Sans clés configurées (état par défaut de config.py) : tout se désactive proprement.
check("est_configure() False sans clés", scraper_ebay.est_configure() is False)

listings, bloque = scraper_ebay.collecter_categorie("cpu_amd")
check("collecter_categorie renvoie [] sans clés", listings == [])
check("collecter_categorie ne signale pas de blocage sans clés", bloque is False)

# Parsing pur d'un item eBay simulé (structure réelle de l'API Browse)
faux_item = {
    "itemId": "v1|123456|0",
    "title": "AMD Ryzen 5 3600 Processor",
    "price": {"value": "42.50", "currency": "EUR"},
    "itemWebUrl": "https://www.ebay.fr/itm/123456",
    "image": {"imageUrl": "https://i.ebayimg.com/x.jpg"},
    "condition": "Used",
}
extrait = scraper_ebay._extraire(faux_item)
check("titre extrait", extrait["titre"] == "AMD Ryzen 5 3600 Processor")
check("prix extrait et converti en float", extrait["prix"] == 42.50)
check("plateforme = eBay", extrait["plateforme"] == "eBay")

item_invalide = {"title": "Sans prix"}
check("item sans prix -> None (pas de crash)", scraper_ebay._extraire(item_invalide) is None)


print("\n" + "=" * 50)
if echecs:
    print(f"ECHECS ({len(echecs)}):")
    for e in echecs:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("TOUT PASSE.")
