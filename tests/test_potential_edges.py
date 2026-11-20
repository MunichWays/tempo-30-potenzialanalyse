"""Boundary cases for potential detectors and annotation helpers."""

from contextlib import redirect_stdout
from io import StringIO
import unittest

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

from PotentialCalculation.GapPotential import Tempo50GapPotential
from PotentialCalculation.ProximityPotential import ProximityPotential
from PotentialCalculation.ZebraPotential import ZebraPotential
from SpeedAnnotationUpdater import SpeedAnnotationUpdater
from tests.fixtures.fixture_data import frame


DETECTORS = (
    ProximityPotential.find_tempo50_segments_near_features,
    ZebraPotential.find_tempo50_segments_near_zebra,
)


class NearbyPotentialEdgeTests(unittest.TestCase):
    def test_empty_inputs_or_only_slow_streets_have_no_matches(self):
        """Unit under test: ProximityPotential.find_tempo50_segments_near_features
        and ZebraPotential.find_tempo50_segments_near_zebra; reject empty inputs."""
        streets = frame("proximity_speeds")
        sources = frame("proximity_speeds", "features")
        slow = streets.loc[streets.maxspeed_class == "30"]
        for detect in DETECTORS:
            for roads, features in ((None, sources), (streets, None),
                                    (streets.iloc[:0], sources),
                                    (streets, sources.iloc[:0]), (slow, sources)):
                with self.subTest(detector=detect.__qualname__, roads=roads is None,
                                  features=features is None):
                    result = detect(roads, features)
                    self.assertEqual((result.street_ids, result.opt_source_ids), ([], []))

    def test_reprojection_preserves_nearby_matches(self):
        """Unit under test: ProximityPotential.find_tempo50_segments_near_features
        and ZebraPotential.find_tempo50_segments_near_zebra; reproject inputs."""
        streets = frame("proximity_speeds").to_crs("EPSG:4326")
        sources = frame("proximity_speeds", "features").to_crs("EPSG:4326")
        for detect in DETECTORS:
            with self.subTest(detector=detect.__qualname__):
                result = detect(streets, sources, search_distance_m=8)
                self.assertCountEqual(result.street_ids, [4, 5])
                self.assertCountEqual(result.opt_source_ids, [104, 105])

    def test_distant_crossing_does_not_match_a_road(self):
        """Unit under test: ZebraPotential.find_tempo50_segments_near_zebra;
        exclude a crossing outside the search radius."""
        roads = frame("proximity_polygons")
        distant = frame("proximity_polygons", "features")
        result = ZebraPotential.find_tempo50_segments_near_zebra(
            roads, distant.loc[distant.osm_id == 3], search_distance_m=18)
        self.assertEqual((result.street_ids, result.opt_source_ids), ([], []))

    def test_conditional_tempo30_is_not_a_proximity_candidate(self):
        """Unit under test: ProximityPotential.find_tempo50_segments_near_features."""
        roads = gpd.GeoDataFrame({"osm_id": [1], "maxspeed_class": ["50"],
                                  "conditional_speed": ["30"]},
                                 geometry=[LineString([(0, 0), (10, 0)])], crs="EPSG:25832")
        sources = gpd.GeoDataFrame({"osm_id": [2]}, geometry=[Point(5, 1)],
                                   crs="EPSG:25832")
        result = ProximityPotential.find_tempo50_segments_near_features(roads, sources)
        self.assertEqual((result.street_ids, result.opt_source_ids), ([], []))


class GapHelperTests(unittest.TestCase):
    def test_direct_slow_anchors_require_both_ends(self):
        """Unit under test: Tempo50GapPotential.check_if_segment_ends_only_touch_tempo_30."""
        expected = {"gap_single_enclosed": True, "gap_open_left": False,
                    "gap_straight_continuation": False}
        for scenario, value in expected.items():
            with self.subTest(scenario=scenario):
                roads = Tempo50GapPotential.prepare_gdf(frame(scenario))
                road = roads.loc[roads.osm_id == 2].iloc[0]
                self.assertEqual(
                    Tempo50GapPotential.check_if_segment_ends_only_touch_tempo_30(road, roads),
                    value)

    def test_angles_reject_a_geometry_without_two_points(self):
        """Unit under test: Tempo50GapPotential.calculate_segment_end_angles."""
        class OnePointLine:
            coords = [(0, 0)]

        with self.assertRaisesRegex(ValueError, "at least two points"):
            Tempo50GapPotential.calculate_segment_end_angles(OnePointLine())


class AnnotationHelperTests(unittest.TestCase):
    def test_unknown_key_keeps_message_and_unknown_label(self):
        """Unit under test: SpeedAnnotationUpdater.get_feature_annotation_for_key."""
        output = StringIO()
        with redirect_stdout(output):
            result = SpeedAnnotationUpdater.get_feature_annotation_for_key("unknown", {})
        self.assertEqual(result, "Unknown")
        self.assertEqual(output.getvalue(), "Unknown potential type unknown\n")

    def test_single_label_helper_updates_only_selected_ids(self):
        """Unit under test: SpeedAnnotationUpdater.annotate_ids_with_feature_type."""
        roads = pd.DataFrame({"osm_id": [1, 2], "feature_type": ["street", "street"]})
        with redirect_stdout(StringIO()):
            updated = SpeedAnnotationUpdater.annotate_ids_with_feature_type(
                roads, [2], "T30_Potenzial_Zebrastreifen")
        self.assertEqual(updated.feature_type.tolist(),
                         ["street", "T30_Potenzial_Zebrastreifen"])
        self.assertEqual(roads.feature_type.tolist(), ["street", "street"])
        self.assertIs(SpeedAnnotationUpdater.annotate_ids_with_feature_type(
            roads, [], "T30_Potenzial_Zebrastreifen"), roads)
