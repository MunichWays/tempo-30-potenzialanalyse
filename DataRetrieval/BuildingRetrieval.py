import re
import requests
import geopandas as gpd

from typing import Tuple, Optional, List

from shapely.geometry import Point, LineString, Polygon

from DataRetrieval.OSMDataCache import OSMDataCache


class BuildingRetrieval:
    """
    Generic OSM amenity retrieval via Overpass API.
    Example:
        amenities = ["school", "kindergarten"]
        retriever = OSMBuildingRetrieval("educational_buildings", amenities, ["gymnasium", "realschule"])
    """

    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(
        self,
        datatype: str,
        amenities: List[str],
        name_filter_regex: Optional[str] = None,
        timeout: int = 60,
    ):
        self.amenities = amenities
        self.timeout = timeout
        self.name_filter_regex = (
            re.compile(name_filter_regex, re.IGNORECASE)
            if name_filter_regex
            else None
        )

        self.datacache = OSMDataCache(datatype=datatype)

    # ------------------------------------------------------------------
    # Query builder
    # ------------------------------------------------------------------
    def _build_query(self, bbox: Tuple[float, float, float, float]) -> str:
        amenity_regex = "|".join(self.amenities)

        if isinstance(bbox, str):
            return f"""
            [out:json][timeout:{self.timeout}];
            (
              area[admin_level=6]["name"="{bbox}"]->.boundaryarea;
              node["amenity"~"{amenity_regex}"](area.boundaryarea);
              way["amenity"~"{amenity_regex}"](area.boundaryarea);
              relation["amenity"~"{amenity_regex}"](area.boundaryarea);
            );
            out tags body;
            >;
            out skel qt;
            """
        else:
            south, west, north, east = bbox
            return f"""
            [out:json][timeout:{self.timeout}];
            (
              node["amenity"~"{amenity_regex}"]({south},{west},{north},{east});
              way["amenity"~"{amenity_regex}"]({south},{west},{north},{east});
              relation["amenity"~"{amenity_regex}"]({south},{west},{north},{east});
            );
            out tags body;
            >;
            out skel qt;
            """

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------
    def _fetch_raw_cached(self, bbox):
        cached = self.datacache.load_file_from_cache(bbox)

        if cached is not None:
            print(f"Using cached data for {self.datacache.datatype}")
            return cached

        print(f"Querying Overpass API for {self.datacache.datatype}...")
        query = self._build_query(bbox)

        response = requests.post(
            self.OVERPASS_URL,
            data={"data": query},
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        self.datacache.store_data(data=data, bbox=bbox)

        return data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch(self, bbox) -> Optional[gpd.GeoDataFrame]:
        data = self._fetch_raw_cached(bbox)

        nodes = {
            el["id"]: (el["lon"], el["lat"])
            for el in data["elements"]
            if el["type"] == "node"
        }

        records = []

        for el in data["elements"]:
            tags = el.get("tags", {})

            # ---------------- Geometry ----------------
            if el["type"] == "node":
                geom = Point(el["lon"], el["lat"])

            elif el["type"] == "way":
                coords = [nodes[n] for n in el.get("nodes", []) if n in nodes]

                if len(coords) < 2:
                    continue

                if coords[0] == coords[-1] and len(coords) >= 3:
                    geom = Polygon(coords)
                else:
                    geom = LineString(coords)

            else:
                continue

            # ---------------- Name filter ----------------
            name = tags.get("name")
            if self.name_filter_regex:
                if name is None or not self.name_filter_regex.search(name):
                    continue

            # ---------------- Record ----------------
            record = {
                "osm_id": el["id"],
                "element_type": el["type"],
                "name": name,
                "street": tags.get("addr:street"),
                "housenumber": tags.get("addr:housenumber"),
                "website": tags.get("contact:website"),
                "operator": tags.get("operator"),
                "geometry": geom,
            }


            records.append(record)

        if not records:
            print("No results found.")
            return None

        return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")