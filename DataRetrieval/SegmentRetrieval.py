import requests
from typing import Tuple
import geopandas as gpd
from shapely.geometry import LineString
import json
import hashlib
from pathlib import Path

from dataclasses import dataclass
from typing import List, Optional

from DataRetrieval.OSMDataCache import OSMDataCache

class SegmentRetrieval:
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self, timeout: int = 600):
        self.timeout = timeout
        self.datacache = OSMDataCache(datatype = "streets")

    def _build_query(
        self,
        bbox: Tuple[float, float, float, float] | str
    ) -> str:
        if(isinstance(bbox, str)):
            return """
            [out:json][timeout:{timeout}];
            (
            area[admin_level=6]["name"="{name}"]->.boundaryarea;
            way(area.boundaryarea)["highway"];
            );
            out body;
            >;
            out skel qt;
            """.format(timeout=self.timeout, name = bbox)
        else:
            south, west, north, east = bbox

            
            return f"""
            [out:json][timeout:{self.timeout}];
            (
            way["highway"]
            ({south},{west},{north},{east});
            );
            out body;
            >;
            out skel qt;
            """

    def _fetch_raw(self, query: str) -> dict:
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


    def _fetch_raw_cached(self, bbox: Tuple[float, float, float, float]) -> dict:
        cached_data = self.datacache.load_file_from_cache(bbox)

        if(cached_data is not None):
            print("Using cached data for streets")
            return cached_data
        else:
            print("Quering overpass API for streets...")
            # not cached → query Overpass
            query = self._build_query(bbox)
            data = self._fetch_raw(query)

            self.datacache.store_data(data = data, bbox = bbox)

            return data

    def fetch_as_geodataframe(
        self,
        bbox: Tuple[float, float, float, float],
        crs: str = "EPSG:4326"
    ) -> gpd.GeoDataFrame:
        data = self._fetch_raw_cached(bbox)

        # Nodes sammeln
        nodes = {
            el["id"]: (el["lon"], el["lat"])
            for el in data["elements"]
            if el["type"] == "node"
        }

        records = []

        for el in data["elements"]:
            if el["type"] != "way":
                continue

            tags = el.get("tags", {})
            highway = tags.get("highway")

            # Nur relevante Straßen
            if highway in {"footway", "cycleway", "path", "steps"}:
                continue

            coords = [
                nodes[nid] for nid in el["nodes"]
                if nid in nodes
            ]
            if len(coords) < 2:
                continue
            
            new_entry = create_gdf_entry(el, highway, coords, tags)
           
            records.append(new_entry)

        result_df = gpd.GeoDataFrame(records, geometry="geometry", crs=crs)

        result_df_sorted = result_df.sort_values(by="name", na_position="last")
        return result_df_sorted


def create_gdf_entry(el, highway, coords, tags):
    # -----------------------------
    # Maxspeed-Klassifikation
    # -----------------------------
    maxspeed = tags.get("maxspeed")
    zone_maxspeed = tags.get("zone:maxspeed")

    if maxspeed == "10":
        maxspeed_class = "10"
    elif maxspeed == "20":
        maxspeed_class = "20"
    elif maxspeed == "30":
        maxspeed_class = "30"
    elif zone_maxspeed == "30":
        maxspeed_class = "30_Zone"
    elif maxspeed == "50":
        maxspeed_class = "50"
    elif maxspeed == "60":
        maxspeed_class = "60"
    else:
        # implizit innerorts
        maxspeed_class = "Keine Daten"

    max_speed_conditional_str = tags.get("maxspeed:conditional")
    try:
        conditional_speed = parse_conditional_speed(max_speed_conditional_str)
    except:
        conditional_speed = None
    
    new_entry = {
        "osm_id": el["id"],
        "name": tags.get("name"),
        "highway": highway,
        "maxspeed_tag": maxspeed,
        "zone_maxspeed_tag": zone_maxspeed,
        "maxspeed_class": maxspeed_class,
        "geometry": LineString(coords)
    }

    if(conditional_speed is None):
        new_entry["conditional_speed"] = None
        new_entry["cond_speed_days"] = None
        new_entry["cond_speed_starttime"] = None
        new_entry["cond_speed_endtime"] = None
        new_entry["cond_speed_special"] = None
    else:
        new_entry["conditional_speed"] = str(conditional_speed.speed)
        new_entry["cond_speed_days"] = str.join(",", conditional_speed.days)
        new_entry["cond_speed_starttime"] = conditional_speed.start_time
        new_entry["cond_speed_endtime"] = conditional_speed.end_time
        new_entry["cond_speed_special"] = str.join(",", conditional_speed.special)

    return new_entry



@dataclass
class ConditionalSpeed:
    speed: int
    days: List[str]
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    special: List[str] = None

def parse_conditional_speed(cond_str: str) -> ConditionalSpeed:
    """
    Parse a conditional speed limit string like:
    "Conditional 50 @ (Mo-Fr 18:00-07:00; Sa, Su, PH)"
    """
    # Remove 'Conditional' prefix
    cond_str = cond_str.replace("Conditional", "").strip()
    
    # Split speed and the rest
    try:
        speed_part, period_part = cond_str.split("@")
    except ValueError:
        raise ValueError(f"Cannot parse speed string: {cond_str}")
    
    speed = int(speed_part.strip())
    
    # Remove parentheses and split by ';'
    period_part = period_part.strip().lstrip("(").rstrip(")")
    parts = [p.strip() for p in period_part.split(";")]
    
    days = []
    special = []
    start_time = None
    end_time = None
    
    for p in parts:
        # Check if there is a time range
        if "-" in p and any(day in p for day in ["Mo","Tu","We","Th","Fr","Sa","Su"]):
            # Example: Mo-Fr 18:00-07:00
            day_part, time_part = p.split(" ", 1)
            days.extend([day_part])
            start_time, end_time = time_part.split("-")
        else:
            # Any remaining part is treated as special days
            special.extend([d.strip() for d in p.split(",")])
    
    return ConditionalSpeed(speed=speed, days=days, start_time=start_time, end_time=end_time, special=special)
