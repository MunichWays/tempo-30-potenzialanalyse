"""
Retrieval of the German accident atlas (Unfallatlas) open data.

The Statistische Ämter des Bundes und der Länder publish one CSV zip per year
with all road traffic accidents with personal injury in Germany
(licence: Datenlizenz Deutschland – Namensnennung – Version 2.0). The yearly
zips (~12 MB) are downloaded on demand into a local cache and only the part
that lies inside the requested region is kept in memory.
"""

import io
import re
import time
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry.base import BaseGeometry

SOURCE_ATTRIBUTION = (
    "Statistische Ämter des Bundes und der Länder, Unfallatlas, "
    "Datenlizenz Deutschland – Namensnennung – Version 2.0"
)

# Canonical column names (as in the 2025 data set), keyed by upper-case name.
# Older years use slightly different spellings for a few columns.
_COLUMN_ALIASES = {
    "ISTSONSTIG": "IstSonstige",
    "ISTSONSTIGE": "IstSonstige",
    "ISTRAD": "IstRad",
    "ISTPKW": "IstPKW",
    "ISTFUSS": "IstFuss",
    "ISTKRAD": "IstKrad",
    "ISTGKFZ": "IstGkfz",
    "ISTSTRASSE": "IstStrassenzustand",
    "STRZUSTAND": "IstStrassenzustand",
    "ISTSTRASSENZUSTAND": "IstStrassenzustand",
    "LICHT": "ULICHTVERH",
}


class CrashDataRetrieval:
    BASE_URL = "https://www.opengeodata.nrw.de/produkte/transport_verkehr/unfallatlas/"
    FILE_PATTERN = "Unfallorte{year}_EPSG25832_CSV.zip"
    _FILE_REGEX = re.compile(r"Unfallorte(\d{4})_EPSG25832_CSV\.zip")

    def __init__(
        self,
        years_back: int = 3,
        cache_dir: str | Path = "./unfallatlas_cache",
        timeout: int = 120,
        chunksize: int = 100_000,
    ):
        if years_back < 1:
            raise ValueError("years_back must be at least 1")
        self.years_back = years_back
        self.cache_dir = Path(cache_dir)
        self.timeout = timeout
        self.chunksize = chunksize

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_for_region(self, region_polygon: BaseGeometry) -> dict[int, gpd.GeoDataFrame]:
        """
        Return the raw crash records inside the region per selected year: all
        original Unfallatlas columns plus a point geometry (EPSG:4326). Years
        without crashes in the region are included as empty GeoDataFrames.
        """
        years = self.selected_years()
        print(f"Using Unfallatlas years: {', '.join(map(str, years))}")
        return {year: self.fetch_year(year, region_polygon) for year in years}

    def fetch_year(self, year: int, region_polygon: BaseGeometry) -> gpd.GeoDataFrame:
        """Raw crash records of one year inside the region (EPSG:4326)."""
        crashes = self.load_year(year, region_polygon.bounds)
        gdf = gpd.GeoDataFrame(
            crashes.drop(columns=["lon", "lat"]),
            geometry=gpd.points_from_xy(crashes["lon"], crashes["lat"]),
            crs="EPSG:4326",
        )
        return gdf[gdf.within(region_polygon)].reset_index(drop=True)

    def selected_years(self) -> list[int]:
        years = self.available_years()
        if not years:
            raise RuntimeError(
                "No Unfallatlas years available (index not reachable and cache empty)"
            )
        return years[-self.years_back:]

    def available_years(self) -> list[int]:
        """Years listed on the open data server, or the cached years when offline."""
        try:
            response = requests.get(self.BASE_URL + "index.json", timeout=self.timeout)
            response.raise_for_status()
            years = self._years_in(response.text)
            if years:
                return years
        except requests.exceptions.RequestException as exc:
            print(f"Unfallatlas index not reachable ({exc}), using cached years")

        cached = " ".join(path.name for path in self.cache_dir.glob("*.zip"))
        return self._years_in(cached)

    def load_year(
        self,
        year: int,
        bounds: tuple[float, float, float, float],
    ) -> pd.DataFrame:
        """
        Read the raw crash records of one year that lie inside ``bounds``
        (minx, miny, maxx, maxy in WGS84), with additional "lon"/"lat" columns.
        """
        zip_path = self._ensure_zip(year)
        minx, miny, maxx, maxy = bounds
        selected = []

        with zipfile.ZipFile(zip_path) as archive:
            with archive.open(self._csv_member(archive)) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
                for chunk in pd.read_csv(text, sep=";", dtype=str, chunksize=self.chunksize):
                    chunk = self._normalize_columns(chunk)
                    chunk["lon"], chunk["lat"] = self._coordinates(chunk)
                    inside = chunk["lon"].between(minx, maxx) & chunk["lat"].between(miny, maxy)
                    selected.append(chunk[inside])

        return pd.concat(selected, ignore_index=True) if selected else pd.DataFrame(columns=["lon", "lat"])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _years_in(cls, text: str) -> list[int]:
        return sorted({int(year) for year in cls._FILE_REGEX.findall(text)})

    def _ensure_zip(self, year: int) -> Path:
        file_name = self.FILE_PATTERN.format(year=year)
        target = self.cache_dir / file_name
        if target.exists():
            print(f"Using cached Unfallatlas {year}")
            return target

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".part")
        url = self.BASE_URL + file_name
        print(f"Downloading Unfallatlas {year} ...")

        for attempt in range(4):
            try:
                with requests.get(url, stream=True, timeout=self.timeout) as response:
                    response.raise_for_status()
                    with open(partial, "wb") as file:
                        for block in response.iter_content(chunk_size=1 << 20):
                            file.write(block)
                partial.replace(target)
                return target
            except requests.exceptions.RequestException as exc:
                print(f"Attempt {attempt + 1} failed: {exc}")
                wait = min(60, 2 ** attempt)
                print(f"Retrying in {wait}s...")
                time.sleep(wait)
            finally:
                partial.unlink(missing_ok=True)

        raise RuntimeError(f"Download of {url} failed")

    @staticmethod
    def _csv_member(archive: zipfile.ZipFile) -> str:
        csv_files = [info for info in archive.infolist() if info.filename.lower().endswith(".csv")]
        if not csv_files:
            raise ValueError(f"No CSV file in {archive.filename}")
        return max(csv_files, key=lambda info: info.file_size).filename

    @staticmethod
    def _normalize_columns(chunk: pd.DataFrame) -> pd.DataFrame:
        return chunk.rename(
            columns=lambda column: _COLUMN_ALIASES.get(column.strip().upper(), column.strip())
        )

    @staticmethod
    def _coordinates(chunk: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        def number(column: str) -> pd.Series:
            return pd.to_numeric(chunk[column].str.replace(",", ".", regex=False), errors="coerce")

        if {"XGCSWGS84", "YGCSWGS84"} <= set(chunk.columns):
            return number("XGCSWGS84"), number("YGCSWGS84")

        # Fallback: projected coordinates (EPSG:25832)
        projected = gpd.GeoSeries(
            gpd.points_from_xy(number("LINREFX"), number("LINREFY")),
            crs="EPSG:25832",
        ).to_crs("EPSG:4326")
        return projected.x.set_axis(chunk.index), projected.y.set_axis(chunk.index)
