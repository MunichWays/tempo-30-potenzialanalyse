import time

import requests
from shapely.geometry import LineString, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from DataRetrieval.OSMDataCache import OSMDataCache
from DataRetrieval.OverpassQueryCreation import OverpassQueryCreation
from RegionDefinition import RegionDefinition


class RegionBoundaryRetrieval:
    """
    Area of a region as a shapely geometry in WGS84, matching the region filter
    used for the Overpass queries (relation area first, then bbox).
    """
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self.datacache = OSMDataCache(datatype="boundary")

    def fetch_region_polygon(self, region_definition: RegionDefinition) -> BaseGeometry:
        setup, _ = OverpassQueryCreation.build_region_filter(region_definition)

        if not setup:
            south, west, north, east = region_definition.bbox
            return box(west, south, east, north)

        data = self._fetch_raw_cached(region_definition)
        return self.polygon_from_relation(data)

    @staticmethod
    def polygon_from_relation(data: dict) -> BaseGeometry:
        """Build the (multi)polygon of a boundary relation from ``out geom`` output."""
        rings = {"outer": [], "inner": []}

        for element in data["elements"]:
            if element["type"] != "relation":
                continue
            for member in element.get("members", []):
                geometry = member.get("geometry")
                if member["type"] != "way" or not geometry or len(geometry) < 2:
                    continue
                role = "inner" if member.get("role") == "inner" else "outer"
                rings[role].append(
                    LineString([(point["lon"], point["lat"]) for point in geometry])
                )

        if not rings["outer"]:
            raise ValueError("Boundary relation without outer ways")

        # unary_union nodes the line work so that ring pieces can be polygonized
        outer = unary_union(list(polygonize(unary_union(rings["outer"]))))
        if outer.is_empty:
            raise ValueError("Outer ways of the boundary relation do not form a closed ring")

        if rings["inner"]:
            inner = unary_union(list(polygonize(unary_union(rings["inner"]))))
            outer = outer.difference(inner)

        return outer

    def _build_query(self, region_definition: RegionDefinition) -> str:
        selector = OverpassQueryCreation.build_boundary_relation_selector(region_definition)
        return f"""[out:json][timeout:{self.timeout}];
        {selector}
        out geom;
        """

    def _fetch_raw_cached(self, region_definition: RegionDefinition) -> dict:
        cached_data = self.datacache.load_file_from_cache(region_definition)
        if cached_data is not None:
            print("Using cached data for region boundary")
            return cached_data

        print("Querying Overpass API for region boundary ...")
        data = self._fetch_raw(self._build_query(region_definition))
        self.datacache.store_data(data=data, region_definition=region_definition)
        return data

    def _fetch_raw(self, query: str) -> dict:
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
