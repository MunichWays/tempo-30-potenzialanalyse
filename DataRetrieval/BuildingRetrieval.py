import re
import requests
import time
import geopandas as gpd

from typing import Tuple, Optional, List, Dict

from shapely.geometry import Point, LineString, Polygon

from RegionDefinition import RegionDefinition

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
        tags: Dict[str, List[str]],   # 👈 instead of amenities
        name_filter_regex: Optional[str] = None,
        timeout: int = 60,
    ):
        self.tags = tags
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
    def _build_query(self, region_definition : RegionDefinition) -> str:
        def build_blocks(bbox_str):
            blocks = []
            for key, values in self.tags.items():
                regex = "|".join(values)

                blocks.append(f'node["{key}"~"{regex}"]{bbox_str};')
                blocks.append(f'way["{key}"~"{regex}"]{bbox_str};')
                blocks.append(f'relation["{key}"~"{regex}"]{bbox_str};')

            return "\n".join(blocks)


        if region_definition.osm_relation_id is not None:
            # TODO: Deine code for this
            pass
        elif region_definition.bbox is not None:
            south, west, north, east = region_definition.bbox
            bbox_str = f"({south},{west},{north},{east})"

            return f"""
            [out:json][timeout:{self.timeout}];
            (
            {build_blocks(bbox_str)}
            );
            out tags body;
            >;
            out skel qt;
            """
        elif region_definition.key == "münchen": # Only used for munich, will be removed later
            return f"""
            [out:json][timeout:{self.timeout}];
            (
            area[admin_level=6]["name"="München"]->.boundaryarea;
            {build_blocks("(area.boundaryarea)")}
            );
            out tags body;
            >;
            out skel qt;
            """

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------
    def _fetch_raw_cached(self, region_definition):
        cached = self.datacache.load_file_from_cache(region_definition)

        if cached is not None:
            print(f"Using cached data for {self.datacache.datatype}")
            return cached
        else:
            print(f"Querying Overpass API for {self.datacache.datatype}...")
            query = self._build_query(region_definition)

            data = self._fetch_raw(query=query)
            self.datacache.store_data(data=data, region_definition=region_definition)

            return data
        
    def _fetch_raw(self, query : str):
        for attempt in range(6):
            try:
                headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'text/plain',
                    'User-Agent': 'Speed-limit-30-tool', 
                }

                response = requests.post(
                    self.OVERPASS_URL,
                    data={"data": query},
                    timeout=self.timeout,
                    headers=headers
                )
                response.raise_for_status()

                return response.json()

            except requests.exceptions.RequestException as exc:
                print(f"Attempt {attempt + 1} failed: {exc}")
                wait = min(60, 2 ** attempt)
                print(f"Retrying in {wait}s...")
                time.sleep(wait)

        raise RuntimeError("Overpass failed")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch(self, region_definition) -> Optional[gpd.GeoDataFrame]:
        data = self._fetch_raw_cached(region_definition)

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