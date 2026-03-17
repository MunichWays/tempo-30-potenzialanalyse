import hashlib
import json
import re
from pathlib import Path
from typing import Tuple, Optional

import requests
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon

from DataRetrieval.OSMDataCache import OSMDataCache

EDUCATION_BUILDING_TYPES = [
    "school",
    "kindergarten"
]

class EducationalBuildingRetrieval:
    """
    Retrieve schools (amenity=school) from OpenStreetMap via Overpass API.
    Returns a GeoDataFrame in EPSG:4326.
    """

    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.datacache = OSMDataCache(datatype = "educational_buildings")
    # ------------------------------------------------------------------
    # Overpass Query
    # ------------------------------------------------------------------

    def _build_query(self, bbox: Tuple[float, float, float, float]) -> str:
        """
        Build Overpass query for schools inside bounding box.
        bbox = (south, west, north, east)
        """
        education_building_regex = "|".join(EDUCATION_BUILDING_TYPES)
        
        if(isinstance(bbox, str)):
            return """
            [out:json][timeout:{timeout}];
            (
            area[admin_level=6]["name"="{name}"]->.boundaryarea;
            node["amenity"~"{education_building_regex}"](area.boundaryarea);
            way["amenity"~"{education_building_regex}"](area.boundaryarea);
            relation["amenity"~"{education_building_regex}"](area.boundaryarea);
            );
            out tags body;
            >;
            out skel qt;
            """.format(timeout=self.timeout, name = bbox, education_building_regex = education_building_regex)
        else:
            south, west, north, east = bbox

            return f"""
            [out:json][timeout:{self.timeout}];
            (
            node["amenity"~"{education_building_regex}"]({south},{west},{north},{east});
            way["amenity"~"{education_building_regex}"]({south},{west},{north},{east});
            relation["amenity"~"{education_building_regex}"]({south},{west},{north},{east});
            );
            out tags body;
            >;
            out skel qt;
            """

    def _fetch_raw_cached(self, bbox: Tuple[float, float, float, float]) -> dict:
        cached_data = self.datacache.load_file_from_cache(bbox)

        if(cached_data is not None):
            print("Using cached data for educational bdgs")
            return cached_data
        else:
            print("Querying Overpass API for educational bdgs...")
            query = self._build_query(bbox)

            response = requests.post(
                self.OVERPASS_URL,
                data={"data": query},
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()

            self.datacache.store_data(data = data, bbox = bbox)

            return data

    def fetch_education_bdg_with_name(
        self,
        bbox: Tuple[float, float, float, float]
    ) -> Optional[gpd.GeoDataFrame]:
        """
        Fetch schools as GeoDataFrame (EPSG:4326).
        """

        data = self._fetch_raw_cached(bbox)

        # Collect nodes for geometry reconstruction
        nodes = {
            el["id"]: (el["lon"], el["lat"])
            for el in data["elements"]
            if el["type"] == "node"
        }

        records = []

        for el in data["elements"]:
            tags = el.get("tags", {})

            if el["type"] == "node":
                geom = Point(el["lon"], el["lat"])

            elif el["type"] == "way":
                coords = [
                    nodes[nid]
                    for nid in el.get("nodes", [])
                    if nid in nodes
                ]

                if len(coords) < 3:
                    continue

                # Closed ring → polygon
                if coords[0] == coords[-1]:
                    geom = Polygon(coords)
                else:
                    geom = LineString(coords)

            elif el["type"] == "relation":
                # Relations are complex (multipolygons)
                # For now, skip them to avoid geometry issues
                continue

            else:
                continue
            
            name = tags.get("name")
            
            pattern = re.compile(r"(kindergarten|grundschule|hauptschule|realschule|mittelschule|gymnasium)", re.IGNORECASE) # Case-insensitive Filter on schools

            if name is None or not pattern.search(name):
                continue

            records.append({
                "osm_id": el["id"],
                "element_type": el["type"],
                "name": tags.get("name"),
                "street": tags.get("addr:street"),
                "housenumber": tags.get("addr:housenumber"),
                "website" : tags.get("contact:website"),
                "operator": tags.get("operator"),
                "school_level": tags.get("school:level"),
                "isced_level": tags.get("isced:level"),
                "geometry": geom,
            })

        if len(records) == 0:
            print("No schools found in bbox.")
            return None

        gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
        return gdf

  
