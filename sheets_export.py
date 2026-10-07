"""
sheets_export.py
-----------------
Toute la communication avec Google Sheets. Utilise gspread pour
l'authentification et l'écriture de données (simple et lisible), et
des appels bruts à l'API (spreadsheet.batch_update) pour ce que
gspread ne couvre pas nativement : mise en forme conditionnelle,
listes déroulantes, graphiques.

HONNÊTETÉ SUR CE QUI EST VÉRIFIÉ : aucun appel à l'API Google Sheets
n'a pu être testé en conditions réelles depuis l'environnement où ce
code a été écrit (pas d'accès réseau à google.com dans ce sandbox).
La structure des requêtes suit la documentation officielle de l'API
Sheets v4, mais la première exécution chez toi sera la vraie
validation. Un point précis d'incertitude : le type de graphique
"CANDLESTICK" — je suis moins sûr à 100% qu'il soit exposé exactement
sous ce nom dans l'API. Chaque création de graphique est donc protégée
par un try/except qui log un avertissement clair au lieu de faire
planter tout l'export si un type de graphique particulier échoue.
"""

import gspread
from google.oauth2.service_account import Credentials

import config
import analysis

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

COULEURS_ALERTE = {
    "rouge":  {"red": 0.96, "green": 0.80, "blue": 0.80},
    "orange": {"red": 1.00, "green": 0.90, "blue": 0.70},
    "vert":   {"red": 0.85, "green": 0.94, "blue": 0.83},
    "gris":   {"red": 0.93, "green": 0.93, "blue": 0.93},
}

COLONNES_BRUT = [
    "categorie", "modele", "prix", "prix_unitaire", "tag_lot",
    "pct_vs_mediane", "marge_estimee", "alerte", "plateforme",
    "score_vendeur", "etat", "duree_en_ligne", "lien", "date_detection",
]


def maintenant_iso():
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------
# AUTHENTIFICATION
# --------------------------------------------------------------------

def connecter():
    creds = Credentials.from_service_account_file(config.GOOGLE_KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(config.GOOGLE_SHEET_ID)


def assurer_onglet(classeur, nom, entetes, lignes=1000, colonnes=20):
    """Renvoie l'onglet `nom`, le crée avec ses en-têtes s'il n'existe pas encore."""
    try:
        ws = classeur.worksheet(nom)
    except gspread.WorksheetNotFound:
        ws = classeur.add_worksheet(title=nom, rows=lignes, cols=colonnes)
        if entetes:
            ws.update("A1", [entetes])
    return ws


# --------------------------------------------------------------------
# CALCUL DES CHAMPS DÉRIVÉS (pct, alerte, marge) PAR MODÈLE
# --------------------------------------------------------------------

def enrichir_listings(listings):
    """
    Regroupe les annonces par modèle précis, calcule la médiane de
    CHAQUE modèle, puis remplit pct_vs_mediane / alerte / marge_estimee
    pour chaque annonce individuellement. Renvoie la liste enrichie
    (annonces masquées incluses avec leur statut, filtrées plus tard
    à l'affichage).
    """
    par_modele = {}
    for l in listings:
        cle = l.get("modele") or "?"
        par_modele.setdefault(cle, []).append(l["prix"])

    medianes = {cle: analysis.mediane(prix) for cle, prix in par_modele.items()}

    enrichis = []
    for l in listings:
        cle = l.get("modele") or "?"
        med = medianes.get(cle)
        prix_ref = l.get("prix_unitaire") or l["prix"]
        pct = analysis.pourcentage_vs_mediane(prix_ref, med)
        l = dict(l)
        l["mediane_modele"] = med
        l["pct_vs_mediane"] = pct
        l["alerte"] = analysis.palier_alerte(pct)
        l["marge_estimee"] = analysis.marge_estimee(med, prix_ref)
        enrichis.append(l)
    return enrichis


def _ligne_brut(l, categorie_label):
    return [
        categorie_label,
        l.get("modele") or "",
        l["prix"],
        l.get("prix_unitaire") or l["prix"],
        "LOT" if l.get("lot_type") == "lot_gros" else "",
        l.get("pct_vs_mediane") if l.get("pct_vs_mediane") is not None else "",
        l.get("marge_estimee") if l.get("marge_estimee") is not None else "",
        l.get("alerte") or "",
        l.get("plateforme") or "",
        l.get("score_vendeur") or "",
        l.get("etat") or "",
        l.get("duree_en_ligne") or "",
        l.get("url") or "",
        l.get("horodatage") or maintenant_iso(),
    ]


# --------------------------------------------------------------------
# ÉCRITURE DES DONNÉES BRUTES
# --------------------------------------------------------------------

def ecrire_brut_occasion(classeur, toutes_les_donnees):
    """
    toutes_les_donnees : dict {categorie_id: [listings...]} (déjà
    enrichis par enrichir_listings). Écrase entièrement l'onglet
    _Brut_Occasion à chaque appel — c'est un instantané du marché
    actuel, pas un historique (l'historique vit dans _Deals_Log et
    _Historique).
    """
    ws = assurer_onglet(classeur, "_Brut_Occasion", COLONNES_BRUT)
    lignes = []
    for cat_id, listings in toutes_les_donnees.items():
        label = config.COMPOSANTS[cat_id]["label"]
        for l in listings:
            lignes.append(_ligne_brut(l, label))

    ws.clear()
    ws.update("A1", [COLONNES_BRUT])
    if lignes:
        ws.update("A2", lignes)
    return len(lignes)


def ecrire_brut_neuf(classeur, toutes_les_donnees_neuf):
    """Même principe que ecrire_brut_occasion, pour les prix neuf de référence."""
    ws = assurer_onglet(classeur, "_Brut_Neuf", COLONNES_BRUT)
    lignes = []
    for cat_id, listings in toutes_les_donnees_neuf.items():
        label = config.COMPOSANTS[cat_id]["label"]
        for l in listings:
            lignes.append(_ligne_brut(l, label))

    ws.clear()
    ws.update("A1", [COLONNES_BRUT])
    if lignes:
        ws.update("A2", lignes)
    return len(lignes)


def journaliser_deals(classeur, toutes_les_donnees):
    """
    Ajoute (sans écraser) une ligne par annonce en alerte rouge ou
    orange détectée ce cycle, dans _Deals_Log. C'est ce log cumulatif
    qui alimente l'onglet Deals et ses bougies japonaises.
    """
    ws = assurer_onglet(
        classeur, "_Deals_Log",
        ["categorie", "modele", "prix", "pct_vs_mediane", "alerte", "plateforme", "date"],
    )
    lignes = []
    for cat_id, listings in toutes_les_donnees.items():
        label = config.COMPOSANTS[cat_id]["label"]
        for l in listings:
            if l.get("alerte") in ("rouge", "orange"):
                lignes.append([
                    label, l.get("modele") or "", l["prix"],
                    l.get("pct_vs_mediane"), l.get("alerte"),
                    l.get("plateforme"), l.get("horodatage") or maintenant_iso(),
                ])
    if lignes:
        ws.append_rows(lignes, value_input_option="USER_ENTERED")
    return len(lignes)


def archiver_disparues(classeur, listings_disparus):
    """listings_disparus : liste de dicts avec categorie/modele/prix/plateforme/
    premiere_vue/derniere_vue. Ajouté (append) à _Historique, jamais écrasé."""
    ws = assurer_onglet(
        classeur, "_Historique",
        ["categorie", "modele", "prix", "plateforme", "premiere_vue",
         "derniere_vue", "duree_heures"],
    )
    lignes = []
    for l in listings_disparus:
        duree = analysis.vitesse_rotation_moyenne([l])
        lignes.append([
            l.get("categorie", ""), l.get("modele", ""), l.get("prix", ""),
            l.get("plateforme", ""), l.get("premiere_vue", ""),
            l.get("derniere_vue", ""), duree if duree is not None else "",
        ])
    if lignes:
        ws.append_rows(lignes, value_input_option="USER_ENTERED")
    return len(lignes)


# --------------------------------------------------------------------
# MISE EN FORME : COULEURS PAR ALERTE + LISTE DÉROULANTE
# --------------------------------------------------------------------

def appliquer_couleurs_alerte(classeur, sheet_id, colonne_alerte_lettre, derniere_ligne=1000):
    """
    Une règle de mise en forme conditionnelle par couleur, basée sur
    le contenu de la colonne "alerte" (rouge/orange/vert/gris).
    """
    requests = []
    for i, (mot, couleur) in enumerate(COULEURS_ALERTE.items()):
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": derniere_ligne,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue":
                                        f"=${colonne_alerte_lettre}2=\"{mot}\""}],
                        },
                        "format": {"backgroundColor": couleur},
                    },
                },
                "index": i,
            }
        })
    try:
        classeur.batch_update({"requests": requests})
    except Exception as e:
        print(f"[Sheets] Avertissement : mise en forme conditionnelle non appliquée ({e})")


def ajouter_liste_deroulante(classeur, sheet_id, ligne, colonne, options):
    """Liste déroulante (validation de données) sur une seule cellule."""
    requests = [{
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id, "startRowIndex": ligne, "endRowIndex": ligne + 1,
                "startColumnIndex": colonne, "endColumnIndex": colonne + 1,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": o} for o in options],
                },
                "showCustomUi": True,
                "strict": False,
            },
        }
    }]
    try:
        classeur.batch_update({"requests": requests})
    except Exception as e:
        print(f"[Sheets] Avertissement : liste déroulante non appliquée ({e})")


def liste_options_dropdown(toutes_les_donnees=None):
    """
    'Tous' + 'Tous les {catégorie}' pour chaque famille + un modèle
    précis par annonce déjà observée (ex: 'RTX 3070'). La liste
    s'enrichit donc naturellement au fil des cycles, sans jamais
    perdre les regroupements par famille.
    """
    options = ["Tous"]
    for cat in config.COMPOSANTS.values():
        options.append(f"Tous les {cat['label']}")

    if toutes_les_donnees:
        modeles = set()
        for listings in toutes_les_donnees.values():
            for l in listings:
                if l.get("modele"):
                    modeles.add(l["modele"])
        options.extend(sorted(modeles))

    return options


# --------------------------------------------------------------------
# ONGLET VISIBLE (dropdown + QUERY vers les données brutes)
# --------------------------------------------------------------------

def construire_onglet_interactif(classeur, nom_onglet, nom_onglet_brut, options_dropdown):
    """
    Crée (si besoin) un onglet avec :
      - B1 : liste déroulante de sélection ("Tous" / "Tous les GPU" / "RTX 3070"...)
      - un bandeau de stats en formules (lignes 3-4), recalculé
        automatiquement à chaque changement de B1
      - à partir de la ligne 7 : une formule QUERY qui filtre
        _Brut_Occasion (ou _Brut_Neuf) selon B1, triée par prix croissant

    Disposition des colonnes en sortie (identique à COLONNES_BRUT) :
      A=categorie B=modele C=prix D=prix_unitaire E=tag_lot
      F=pct_vs_mediane G=marge_estimee H=alerte I=plateforme
      J=score_vendeur K=etat L=duree_en_ligne M=lien N=date_detection
    """
    ws = assurer_onglet(classeur, nom_onglet, None, colonnes=16)
    sheet_id = ws.id

    ws.update("A1", [["Sélection :", "Tous"]])
    ws.update("A3", [["Médiane", "Min", "Max", "Annonces", "Volume total"]])
    # Les stats portent sur la colonne C (prix) du résultat filtré, qui
    # commence en ligne 7 (voir formule QUERY plus bas).
    ws.update("A4", [[
        "=IFERROR(MEDIAN(C7:C1000),\"-\")",
        "=IFERROR(MIN(C7:C1000),\"-\")",
        "=IFERROR(MAX(C7:C1000),\"-\")",
        "=IFERROR(COUNTA(C7:C1000),0)",
        "=IFERROR(SUM(C7:C1000),0)",
    ]], raw=False)

    ws.update("A6", [list(COLONNES_BRUT)])

    formule_filtre = (
        f'=QUERY({nom_onglet_brut}!A2:N, '
        f'"select A,B,C,D,E,F,G,H,I,J,K,L,M,N '
        f'where (B = \'"&SUBSTITUTE($B$1,\'Tous les \',\'\')&"\' '
        f'or A = \'"&SUBSTITUTE($B$1,\'Tous les \',\'\')&"\' '
        f'or \'"&$B$1&"\' = \'Tous\') '
        f'and F <= {config.SEUIL_MASQUAGE} '
        f'order by C asc", 0)'
    )
    ws.update("A7", [[formule_filtre]], raw=False)

    ajouter_liste_deroulante(classeur, sheet_id, 0, 1, options_dropdown)
    appliquer_couleurs_alerte(classeur, sheet_id, "H", derniere_ligne=1000)
    return ws


# --------------------------------------------------------------------
# GRAPHIQUES (best-effort — voir avertissement en haut du fichier)
# --------------------------------------------------------------------

def _ajouter_graphique(classeur, requete, description):
    try:
        classeur.batch_update({"requests": [requete]})
    except Exception as e:
        print(f"[Sheets] Avertissement : graphique '{description}' non créé ({e})")


def creer_graphique_barres(classeur, sheet_id, titre, plage_categories, plage_valeurs, ancre):
    requete = {
        "addChart": {
            "chart": {
                "spec": {
                    "title": titre,
                    "basicChart": {
                        "chartType": "COLUMN",
                        "legendPosition": "BOTTOM_LEGEND",
                        "domains": [{"domain": {"sourceRange": {"sources": [plage_categories]}}}],
                        "series": [{"series": {"sourceRange": {"sources": [v]}}} for v in plage_valeurs],
                    },
                },
                "position": {"overlayPosition": {"anchorCell": ancre}},
            }
        }
    }
    _ajouter_graphique(classeur, requete, titre)


def creer_graphique_courbes(classeur, sheet_id, titre, plage_dates, plages_series, ancre):
    requete = {
        "addChart": {
            "chart": {
                "spec": {
                    "title": titre,
                    "basicChart": {
                        "chartType": "LINE",
                        "legendPosition": "BOTTOM_LEGEND",
                        "domains": [{"domain": {"sourceRange": {"sources": [plage_dates]}}}],
                        "series": [{"series": {"sourceRange": {"sources": [s]}}} for s in plages_series],
                    },
                },
                "position": {"overlayPosition": {"anchorCell": ancre}},
            }
        }
    }
    _ajouter_graphique(classeur, requete, titre)


def creer_graphique_bougies(classeur, sheet_id, titre, plage_dates, plage_ohlc, ancre):
    """
    Bougies japonaises. Point d'incertitude signalé en haut du fichier :
    protégé par try/except, avec repli automatique en graphique en
    courbes si le type CANDLESTICK est refusé par l'API.
    """
    requete = {
        "addChart": {
            "chart": {
                "spec": {
                    "title": titre,
                    "candlestickChart": {
                        "domain": {"data": {"sourceRange": {"sources": [plage_dates]}}},
                        "data": [{
                            "lowSeries": {"data": {"sourceRange": {"sources": [plage_ohlc]}}},
                            "highSeries": {"data": {"sourceRange": {"sources": [plage_ohlc]}}},
                            "openSeries": {"data": {"sourceRange": {"sources": [plage_ohlc]}}},
                            "closeSeries": {"data": {"sourceRange": {"sources": [plage_ohlc]}}},
                        }],
                    },
                },
                "position": {"overlayPosition": {"anchorCell": ancre}},
            }
        }
    }
    try:
        classeur.batch_update({"requests": [requete]})
    except Exception as e:
        print(f"[Sheets] Bougie '{titre}' refusée par l'API ({e}) — repli en courbe.")
        creer_graphique_courbes(classeur, sheet_id, titre + " (repli courbe)",
                                 plage_dates, [plage_ohlc], ancre)
