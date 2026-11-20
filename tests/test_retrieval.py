"""Exercise Overpass query, cache, and geometry handling without network access."""

from contextlib import redirect_stdout
from io import StringIO
import re
import unittest
from unittest.mock import Mock, patch

import geopandas as gpd
import requests
from shapely.geometry import Point

from DataRetrieval.BuildingRetrieval import BuildingRetrieval
from DataRetrieval.SegmentRetrieval import SegmentRetrieval, create_gdf_entry, parse_conditional_speed
from DataRetrieval.SpecificBuildingRetrieval import SpecificBuildingRetrieval
from DataRetrieval.ZebraCrossingRetrieval import ZebraCrossingRetrieval
from RegionDefinition import RegionDefinition


REGION = RegionDefinition("example", "Example", bbox=(48, 11, 49, 12))
RETRIEVERS = (SegmentRetrieval, BuildingRetrieval, ZebraCrossingRetrieval)


def _retriever(cls):
    instance = cls.__new__(cls)
    instance.timeout = 7
    if cls is BuildingRetrieval:
        instance.tags = {"amenity": ["school", "hospital"]}
        instance.name_filter_regex = None
    return instance


class RetrievalRequestTests(unittest.TestCase):
    def test_queries_use_region_bounds_and_munich_fallback(self):
        """Unit under test: _build_query on SegmentRetrieval,
        BuildingRetrieval, and ZebraCrossingRetrieval; select region bounds."""
        munich = RegionDefinition("münchen", "München")
        for cls in RETRIEVERS:
            with self.subTest(cls=cls.__name__):
                instance = _retriever(cls)
                bounded = instance._build_query(REGION)
                self.assertIn("48,11,49,12", bounded)
                self.assertIn("timeout:7", bounded)
                self.assertIn("highway" if cls is SegmentRetrieval else
                              "amenity" if cls is BuildingRetrieval else "crossing", bounded)
                self.assertIn("München", instance._build_query(munich))

    def test_raw_fetch_returns_json_after_a_retry(self):
        """Unit under test: _fetch_raw on SegmentRetrieval,
        BuildingRetrieval, and ZebraCrossingRetrieval; retry a failed request."""
        response = Mock()
        response.json.return_value = {"elements": [{"id": 7}]}
        for cls in RETRIEVERS:
            with self.subTest(cls=cls.__name__), patch("requests.post", side_effect=[
                requests.exceptions.ConnectionError("offline"), response,
            ]) as post, patch("time.sleep") as sleep, redirect_stdout(StringIO()):
                self.assertEqual(_retriever(cls)._fetch_raw("query"), {"elements": [{"id": 7}]})
                self.assertEqual(post.call_count, 2)
                self.assertEqual(post.call_args.kwargs["timeout"], 7)
                sleep.assert_called_once_with(1)

    def test_raw_fetch_stops_after_six_failures(self):
        """Unit under test: _fetch_raw on SegmentRetrieval,
        BuildingRetrieval, and ZebraCrossingRetrieval; bound failed retries."""
        for cls in RETRIEVERS:
            with self.subTest(cls=cls.__name__), patch("requests.post", side_effect=
                              requests.exceptions.Timeout("offline")) as post, \
                    patch("time.sleep") as sleep, redirect_stdout(StringIO()):
                with self.assertRaisesRegex(RuntimeError, "Overpass failed"):
                    _retriever(cls)._fetch_raw("query")
                self.assertEqual(post.call_count, 6)
                self.assertEqual([call.args[0] for call in sleep.call_args_list],
                                 [1, 2, 4, 8, 16, 32])

    def test_cached_fetch_returns_cached_data_without_request(self):
        """Unit under test: _fetch_raw_cached on SegmentRetrieval,
        BuildingRetrieval, and ZebraCrossingRetrieval; use a cache hit."""
        for cls in RETRIEVERS:
            with self.subTest(cls=cls.__name__), redirect_stdout(StringIO()):
                instance = _retriever(cls)
                instance.datacache = Mock()
                instance.datacache.load_file_from_cache.return_value = {"cached": True}
                instance._build_query = Mock()
                instance._fetch_raw = Mock()
                self.assertEqual(instance._fetch_raw_cached(REGION), {"cached": True})
                instance._build_query.assert_not_called()
                instance._fetch_raw.assert_not_called()
                instance.datacache.store_data.assert_not_called()

    def test_cached_fetch_queries_and_stores_cache_miss(self):
        """Unit under test: _fetch_raw_cached on SegmentRetrieval,
        BuildingRetrieval, and ZebraCrossingRetrieval; store a cache miss."""
        for cls in RETRIEVERS:
            with self.subTest(cls=cls.__name__), redirect_stdout(StringIO()):
                instance = _retriever(cls)
                instance.datacache = Mock()
                instance.datacache.load_file_from_cache.return_value = None
                instance._build_query = Mock(return_value="query")
                instance._fetch_raw = Mock(return_value={"fresh": True})
                self.assertEqual(instance._fetch_raw_cached(REGION), {"fresh": True})
                instance._build_query.assert_called_once_with(REGION)
                if cls is SegmentRetrieval:
                    instance._fetch_raw.assert_called_once_with("query")
                else:
                    instance._fetch_raw.assert_called_once_with(query="query")
                instance.datacache.store_data.assert_called_once_with(
                    data={"fresh": True}, region_definition=REGION)


class SegmentRetrievalTests(unittest.TestCase):
    def test_fetch_builds_sorted_streets_and_ignores_unusable_ways(self):
        """Unit under test: SegmentRetrieval.fetch_as_geodataframe; select usable roads."""
        elements = [
            {"type": "node", "id": 1, "lon": 11, "lat": 48},
            {"type": "node", "id": 2, "lon": 11.001, "lat": 48},
            {"type": "node", "id": 3, "lon": 11.002, "lat": 48},
            {"type": "way", "id": 10, "nodes": [1, 2], "tags":
             {"highway": "residential", "name": "Z Road", "maxspeed": "50"}},
            {"type": "way", "id": 20, "nodes": [2, 3], "tags":
             {"highway": "residential", "name": "A Road", "maxspeed": "30"}},
            {"type": "way", "id": 30, "nodes": [1, 2], "tags": {"highway": "footway"}},
            {"type": "way", "id": 40, "nodes": [1, 99], "tags": {"highway": "residential"}},
        ]
        instance = _retriever(SegmentRetrieval)
        instance._fetch_raw_cached = Mock(return_value={"elements": elements})
        roads = instance.fetch_as_geodataframe(REGION)
        self.assertEqual(roads.osm_id.tolist(), [20, 10])
        self.assertEqual(roads.maxspeed_class.tolist(), ["30", "50"])
        self.assertTrue(all(roads.geometry.geom_type == "LineString"))

    def test_entry_classifies_each_permanent_speed_and_bad_conditionals(self):
        """Unit under test: create_gdf_entry; classify speed tags and invalid schedules."""
        expected = {"10": "10", "20": "20", "30": "30", "50": "50", "60": "60"}
        for speed, classification in expected.items():
            with self.subTest(speed=speed):
                entry = create_gdf_entry({"id": 7}, "residential", [(0, 0), (1, 0)],
                                         {"maxspeed": speed})
                self.assertEqual(entry["maxspeed_class"], classification)
                self.assertIsNone(entry["conditional_speed"])
        zone = create_gdf_entry({"id": 7}, "residential", [(0, 0), (1, 0)],
                                {"zone:maxspeed": "30", "maxspeed:conditional": "bad"})
        self.assertEqual(zone["maxspeed_class"], "30_Zone")
        self.assertIsNone(zone["conditional_speed"])

    def test_conditional_parser_rejects_invalid_input_and_keeps_special_days(self):
        """Unit under test: parse_conditional_speed; parse schedules and reject bad input."""
        parsed = parse_conditional_speed("Conditional 30 @ (Mo-Fr 18:00-07:00; Sa, Su, PH)")
        self.assertEqual((parsed.speed, parsed.days, parsed.start_time, parsed.end_time,
                          parsed.special), (30, ["Mo-Fr"], "18:00", "07:00",
                                           ["Sa", "Su", "PH"]))
        with self.assertRaisesRegex(ValueError, "Cannot parse speed string"):
            parse_conditional_speed("30")
        with self.assertRaises(ValueError):
            parse_conditional_speed("fast @ (Mo-Fr 18:00-07:00)")


class BuildingRetrievalTests(unittest.TestCase):
    def test_fetch_converts_nodes_and_ways_to_geometries(self):
        """Unit under test: BuildingRetrieval.fetch; retain point, line, and polygon features."""
        elements = [
            {"type": "node", "id": 1, "lon": 11, "lat": 48, "tags": {"name": "Campus"}},
            {"type": "node", "id": 2, "lon": 11.001, "lat": 48},
            {"type": "node", "id": 3, "lon": 11.001, "lat": 48.001},
            {"type": "way", "id": 10, "nodes": [1, 2], "tags": {"name": "Line"}},
            {"type": "way", "id": 20, "nodes": [1, 2, 3, 1], "tags": {"name": "Area"}},
            {"type": "way", "id": 30, "nodes": [1, 99]},
            {"type": "relation", "id": 40},
        ]
        instance = _retriever(BuildingRetrieval)
        instance._fetch_raw_cached = Mock(return_value={"elements": elements})
        features = instance.fetch(REGION).set_index("osm_id")
        self.assertEqual(features.loc[1, "geometry"].geom_type, "Point")
        self.assertEqual(features.loc[10, "geometry"].geom_type, "LineString")
        self.assertEqual(features.loc[20, "geometry"].geom_type, "Polygon")
        self.assertEqual(features.loc[1, "name"], "Campus")
        self.assertNotIn(30, features.index)

    def test_fetch_filters_names_and_returns_none_when_empty(self):
        """Unit under test: BuildingRetrieval.fetch; apply optional name regex."""
        instance = _retriever(BuildingRetrieval)
        instance.name_filter_regex = re.compile("school", re.I)
        instance._fetch_raw_cached = Mock(return_value={"elements": [
            {"type": "node", "id": 1, "lon": 11, "lat": 48, "tags": {"name": "School North"}},
            {"type": "node", "id": 2, "lon": 11, "lat": 48, "tags": {"name": "Library"}},
            {"type": "node", "id": 3, "lon": 11, "lat": 48},
        ]})
        self.assertEqual(instance.fetch(REGION).osm_id.tolist(), [1])
        instance._fetch_raw_cached.return_value = {"elements": []}
        with redirect_stdout(StringIO()):
            self.assertIsNone(instance.fetch(REGION))

    def test_specific_retrieval_omits_empty_categories(self):
        """Unit under test: SpecificBuildingRetrieval.retrieve_building_data; keep found types."""
        school = gpd.GeoDataFrame({"name": ["School"]}, geometry=[Point(11, 48)], crs="EPSG:4326")
        configs = {"schools": {"tags": {"amenity": ["school"]}},
                   "clinics": {"tags": {"amenity": ["clinic"]}}}
        with patch("DataRetrieval.SpecificBuildingRetrieval.BuildingRetrieval") as cls, \
                redirect_stdout(StringIO()):
            cls.return_value.fetch.side_effect = [school, None]
            result = SpecificBuildingRetrieval.retrieve_building_data(REGION, configs)
        self.assertEqual(list(result), ["schools"])
        self.assertIs(result["schools"], school)


class ZebraCrossingRetrievalTests(unittest.TestCase):
    def test_fetch_keeps_crossing_points_and_ways(self):
        """Unit under test: ZebraCrossingRetrieval.fetch_zebra_crossings; build geometries."""
        instance = _retriever(ZebraCrossingRetrieval)
        instance._fetch_raw_cached = Mock(return_value={"elements": [
            {"type": "node", "id": 1, "lon": 11, "lat": 48,
             "tags": {"crossing": "zebra", "name": "A"}},
            {"type": "node", "id": 2, "lon": 11.001, "lat": 48},
            {"type": "way", "id": 10, "nodes": [1, 2], "tags": {"crossing": "zebra"}},
            {"type": "way", "id": 20, "nodes": [1, 99]},
            {"type": "relation", "id": 30},
        ]})
        crossings = instance.fetch_zebra_crossings(REGION).set_index("osm_id")
        self.assertEqual(crossings.loc[1, "geometry"].geom_type, "Point")
        self.assertEqual(crossings.loc[10, "geometry"].geom_type, "LineString")
        self.assertNotIn(20, crossings.index)

    def test_fetch_returns_none_for_no_crossings(self):
        """Unit under test: ZebraCrossingRetrieval.fetch_zebra_crossings; empty response."""
        instance = _retriever(ZebraCrossingRetrieval)
        instance._fetch_raw_cached = Mock(return_value={"elements": []})
        with redirect_stdout(StringIO()):
            self.assertIsNone(instance.fetch_zebra_crossings(REGION))
