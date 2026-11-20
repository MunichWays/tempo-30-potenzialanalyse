"""Exercise GeoJSON and plotting output with local data."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString, Point

from DataOutput.GeoJsonCreator import GeoJsonCreator
from DataOutput.PlaygroundConsolidation import PlaygroundConsolidation
from DataOutput.PrintOutput import PrintOutput
from DataOutput.StreetPlot import StreetPlot


def _points(ids, candidate):
    return gpd.GeoDataFrame({
        "osm_id": ids,
        "name": [f"Place {value}" for value in ids],
        "potential_candidate": candidate,
        "street": [None] * len(ids),
        "housenumber": [None] * len(ids),
        "website": [None] * len(ids),
        "operator": [None] * len(ids),
    }, geometry=[Point(11 + value * 0.00001, 48) for value in ids], crs="EPSG:4326")


class PlaygroundConsolidationTests(unittest.TestCase):
    def test_nearby_inactive_points_merge_and_candidates_remain(self):
        """Unit under test: PlaygroundConsolidation.summarize_playground_features."""
        playgrounds = _points([1, 2, 100, 200], [False, False, False, True])
        result = PlaygroundConsolidation.summarize_playground_features(playgrounds)
        self.assertEqual(len(result), 3)
        self.assertCountEqual(result.potential_candidate.tolist(), [False, False, True])
        self.assertTrue(all(result.geometry.geom_type == "Point"))

    def test_no_inactive_points_returns_an_unchanged_copy(self):
        """Unit under test: PlaygroundConsolidation.summarize_playground_features."""
        playgrounds = _points([1], [True])
        result = PlaygroundConsolidation.summarize_playground_features(playgrounds)
        self.assertEqual(result.osm_id.tolist(), [1])
        self.assertIsNot(result, playgrounds)


class GeoJsonCreatorTests(unittest.TestCase):
    def test_export_labels_speeds_and_removes_null_properties(self):
        """Unit under test: GeoJsonCreator.create_geojson_layer_files."""
        roads = gpd.GeoDataFrame({
            "osm_id": [1, 2], "name": ["A", "B"],
            "maxspeed_class": ["50", "30"],
            "feature_type": ["T30_Potenzial_Zebrastreifen", "T30_Potenzial_Multifaktor"],
            "conditional_speed": [None, "30"],
            "cond_speed_days": [None, "Mo-Fr"],
            "cond_speed_starttime": [None, "08:00"],
            "cond_speed_endtime": [None, "09:00"],
            "cond_speed_special": [None, None],
        }, geometry=[LineString([(11, 48), (11.001, 48)]),
                     LineString([(11.001, 48), (11.002, 48)])], crs="EPSG:4326")
        zebra = _points([10], [True])
        buildings = {"playgrounds": _points([20], [False]),
                     "schools": _points([30], [True])}
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            output = Path(directory) / "export"
            GeoJsonCreator.create_geojson_layer_files(output, roads, roads, zebra, buildings)
            street_data = json.loads((output / "potential_streets.geojson").read_text())
            limit_data = json.loads((output / "streets_and_limit.geojson").read_text())
            playground_data = json.loads((output / "playgrounds.geojson").read_text())
            self.assertTrue((output / "schools.geojson").is_file())
        self.assertEqual([feature["properties"]["feature_type"] for feature in
                          street_data["features"]],
                         ["Potenzial durch Zebrastreifen", "Potenzial durch mehrere Faktoren"])
        self.assertEqual([feature["properties"]["maxspeed_class"] for feature in
                          limit_data["features"]], ["T50+", "Conditional-T30"])
        self.assertNotIn("cond_speed_days", limit_data["features"][0]["properties"])
        self.assertNotIn("housenumber", playground_data["features"][0]["properties"])
        self.assertEqual(roads.feature_type.iloc[0], "T30_Potenzial_Zebrastreifen")


class PrintOutputTests(unittest.TestCase):
    def test_print_streets_summarizes_named_segments(self):
        """Unit under test: PrintOutput.print_streets; summarize local road lengths."""
        streets = gpd.GeoDataFrame({
            "osm_id": [1, 2], "name": ["Main", "Main"],
            "highway": ["residential"] * 2,
            "maxspeed_tag": ["50"] * 2,
            "zone_maxspeed_tag": [None] * 2,
        }, geometry=[LineString([(0, 0), (30, 0)]),
                     LineString([(30, 0), (40, 0)])], crs="EPSG:25832")
        output = StringIO()
        with redirect_stdout(output):
            PrintOutput.print_streets(streets)
        self.assertIn("more than 20 m", output.getvalue())
        self.assertIn("Main", output.getvalue())


class StreetPlotTests(unittest.TestCase):
    def test_extract_endpoints_handles_lines_and_multilines(self):
        """Unit under test: StreetPlot._extract_start_end_points; find terminal points."""
        roads = gpd.GeoDataFrame(geometry=[
            LineString([(0, 0), (1, 0)]),
            MultiLineString([[(2, 0), (3, 0)], [(3, 0), (4, 0)]]),
        ], crs="EPSG:25832")
        starts, ends = StreetPlot._extract_start_end_points(roads)
        self.assertEqual([point.x for point in starts.geometry], [0, 2])
        self.assertEqual([point.x for point in ends.geometry], [1, 4])

    def test_plot_map_adds_crossing_building_and_potential_legends(self):
        """Unit under test: StreetPlot.plot_map; render all available map layers."""
        streets = gpd.GeoDataFrame({
            "maxspeed_class": ["50", "30"], "conditional_speed": [None, "30"],
            "feature_type": ["T30_Potenzial_Zebrastreifen", "street"],
        }, geometry=[LineString([(0, 0), (1, 0)]),
                     LineString([(1, 0), (2, 0)])], crs="EPSG:25832")
        zebra = gpd.GeoDataFrame(geometry=[Point(1, 0)], crs=streets.crs)
        school = gpd.GeoDataFrame(geometry=[Point(1.5, 0)], crs=streets.crs)
        StreetPlot.plot_map(streets, zebra, {"educational_buildings": school},
                            debug_endpoints=True)
        ax = plt.gca()
        self.assertEqual(ax.get_title(), "Straßenabschnitte nach Tempolimit")
        self.assertIn("Zebrastreifen", [text.get_text() for text in ax.get_legend().get_texts()])
        self.assertEqual(streets.maxspeed_class.tolist(), ["50", "30"])
        plt.close(ax.figure)
