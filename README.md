# Veille Composants v2 — Mode d'emploi

Système de veille des prix de composants PC (occasion + neuf) et du
marché des PC gamer montés. Interface : un dashboard HTML local,
aucun serveur, aucun abonnement.

---

## 1. Installation (une seule fois)

```
pip install -r requirements.txt
```

C'est tout. (Si tu utilises le backup Google Sheets : le fichier de
clé `vinted-watch-*.json` doit être dans le dossier, comme avant.)

## 2. Lancer le programme

```
python main.py
```

Laisse la fenêtre ouverte : c'est le moteur. Il scanne chaque source à
son rythme (voir §7) et régénère `dashboard.html` après chaque cycle.
`Ctrl+C` pour arrêter — l'historique est sauvegardé en continu dans
`historique.json`, tu peux relancer quand tu veux sans rien perdre.

## 3. Ouvrir l'interface

Double-clique sur **`dashboard.html`** (dans le même dossier). Ça
s'ouvre dans ton navigateur. Appuie sur **F5** pour recharger les
dernières données. Bouton **en haut à droite** : bascule sombre/clair
(mémorisé).

⚠️ Avant le premier cycle complet, le fichier peut ne pas exister
encore ; tu peux ouvrir `dashboard_template.html` pour découvrir
l'interface avec des **données de démonstration** (bandeau orange).

## 4. Les onglets

| Onglet | Contenu |
|---|---|
| **Tableaux** | Annonces triées du moins cher au plus cher. Menu déroulant par composant ou groupe ("Tous les GPU"...). Vues Occasion / Neuf / Mixte. Filtre par alerte. Colonnes région + livraison pour Leboncoin. |
| **Tendances** | Bougies japonaises (occasion et neuf) + courbes de médiane par plateforme. |
| **Deals** | Journal horodaté de toutes les alertes rouges/oranges détectées, avec fréquence des deals. |
| **Valeur marché** | Donut de la valeur totale des annonces par plateforme + évolution jour par jour + détail par modèle. |
| **Vente PC** | Le marché des PC gamer montés : donuts (NVIDIA/AMD, plateformes, % Île-de-France), ventes réelles par jour, rentabilité montage, bougies des PC vendus (jour/semaine), brut vs net, tableau des annonces avec écart prix/valeur des pièces. |
| **Opportunités** | PC vendus SOUS la valeur de leurs composants (gain direct), vitesse de vente par GPU, marge par gamme de prix, config gagnante. |
| **Résumé** | Une carte par modèle : médiane occasion vs neuf le moins cher, rotation, meilleure affaire en cours. |
| **P&L** | Ton journal d'achats/reventes réels. Saisie manuelle, totaux automatiques (investi, revendu, marge, ROI). Sauvegardé dans le navigateur + export/import JSON. |

## 5. Interpréter les alertes

| Couleur | Signification |
|---|---|
| 🔴 Rouge | ≥ 30 % sous la médiane du modèle → **achète vite** |
| 🟠 Orange | 15 à 30 % sous la médiane → à regarder |
| 🟢 Vert | prix correct (sous la médiane) |
| ⚪ Gris | au-dessus de la médiane (jusqu'à +15 %) |
| masqué | > +15 % : pas affiché |

**Marge est.** = médiane − prix − 12 € de frais forfaitaires.
**Net (PC)** = somme des médianes occasion des composants détectés
dans l'annonce ; si un composant n'est pas mentionné : RAM 16 Go,
SSD 512 Go, alim médiane, +50 € boîtier, +50 € carte mère.
**Écart négatif** = le PC coûte moins cher que ses pièces.

## 6. Modifier la configuration

Tout se règle dans **`config.py`** (seul fichier à toucher) :
- ajouter/retirer un composant ou un terme de recherche → `COMPOSANTS`
- activer eBay → remplir `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET`
  (developer.ebay.com, gratuit) puis `"actif": True`
- réactiver Google Sheets → `GOOGLE_SHEETS_ACTIF = True`
- seuils d'alerte, fréquences, règles PC (GPU/CPU qualifiants,
  défauts du calcul net) → sections dédiées, tout est commenté

## 7. Fréquences et fiabilité

- Composants occasion : toutes les 5 min (CPU/GPU/RAM), 15-30 min (reste)
- Prix neuf (GPUTracker 117 magasins, Idealo, PC Componentes) : toutes les 6 h
- Annonces PC : toutes les 30 min ; comptage des ventes toutes les 3 h ;
  compteurs remis à zéro chaque nuit → 1 point de courbe par jour
- **Les courbes de ventes deviennent fiables après 48-72 h de collecte.**
- Anti-blocage : en cas de 403 répétés, la fréquence de la catégorie
  double automatiquement (plafond 1 h), puis revient à la normale.

## Points à valider au premier lancement réel

- **Leboncoin** : l'API `finder/search` est protégée par DataDome
  (comme Vinted). Le script utilise la même approche honnête que
  Vinted (cookies + ralentissement). Si les logs montrent des 403
  permanents, mets `"leboncoin": {"actif": False}` — tout le reste
  fonctionne sans.
- Les sites marchands changent parfois leur HTML : si une source
  remonte 0 offre durablement, dis-le, le parser sera ajusté.

## Fichiers

| Fichier | Rôle |
|---|---|
| `main.py` | le moteur (à lancer) |
| `config.py` | tous les réglages |
| `dashboard.html` | l'interface (générée, à ouvrir) |
| `dashboard_template.html` | modèle de l'interface (ne pas éditer) |
| `historique.json` | mémoire du programme (ne pas éditer) |
| `backup_local.xlsx` | export Excel de secours |
| `scraper_*.py` | un module par source |
| `pc_analyzer.py` / `ventes_tracker.py` | logique PC gamer / ventes |
| `test_*.py` | tests (python test_xxx.py) |
