"""Keep the map examples valid, grouped and documented alongside their tests."""

import json
import unittest
from collections import Counter
from itertools import combinations
from pathlib import Path
from shapely.geometry import shape
from tests.fixtures.fixture_data import FIXTURE_PATH


class FixtureTests(unittest.TestCase):
    @staticmethod
    def _load_layers():
        scenarios = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        areas = json.loads(FIXTURE_PATH.with_name("groups.geojson").read_text(encoding="utf-8"))
        return scenarios, areas

    def test_features_have_valid_geometry_and_documented_outcomes(self):
        """Unit under test: the scenarios.geojson and groups.geojson feature contract."""
        data, areas = self._load_layers()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertTrue(all(f["properties"]["role"] == "group" for f in areas["features"]))
        self.assertTrue(all(f["properties"]["role"] != "group" for f in data["features"]))
        ids = []
        for feature in areas["features"] + data["features"]:
            props = feature["properties"]
            with self.subTest(feature=feature["id"]):
                geometry = shape(feature["geometry"])
                self.assertTrue(geometry.is_valid and not geometry.is_empty)
                west, south, east, north = geometry.bounds
                self.assertTrue(4 < west <= east < 6 and 54 < south <= north < 56)
                for field in ("group_id", "group_title"):
                    self.assertTrue(props[field], field)
                if props["role"] != "group":
                    for field in ("description", "expected_outcome"):
                        self.assertTrue(props[field], field)
                    if props["role"] != "guide":
                        for field in ("input_details", "expected_details"):
                            self.assertTrue(props[field], field)
                    self.assertTrue((Path(__file__).parent / props["test_file"]).is_file())
                self.assertEqual(props["_umap_options"]["popupShape"], "Default")
                self.assertEqual(feature["id"], props["fixture_id"])
            ids.append(feature["id"])
        self.assertEqual(len(ids), len(set(ids)))
