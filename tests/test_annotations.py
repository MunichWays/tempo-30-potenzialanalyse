"""Preserve individual reasons, combine overlapping reasons, and leave other roads alone."""

import unittest
import pandas as pd
from pandas.testing import assert_frame_equal
from PotentialCalculation.PotentialCalculationResult import PotentialCalculationResult
from SpeedAnnotationUpdater import SpeedAnnotationUpdater


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.streets = pd.DataFrame({
            "osm_id": range(1, 10),
            "feature_type": ["street"] * 9,
            "name": [f"Road {i}" for i in range(1, 10)],
        })
        self.configs = {
            'educational_buildings': {'speed_annotation': 'T30_Potenzial_Schule'},
            'hospitals': {'speed_annotation': 'T30_Potenzial_Krankenhaus'},
            'elderly_homes': {'speed_annotation': 'T30_Potenzial_Altenheim'},
            'playgrounds': {'speed_annotation': 'T30_Potenzial_Spielplatz'},
            'disability_facilities': {'speed_annotation': 'T30_Potenzial_Behinderteneinrichtung'},
        }

    def test_each_single_reason_has_its_own_annotation(self):
        """Unit under test: SpeedAnnotationUpdater.annotate_gdf_with_potential_type.

        One road per reason receives that reason's annotation."""
        results = {
            key: PotentialCalculationResult([i], [])
            for i, key in enumerate(("zebra", "gap", *self.configs), start=1)
        }
        annotated = SpeedAnnotationUpdater.annotate_gdf_with_potential_type(
            self.streets, results, self.configs)
        self.assertEqual(annotated.feature_type.iloc[:7].tolist(), [
            "T30_Potenzial_Zebrastreifen", "T30_Potenzial_Luecke",
            "T30_Potenzial_Schule", "T30_Potenzial_Krankenhaus", "T30_Potenzial_Altenheim",
            "T30_Potenzial_Spielplatz", "T30_Potenzial_Behinderteneinrichtung",
        ])

    def test_multiple_reasons_have_multifactor_annotation(self):
        """Unit under test: SpeedAnnotationUpdater.annotate_gdf_with_potential_type.

        Two reasons for road 8 produce the multifactor annotation."""
        results = {
            "zebra": PotentialCalculationResult([8], []),
            "gap": PotentialCalculationResult([8], []),
        }
        annotated = SpeedAnnotationUpdater.annotate_gdf_with_potential_type(
            self.streets, results, self.configs)
        self.assertEqual(annotated.loc[annotated.osm_id == 8, "feature_type"].item(),
                         "T30_Potenzial_Multifaktor")

    def test_unselected_road_and_input_data_remain_unchanged(self):
        """Unit under test: SpeedAnnotationUpdater.annotate_gdf_with_potential_type.

        Selecting road 1 leaves road 9 and the input frame unchanged."""
        before = self.streets.copy()
        results = {"zebra": PotentialCalculationResult([1], [])}
        annotated = SpeedAnnotationUpdater.annotate_gdf_with_potential_type(
            self.streets, results, self.configs)
        self.assertEqual(annotated.loc[annotated.osm_id == 9, "feature_type"].item(), "street")
        assert_frame_equal(self.streets, before)
        assert_frame_equal(annotated.drop(columns="feature_type"),
                           self.streets.drop(columns="feature_type"))
