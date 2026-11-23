import unittest

import geopandas as gpd
from shapely.geometry import LineString, Point

from PotentialCalculation.ZebraPotential import ZebraPotential


class ZebraPotentialTests(unittest.TestCase):
    def test_finds_distinct_streets_and_zebras_within_search_distance(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [101, 102, 103],
                "maxspeed_class": ["50", "60", "30"],
                "geometry": [
                    LineString([(0, 0), (20, 0)]),
                    LineString([(100, 0), (120, 0)]),
                    LineString([(200, 0), (220, 0)]),
                ],
            },
            crs="EPSG:25832",
        )
        zebras = gpd.GeoDataFrame(
            {"osm_id": [201, 202], 
             "geometry": [Point(5, 0), Point(105, 1)]},
            crs="EPSG:25832",
        )

        result = ZebraPotential.find_tempo50_segments_near_zebra(
            streets, zebras, search_distance_m=2
        )

        self.assertEqual(result.street_ids, [101, 102])
        self.assertEqual(result.opt_source_ids, [201, 202])

    def test_returns_empty_result_when_input_or_matching_data_is_empty(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [101],
                "maxspeed_class": ["30"],
                "geometry": [LineString([(0, 0), (20, 0)])],
            },
            crs="EPSG:25832",
        )
        zebras = gpd.GeoDataFrame(
            {"osm_id": [201], "geometry": [Point(5, 0)]},
            crs="EPSG:25832",
        )

        empty = ZebraPotential.find_tempo50_segments_near_zebra(
            gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:25832"),
            zebras,
        )
        no_match = ZebraPotential.find_tempo50_segments_near_zebra(
            streets, zebras
        )
        no_zebras = ZebraPotential.find_tempo50_segments_near_zebra(
            streets,
            gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:25832"),
        )

        self.assertEqual(empty.street_ids, [])
        self.assertEqual(empty.opt_source_ids, [])
        self.assertEqual(no_match.street_ids, [])
        self.assertEqual(no_zebras.street_ids, [])


if __name__ == "__main__":
    unittest.main()
