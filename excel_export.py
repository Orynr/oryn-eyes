"""
excel_export.py
----------------
Backup local en .xlsx, régénéré entièrement à chaque cycle. C'est un
instantané, pas un modèle interactif : les valeurs sont écrites
directement (pas de formules à recalculer) puisque Google Sheets est
l'outil interactif principal — ce fichier est le filet de sécurité si
la connexion à Google venait à manquer.

Les graphiques ici se limitent à barres + courbes (openpyxl n'a pas
d'équivalent natif fiable pour les bougies japonaises) ; les bougies
japonaises restent réservées à Google Sheets.
"""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.chart import BarChart, LineChart, Reference

import config
import sheets_export  # réutilise COLONNES_BRUT et _ligne_brut

POLICE = "Calibri"

COULEURS_ALERTE_XLSX = {
    "rouge":  "F6CCCC",
    "orange": "FFE5B3",
    "vert":   "D9F0D3",
    "gris":   "EDEDED",
}


def _entete(ws, ligne, colonnes):
    for i, c in enumerate(colonnes, start=1):
        cell = ws.cell(row=ligne, column=i, value=c)
        cell.font = Font(name=POLICE, bold=True, size=10)
        cell.alignment = Alignment(horizontal="center")


def _feuille_occasion(wb, toutes_les_donnees):
    ws = wb.create_sheet("Occasion")
    _entete(ws, 1, sheets_export.COLONNES_BRUT)

    ligne = 2
    for cat_id, listings in toutes_les_donnees.items():
        label = config.COMPOSANTS[cat_id]["label"]
        for l in listings:
            valeurs = sheets_export._ligne_brut(l, label)
            for col, v in enumerate(valeurs, start=1):
                cell = ws.cell(row=ligne, column=col, value=v)
                cell.font = Font(name=POLICE, size=10)
            couleur = COULEURS_ALERTE_XLSX.get(l.get("alerte"))
            if couleur:
                fill = PatternFill(start_color=couleur, end_color=couleur, fill_type="solid")
                for col in range(1, len(sheets_export.COLONNES_BRUT) + 1):
                    ws.cell(row=ligne, column=col).fill = fill
            ligne += 1

    for col_cells in ws.columns:
        longueur = max((len(str(c.value)) for c in col_cells if c.value is not None), default=10)
        ws.column_dimensions[col_cells[0].column_letter].width = min(longueur + 2, 40)
    return ws


def _feuille_resume(wb, toutes_les_donnees):
    ws = wb.create_sheet("Resume")
    entetes = ["Categorie", "Mediane", "Min", "Max", "Nb annonces", "Volume total (EUR)"]
    _entete(ws, 1, entetes)

    ligne = 2
    for cat_id, listings in toutes_les_donnees.items():
        label = config.COMPOSANTS[cat_id]["label"]
        prix = [l["prix"] for l in listings]
        if not prix:
            ws.append([label, "-", "-", "-", 0, 0])
            ligne += 1
            continue
        stats = {
            "min": min(prix), "max": max(prix),
            "mediane": sorted(prix)[len(prix) // 2],
            "total": round(sum(prix), 2),
        }
        for col, v in enumerate(
            [label, stats["mediane"], stats["min"], stats["max"], len(prix), stats["total"]],
            start=1,
        ):
            ws.cell(row=ligne, column=col, value=v).font = Font(name=POLICE, size=10)
        ligne += 1

    for col_cells in ws.columns:
        longueur = max((len(str(c.value)) for c in col_cells if c.value is not None), default=10)
        ws.column_dimensions[col_cells[0].column_letter].width = min(longueur + 2, 30)

    # Graphique barres : médiane par catégorie
    if ligne > 2:
        chart = BarChart()
        chart.title = "Médiane par catégorie"
        chart.y_axis.title = "EUR"
        data = Reference(ws, min_col=2, min_row=1, max_row=ligne - 1)
        cats = Reference(ws, min_col=1, min_row=2, max_row=ligne - 1)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        ws.add_chart(chart, "H2")
    return ws


def generer_backup(toutes_les_donnees, chemin=None):
    """
    toutes_les_donnees : dict {categorie_id: [listings enrichis...]}
    Écrit un .xlsx complet et l'écrase à chaque appel.
    """
    chemin = chemin or config.EXCEL_BACKUP_FILE
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # enlève la feuille vide par défaut

    _feuille_occasion(wb, toutes_les_donnees)
    _feuille_resume(wb, toutes_les_donnees)

    wb.save(chemin)
    return chemin
