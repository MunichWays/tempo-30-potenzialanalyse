import requests
import time
from pathlib import Path
from typing import Tuple

import geopandas as gpd
from shapely.geometry import Point, LineString

from RegionDefinition import RegionDefinition

from DataRetrieval.OSMDataCache import OSMDataCache
from DataRetrieval.OverpassQueryCreation import OverpassQueryCreation

class ZebraCrossingRetrieval:
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.datacache = OSMDataCache(datatype = "zebra_crossing")

    def _build_query(self, region_definition: RegionDefinition) -> str:
        filters = """
        node["crossing"="zebra"]{region};
        way["crossing"="zebra"]{region};

        node["highway"="crossing"]["crossing"="zebra"]{region};
        way["highway"="crossing"]["crossing"="zebra"]{region};

        node["crossing:markings"="zebra"]{region};
        way["crossing:markings"="zebra"]{region};

        node["crossing_ref"="zebra"]{region};
        way["crossing_ref"="zebra"]{region};
        """

        return OverpassQueryCreation.build_query(
            self,
            region_definition,
            filters,
        )
      

    def _fetch_raw_cached(self, region_definition) -> dict:
        cached_data = self.datacache.load_file_from_cache(region_definition)
        if(cached_data is not None):
            print("Using cached data for zebra crossing")
            return cached_data
        else:
            print("Querying OverpassAPI for Zebra Crossings")
            # not cached → query Overpass
            query = self._build_query(region_definition)

            data = self._fetch_raw(query=query)

            self.datacache.store_data(data = data, region_definition = region_definition)

            return data
        
    def _fetch_raw(self, query):
        for attempt in range(0, 6):
            try:
                headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'text/plain',
                    'User-Agent': 'Speed-limit-30-tool', 
                }
                response = requests.post(self.OVERPASS_URL, data={"data": query}, timeout=self.timeout, headers=headers)
                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as exc:
                print(f"Attempt {attempt + 1} failed: {exc}")
                wait = min(60, 2 ** attempt)
                print(f"Retrying in {wait}s...")
                time.sleep(wait)

        raise RuntimeError("Overpass failed")

    def fetch_zebra_crossings(self, region_definition) -> gpd.GeoDataFrame:
        data = self._fetch_raw_cached(region_definition)

        # Nodes sammeln (für Wege)
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
                coords = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]
                if len(coords) < 2:
                    continue
                geom = LineString(coords)

            else:
                continue

            records.append({
                "osm_id": el["id"],
                "element_type": el["type"],
                "crossing": tags.get("crossing"),
                "highway": tags.get("highway"),
                "name": tags.get("name"),
                "street" : tags.get("addr:street"),
                "geometry": geom
            })

        if(len(records) > 0):
            return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
        else:
            print("No crossings identified")
            return None
