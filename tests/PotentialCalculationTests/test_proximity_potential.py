import unittest

import geopandas as gpd
from shapely.geometry import LineString, Point

from PotentialCalculation.ProximityPotential import ProximityPotential


class ProximityPotentialTests(unittest.TestCase):
    def test_finds_tempo50_and_tempo60_segments_near_features(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [301, 302, 303, 304],
                "maxspeed_class": ["50", "60", "30", "50"],
                "conditional_speed": [None, None, None, "30"],
                "geometry": [
                    LineString([(0, 0), (20, 0)]),
                    LineString([(100, 0), (120, 0)]),
                    LineString([(200, 0), (220, 0)]),
                    LineString([(300, 0), (320, 0)]),
                ],
            },
            crs="EPSG:25832",
        )
        features = gpd.GeoDataFrame(
            {"osm_id": [401, 402], "geometry": [Point(10, 0), Point(110, 0)]},
            crs="EPSG:25832",
        )

        result = ProximityPotential.find_tempo50_segments_near_features(
            streets, features, search_distance_m=15
        )

        self.assertEqual(result.street_ids, [301, 302])
        self.assertEqual(result.opt_source_ids, [401, 402])

    def test_returns_empty_result_for_empty_inputs(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [301],
                "maxspeed_class": ["50"],
                "conditional_speed": [None],
                "geometry": [LineString([(0, 0), (20, 0)])],
            },
            crs="EPSG:25832",
        )
        empty_features = gpd.GeoDataFrame(
            columns=["geometry"], crs="EPSG:25832"
        )

        result = ProximityPotential.find_tempo50_segments_near_features(
            streets, empty_features
        )

        self.assertEqual(result.street_ids, [])
        self.assertEqual(result.opt_source_ids, [])


if __name__ == "__main__":
    unittest.main()
