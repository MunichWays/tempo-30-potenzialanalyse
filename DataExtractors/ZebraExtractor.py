import geopandas as gpd
from shapely.geometry import Point, LineString
from DataRetrieval.OSMParser import OSMParser


class ZebraExtractor:
    @staticmethod
    def extract(data):
        nodes = OSMParser.build_node_index(data)
        records = []

        for el in data["elements"]:
            tags = el.get("tags", {})

            if tags.get("crossing") != "zebra":
                continue

            if el["type"] == "node":
                geom = Point(el["lon"], el["lat"])
            elif el["type"] == "way":
                coords = [nodes[n] for n in el["nodes"] if n in nodes]
                if len(coords) < 2:
                    continue
                geom = LineString(coords)
            else:
                continue

            records.append({ "osm_id": el["id"], "element_type": el["type"], "crossing": tags.get("crossing"), "highway": tags.get("highway"), "name": tags.get("name"), "street" : tags.get("addr:street"), "geometry": geom })

        return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")