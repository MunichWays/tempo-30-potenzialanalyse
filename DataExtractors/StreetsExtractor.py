import geopandas as gpd
from shapely.geometry import LineString

from DataRetrieval.OSMParser import OSMParser
from utils.speed import parse_conditional_speed

class StreetsExtractor:
    @staticmethod
    def extract(data):
        nodes = OSMParser.build_node_index(data)
        records = []

        for el in data["elements"]:
            if el["type"] != "way":
                continue

            tags = el.get("tags", {})
            highway = tags.get("highway")

            # Filter irrelevante Wege
            if not highway or highway in {"footway", "cycleway", "path", "steps"}:
                continue

            coords = [
                nodes[nid] for nid in el["nodes"]
                if nid in nodes
            ]

            if len(coords) < 2:
                continue

            record = StreetsExtractor._create_entry(el, highway, coords, tags)
            records.append(record)

        gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
        return gdf.sort_values(by="name", na_position="last")

    # --------------------------------------------------
    # Original logic restored
    # --------------------------------------------------
    @staticmethod
    def _create_entry(el, highway, coords, tags):
        maxspeed = tags.get("maxspeed")
        zone_maxspeed = tags.get("zone:maxspeed")

        # Klassifikation (wie vorher)
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
            maxspeed_class = "Keine Daten"

        # Conditional parsing
        max_speed_conditional_str = tags.get("maxspeed:conditional")

        try:
            conditional_speed = parse_conditional_speed(max_speed_conditional_str)
        except:
            conditional_speed = None

        entry = {
            "osm_id": el["id"],
            "name": tags.get("name"),
            "highway": highway,
            "maxspeed_tag": maxspeed,
            "zone_maxspeed_tag": zone_maxspeed,
            "maxspeed_class": maxspeed_class,
            "geometry": LineString(coords)
        }

        if conditional_speed is None:
            entry.update({
                "conditional_speed": None,
                "cond_speed_days": None,
                "cond_speed_starttime": None,
                "cond_speed_endtime": None,
                "cond_speed_special": None
            })
        else:
            entry.update({
                "conditional_speed": str(conditional_speed.speed),
                "cond_speed_days": ",".join(conditional_speed.days),
                "cond_speed_starttime": conditional_speed.start_time,
                "cond_speed_endtime": conditional_speed.end_time,
                "cond_speed_special": ",".join(conditional_speed.special)
            })

        return entry