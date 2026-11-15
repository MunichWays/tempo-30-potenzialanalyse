"""Offline checks for region configuration, cached data, and street grouping."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import LineString, Point

from DataRetrieval.OSMDataCache import OSMDataCache
from RegionDefinition import RegionDefinition
from RegionStorage import RegionStorage
from SegmentMerging import SegmentMerging, _endpoint_key


class RegionStorageTests(unittest.TestCase):
    def test_get_reads_and_normalizes_region_config(self):
        """Unit under test: RegionStorage.get; read a named YAML region."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.yaml").write_text(
                "display_name: ' Example ' \nbbox: [48, 11, 49, 12]\nosm_relation_id: 42\n",
                encoding="utf-8",
            )
            with patch("RegionStorage.REGIONS_DIR", root):
                region = RegionStorage.get(" Example ")
                with self.assertRaisesRegex(ValueError, "Verfügbar: example"):
                    RegionStorage.get("missing")

        self.assertEqual(region, RegionDefinition("example", "Example", 42, (48.0, 11.0, 49.0, 12.0)))

    def test_parse_rejects_invalid_region_fields(self):
        """Unit under test: RegionStorage._parse; reject malformed YAML values."""
        cases = [
            (None, "muss ein Objekt"),
            ({}, "display_name"),
            ({"display_name": " "}, "display_name"),
            ({"display_name": "A", "osm_relation_id": True}, "osm_relation_id"),
            ({"display_name": "A", "osm_relation_id": 0}, "osm_relation_id"),
            ({"display_name": "A", "bbox": [1, 2, 3]}, "vier Zahlen"),
            ({"display_name": "A", "bbox": [1, 2, True, 4]}, "vier Zahlen"),
            ({"display_name": "A", "bbox": [49, 11, 48, 12]}, "Süd-/Nordwerte"),
            ({"display_name": "A", "bbox": [48, 12, 49, 11]}, "West-/Ostwerte"),
        ]
        for data, message in cases:
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, message):
                RegionStorage._parse("example", data)


class OSMDataCacheTests(unittest.TestCase):
    def test_store_and_load_use_region_specific_json_files(self):
        """Unit under test: OSMDataCache; persist and retrieve one region's data."""
        region = RegionDefinition("example", "Example")
        other = RegionDefinition("other", "Other")
        with tempfile.TemporaryDirectory() as directory:
            cache = OSMDataCache("streets", directory)
            self.assertIsNone(cache.load_file_from_cache(region))
            cache.store_data({"elements": [{"id": 7}]}, region)
            self.assertEqual(cache.load_file_from_cache(region), {"elements": [{"id": 7}]})
            self.assertIsNone(cache.load_file_from_cache(other))
            self.assertEqual(json.loads((Path(directory) / "streets_example.json").read_text()),
                             {"elements": [{"id": 7}]})


class SegmentMergingTests(unittest.TestCase):
    def test_endpoint_key_snaps_points_to_the_requested_grid(self):
        """Unit under test: _endpoint_key; nearby endpoints share a grid key."""
        self.assertEqual(_endpoint_key(Point(0.1, 0.1)), _endpoint_key(Point(0.2, 0.2)))
        self.assertNotEqual(_endpoint_key(Point(0.1, 0.1)), _endpoint_key(Point(0.6, 0.1)))

    def test_merge_connected_segments_keeps_components_separate(self):
        """Unit under test: SegmentMerging.merge_connected_segments; group touching lines."""
        streets = gpd.GeoDataFrame({
            "name": ["A", "A", "B", "B"],
            "osm_id": [1, 2, 3, 4],
            "length_m": [10, 20, 30, 40],
        }, geometry=[
            LineString([(0, 0), (1, 0)]), LineString([(1, 0), (2, 0)]),
            LineString([(10, 0), (11, 0)]), LineString([(11, 0), (12, 0)]),
        ], crs="EPSG:25832")

        groups = SegmentMerging.merge_connected_segments(streets)

        self.assertEqual({frozenset(group["osm_ids"]): group["length_m"] for group in groups},
                         {frozenset({1, 2}): 30, frozenset({3, 4}): 70})
        self.assertTrue(all(group["geometry"].geom_type == "LineString" for group in groups))

    def test_merge_connected_segments_returns_no_groups_for_empty_input(self):
        """Unit under test: SegmentMerging.merge_connected_segments; empty streets."""
        streets = gpd.GeoDataFrame(geometry=[], crs="EPSG:25832")
        self.assertEqual(SegmentMerging.merge_connected_segments(streets), [])
