import re
import geopandas as gpd
from shapely.geometry import Point, LineString
from DataRetrieval.OSMParser import OSMParser


class BuildingExtractor:
    @staticmethod
    def extract(data, config):
        nodes = OSMParser.build_node_index(data)
        records = []

        tag_filters = config["tags"]
        regex = config.get("regex")
        speed_annotation = config.get("speed_annotation")

        pattern = re.compile(regex, re.IGNORECASE) if regex else None

        for el in data["elements"]:
            tags = el.get("tags", {})

            # ---------------- Tag Matching ----------------
            match = False
            for key, values in tag_filters.items():
                if tags.get(key) in values:
                    match = True
                    break

            if not match:
                continue

            # ---------------- Name Filter ----------------
            name = tags.get("name")
            if pattern and (not name or not pattern.search(name)):
                continue

            # ---------------- Geometry ----------------
            if el["type"] == "node":
                geom = Point(el["lon"], el["lat"])

            elif el["type"] == "way":
                coords = [nodes[n] for n in el["nodes"] if n in nodes]
                if len(coords) < 2:
                    continue
                geom = LineString(coords)

            else:
                continue

            # ---------------- Record ----------------
            records.append({
                "osm_id": el["id"],
                "name": name,
                "speed_annotation": speed_annotation,
                "geometry": geom
            })

        return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")