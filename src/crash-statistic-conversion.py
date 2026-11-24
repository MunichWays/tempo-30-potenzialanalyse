import geopandas as gpd
import pandas as pd
from pathlib import Path

# ============================================================
# 1. KONFIGURATION
# ============================================================

# Pfad zur entpackten Shapefile-Datei des Unfallatlas
INPUT_FILE = Path("Unfallorte2024_EPSG25832_Shape/shp/Unfallorte_2024_LR_BasisDLM.shp")

# Ausgabedatei für uMap
OUTPUT_FILE = Path("unfallatlas_muenchen_2024.geojson")

# Bounding Box München in WGS84 (EPSG:4326)
# Reihenfolge: West, Süd, Ost, Nord
BBOX = (11.36, 48.06, 11.72, 48.25)


# ============================================================
# 2. DATEN EINLESEN
# ============================================================

print("Lese Unfallatlas ein ...")

gdf = gpd.read_file(INPUT_FILE)

print(f"Ursprüngliche Anzahl Unfälle: {len(gdf):,}")
print(f"Koordinatenreferenzsystem: {gdf.crs}")
print("Vorhandene Spalten:")
print(gdf.columns.tolist())

if gdf.crs is None:
    raise ValueError(
        "Das Koordinatenreferenzsystem fehlt. "
        "Bitte anhand der Quelldokumentation klären."
    )

if gdf.geometry.isna().any():
    print("Hinweis: Datensätze ohne Geometrie vorhanden.")

# Nur Datensätze mit gültiger Geometrie behalten
gdf = gdf[
    gdf.geometry.notna() & ~gdf.geometry.is_empty
].copy()

# ============================================================
# 3. KOORDINATENSYSTEM TRANSFORMIEREN
# ============================================================

print("Transformiere Koordinaten nach EPSG:4326 ...")

gdf = gdf.to_crs("EPSG:4326")

# ============================================================
# 4. AUF DIE MÜNCHNER BOUNDING BOX FILTERN
# ============================================================

print("Filtere Unfälle innerhalb der Bounding Box ...")

xmin, ymin, xmax, ymax = BBOX

muenchen = gdf.cx[
    xmin:xmax,
    ymin:ymax
].copy()

print(f"Unfälle innerhalb der Bounding Box: {len(muenchen):,}")

if muenchen.empty:
    raise ValueError(
        "Keine Unfälle innerhalb der Bounding Box gefunden. "
        "Prüfe das Koordinatensystem und die Bounding Box."
    )


# ============================================================
# 6. UNFALLARTEN KLASSIFIZIEREN
# ============================================================

import pandas as pd

# Reihenfolge bestimmt die Benennung der Kombinationen
teilnehmer = [
    "IstRad",
    "IstPKW",
    "IstFuss",
    "IstKrad",
    "IstGkfz",
    "IstSonstig",
]

# Kurzbezeichnungen für die Ausgabe
namen = {
    "IstRad": "Rad",
    "IstPKW": "PKW",
    "IstFuss": "Fuss",
    "IstKrad": "Krad",
    "IstGkfz": "Gkfz",
    "IstSonstig": "Sonstig",
}


def klassifiziere_unfall(row):
    # Fehlende und unerwartete Werte erkennen
    werte = row[teilnehmer]

    if werte.isna().any():
        return "Unklar"

    if not werte.isin([0, 1]).all():
        return "Unklar"

    # Beteiligte Arten in ursprünglicher Reihenfolge
    beteiligt = [
        namen[col]
        for col in teilnehmer
        if row[col] == 1
    ]

    anzahl = len(beteiligt)

    if anzahl == 0:
        return "Keine dieser Arten"

    if anzahl == 1:
        return f"{beteiligt[0]}"

    if anzahl == 2:
        return "-".join(beteiligt)

    return "3+ Arten"



print("\nKlassifiziere Unfallarten ...")

# Teilnehmermerkmale in numerische Werte umwandeln
for col in teilnehmer:
    muenchen[col] = pd.to_numeric(
        muenchen[col],
        errors="coerce"
    )


muenchen["Unfallklasse"] = muenchen.apply(
    klassifiziere_unfall,
    axis=1
)

# ============================================================
# 7. ERGEBNISSE KONTROLLIEREN
# ============================================================

print("\nAnzahl Unfälle je Kategorie:")
print(
    muenchen["Unfallklasse"]
    .value_counts(dropna=False)
    .to_string()
)

# Prozentanteile je Kategorie
print("\nProzentuale Verteilung:")
print(
    (
        muenchen["Unfallklasse"]
        .value_counts(normalize=True, dropna=False)
        * 100
    ).round(2).to_string()
)

# ============================================================
# 8. GEOJSON EXPORTIEREN
# ============================================================

print("\nExportiere GeoJSON ...")

# GeoJSON verwendet WGS84 (EPSG:4326).
muenchen = muenchen.to_crs("EPSG:4326")

muenchen.to_file(
    OUTPUT_FILE,
    driver="GeoJSON",
    index=False
)

print("\nFertig!")
print(f"Datei: {OUTPUT_FILE.resolve()}")
print(f"Anzahl exportierter Unfälle: {len(muenchen):,}")