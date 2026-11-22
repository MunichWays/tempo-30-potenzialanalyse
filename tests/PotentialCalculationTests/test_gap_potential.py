import unittest

import geopandas as gpd
from shapely.geometry import LineString

from PotentialCalculation.GapPotential import Tempo50GapPotential


class GapPotentialTests(unittest.TestCase):
    def test_calculates_compass_bearing_for_both_segment_ends(self):
        line = LineString([(0, 0), (10, 0), (10, 10)])

        start_angle, end_angle = Tempo50GapPotential.calculate_segment_end_angles(line)

        self.assertAlmostEqual(start_angle, 90)
        self.assertAlmostEqual(end_angle, 180)

    def test_calculate_segment_end_angles_rejects_empty_lines(self):
        with self.assertRaises(ValueError):
            Tempo50GapPotential.calculate_segment_end_angles(
                LineString()
            )

    def test_axis_angle_diff_treats_opposite_directions_as_same_axis(self):
        self.assertAlmostEqual(
            Tempo50GapPotential.axis_angle_diff(0, 180), 0
        )
        self.assertAlmostEqual(
            Tempo50GapPotential.axis_angle_diff(350, 10), 20
        )
        self.assertAlmostEqual(
            Tempo50GapPotential.axis_angle_diff(45, 135), 90
        )

    def test_finds_gap_between_tempo30_segments(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [501, 502, 503],
                "maxspeed_class": ["30", "50", "30"],
                "conditional_speed": [None, None, None],
                "name": ["left", "gap", "right"],
                "geometry": [
                    LineString([(-100, 0), (-50, 0)]),
                    LineString([(-50, 0), (50, 0)]),
                    LineString([(50, 0), (100, 0)]),
                ],
            },
            crs="EPSG:25832",
        )

        result = Tempo50GapPotential.find_all_tempo_50_gaps(streets)

        self.assertEqual(result.street_ids, [502])

    def test_gap_filter_excludes_conditional_tempo30(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [601, 602, 603],
                "maxspeed_class": ["30", "50", "30"],
                "conditional_speed": [None, "30", None],
                "name": ["left", "conditional", "right"],
                "geometry": [
                    LineString([(-100, 0), (-50, 0)]),
                    LineString([(-50, 0), (50, 0)]),
                    LineString([(50, 0), (100, 0)]),
                ],
            },
            crs="EPSG:25832",
        )

        result = Tempo50GapPotential.find_all_tempo_50_gaps(streets)

        self.assertEqual(result.street_ids, [])


    def test_finds_gap_consisting_of_multiple_short_segments(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [501, 502, 503, 504],
                "maxspeed_class": ["30", "50", "50", "30"],
                "conditional_speed": [None, None, None, None],
                "name": ["left", "first_50", "second_50", "right"],
                "geometry": [
                    LineString([(-100, 0), (-50, 0)]),
                    LineString([(-50, 0), (0, 0)]),
                    LineString([(0, 0), (50, 0)]),
                    LineString([(50, 0), (100, 0)]),
                ],
            },
            crs="EPSG:25832",
        )

        result = Tempo50GapPotential.find_all_tempo_50_gaps(streets)

        self.assertEqual(sorted(result.street_ids, reverse=False), [502, 503])


    def test_multiple_short_segments_are_detected_with_conditional_boundaries(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [701, 702, 703, 704, 705],
                "maxspeed_class": [
                    "30",
                    "50",
                    "50",
                    "50",
                    "30"
                ],
                "conditional_speed": [
                    None,
                    None,
                    "30",
                    None,
                    None
                ],
                "name": [
                    "left",
                    "gap_1",
                    "conditional_30",
                    "gap_2",
                    "right"
                ],
                "geometry": [
                    LineString([(-100, 0), (-50, 0)]),
                    LineString([(-50, 0), (0, 0)]),
                    LineString([(0, 0), (50, 0)]),
                    LineString([(50, 0), (100, 0)]),
                    LineString([(100, 0), (150, 0)])
                ],
            },
            crs="EPSG:25832",
        )

        result = Tempo50GapPotential.find_all_tempo_50_gaps(streets)

        self.assertEqual(sorted(result.street_ids, reverse=False), [702, 704])

    def test_single_segment_over_500_meters_not_detected(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [801, 802, 803],
                "maxspeed_class": ["30", "50", "30"],
                "conditional_speed": [None, None, None],
                "name": ["left", "long_gap", "right"],
                "geometry": [
                    LineString([(0, 0), (100, 0)]),
                    LineString([(100, 0), (601, 0)]),
                    LineString([(601, 0), (700, 0)]),
                ],
            },
            crs="EPSG:25832",
        )

        result = Tempo50GapPotential.find_all_tempo_50_gaps(streets)

        self.assertEqual(result.street_ids, [])

    def test_multiple_segments_over_500_meters_are_not_detected(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [801, 802, 803, 804, 805, 806],
                "maxspeed_class": ["30", "50", "30", "30", "60", "30"],
                "conditional_speed": [None, None, None, None, None, None],
                "name": ["left_1", "gap_1", "right_1", "left_2", "gap_2", "right_2"],
                "geometry": [
                    LineString([(-500, 0), (-250, 0)]),
                    LineString([(-250, 0), (250, 0)]),
                    LineString([(250, 0), (500, 0)]),
                    LineString([(-500, 200), (-250, 200)]),
                    LineString([(-250, 200), (250, 200)]),
                    LineString([(250, 200), (500, 200)]),
                ],
            },
            crs="EPSG:25832",
        )

        result = Tempo50GapPotential.find_all_tempo_50_gaps(streets)

        self.assertEqual(result.street_ids, [])

    def test_detection_follows_most_straight_segments_in_both_directions(self):
        streets = gpd.GeoDataFrame(
            {
                "osm_id": [901, 902, 903, 904, 905, 906, 907],
                "maxspeed_class": ["30", "50", "50", "30", "30", "30", "30"],
                "conditional_speed": [None, None, None, None, None, None, None],
                "name": [
                    "start",
                    "gap",
                    "straight_direction_start",
                    "straight_direction_follow_up",
                    "segment_that_turns_left",
                    "segment_that_turns_slightly_right",
                    "unrelated",
                ],
                "geometry": [
                    LineString([(0, 0), (50, 0)]),
                    LineString([(50, 0), (100, 0)]),
                    LineString([(100, 0), (150, 0)]),
                    LineString([(150, 0), (200, 0)]),
                    LineString([(100, 0), (150, 50)]),
                    LineString([(100, 0), (150, -1)]),
                    LineString([(500, 500), (550, 500)]),
                ],
            },
            crs="EPSG:25832",
        )

        result = Tempo50GapPotential.find_all_tempo_50_gaps(streets)

        self.assertEqual(sorted(result.street_ids, reverse=False), [902, 903])


if __name__ == "__main__":
    unittest.main()
