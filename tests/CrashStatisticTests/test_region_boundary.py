import unittest
from unittest.mock import patch

from shapely.geometry import Point

from DataRetrieval.OSMDataCache import OSMDataCache
from DataRetrieval.RegionBoundaryRetrieval import RegionBoundaryRetrieval
from RegionDefinition import RegionDefinition


def way(role, coords):
    return {
        "type": "way",
        "ref": 1,
        "role": role,
        "geometry": [{"lon": lon, "lat": lat} for lon, lat in coords],
    }


def relation(*members):
    return {"elements": [{"type": "relation", "id": 42, "members": list(members)}]}


class RegionBoundaryTests(unittest.TestCase):

    def test_bbox_region_is_a_box_without_query(self):
        region = RegionDefinition(key="test", display_name="Test", bbox=(48.0, 11.0, 48.2, 11.4))

        with patch("requests.post") as post:
            polygon = RegionBoundaryRetrieval().fetch_region_polygon(region)

        post.assert_not_called()
        self.assertEqual(polygon.bounds, (11.0, 48.0, 11.4, 48.2))

    def test_outer_ring_split_into_several_ways(self):
        data = relation(
            way("outer", [(0, 0), (2, 0), (2, 2)]),
            way("outer", [(2, 2), (0, 2), (0, 0)]),
        )

        polygon = RegionBoundaryRetrieval.polygon_from_relation(data)

        self.assertAlmostEqual(polygon.area, 4)

    def test_inner_ring_is_a_hole(self):
        data = relation(
            way("outer", [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]),
            way("inner", [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)]),
        )

        polygon = RegionBoundaryRetrieval.polygon_from_relation(data)

        self.assertAlmostEqual(polygon.area, 15)
        self.assertFalse(polygon.contains(Point(1.5, 1.5)))
        self.assertTrue(polygon.contains(Point(3, 3)))

    def test_relation_region_queries_boundary_once_and_caches(self):
        region = RegionDefinition(key="test", display_name="Test", osm_relation_id=42)
        data = relation(way("outer", [(0, 0), (1, 0), (1, 1), (0, 0)]))

        with patch("requests.post") as post, \
             patch.object(OSMDataCache, "load_file_from_cache", return_value=None), \
             patch.object(OSMDataCache, "store_data") as store:
            post.return_value.json.return_value = data
            polygon = RegionBoundaryRetrieval().fetch_region_polygon(region)

        query = post.call_args.kwargs["data"]["data"]
        self.assertIn("rel(42);", query)
        self.assertIn("out geom;", query)
        store.assert_called_once()
        self.assertAlmostEqual(polygon.area, 0.5)

    def test_missing_outer_ring_raises(self):
        with self.assertRaises(ValueError):
            RegionBoundaryRetrieval.polygon_from_relation(relation())


if __name__ == "__main__":
    unittest.main()
