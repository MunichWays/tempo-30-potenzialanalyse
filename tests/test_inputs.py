"""Interpret speed information without inventing missing values."""

import unittest
from DataRetrieval.SegmentRetrieval import create_gdf_entry
from tests.fixtures.fixture_data import features


class InputTests(unittest.TestCase):
    @staticmethod
    def _entry(case):
        feature = next(f for f in features("speed_tags", "streets")
                       if f["properties"]["input_case"] == case)
        props = feature["properties"]
        return create_gdf_entry({"id": props["osm_id"]}, props["highway"],
                                feature["geometry"]["coordinates"], props["tags"])

    def test_unknown_speed_is_not_assumed_to_be_tempo50(self):
        """Unit under test: DataRetrieval.SegmentRetrieval.create_gdf_entry.

        Missing or invalid speed tags remain unknown; the analysis must not guess."""
        for case in ("missing_speed", "invalid_speed"):
            with self.subTest(case=case):
                self.assertEqual(self._entry(case)["maxspeed_class"], "Keine Daten")

    def test_conditional_speed_keeps_its_schedule_and_permanent_speed(self):
        """Unit under test: DataRetrieval.SegmentRetrieval.create_gdf_entry.

        A time-limited restriction supplements the permanent speed instead of replacing it."""
        for case in ("conditional_speed", "conditional_prefix"):
            with self.subTest(case=case):
                entry = self._entry(case)
                self.assertEqual(entry["maxspeed_class"], "50")
                self.assertEqual({key: entry[key] for key in (
                    "conditional_speed", "cond_speed_days", "cond_speed_starttime",
                    "cond_speed_endtime", "cond_speed_special",
                )}, {"conditional_speed": "30", "cond_speed_days": "Mo-Fr",
                     "cond_speed_starttime": "18:00", "cond_speed_endtime": "07:00",
                     "cond_speed_special": "Sa,Su,PH"})
