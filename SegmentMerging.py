
from shapely.geometry import Point
import networkx as nx
import geopandas as gpd

from shapely.ops import linemerge

def endpoint_key(pt, tol=0.5):
    # snap to grid to make stable keys
    return (round(pt.x / tol), round(pt.y / tol))

class SegmentMerging:
    def merge_connected_segments(gdf_name: gpd.GeoDataFrame, tol = 0.5) -> list[dict]:
        G = nx.Graph()

        # Map endpoint keys → segments
        endpoint_map = {}

        for idx, row in gdf_name.iterrows():
            geom = row.geometry
            p_start = Point(geom.coords[0])
            p_end = Point(geom.coords[-1])

            k_start = endpoint_key(p_start, tol)
            k_end = endpoint_key(p_end, tol)

            G.add_node(idx)

            for k in (k_start, k_end):
                if k in endpoint_map:
                    for other_idx in endpoint_map[k]:
                        G.add_edge(idx, other_idx)
                endpoint_map.setdefault(k, []).append(idx)

        results = []

        for comp in nx.connected_components(G):
            sub = gdf_name.loc[list(comp)]

            merged_geom = linemerge(sub.geometry.unary_union)

            results.append({
                "name": sub.iloc[0]["name"],
                "osm_ids": list(sub["osm_id"]),
                "length_m": sub["length_m"].sum(),
                "geometry": merged_geom,
            })

        return results