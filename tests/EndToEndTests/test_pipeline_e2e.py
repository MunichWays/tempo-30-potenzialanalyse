"""
End-to-end tests for the full potential calculation pipeline.

Each test builds a small OSM world, serves it through a mocked Overpass API and
runs ``run_potential_calculation`` from retrieval to GeoJSON export. The
assertions are made on the exported GeoJSON files only.

The OSM cache is disabled (never read, never written) and the pipeline runs
inside a temporary working directory, so neither local cache files influence
the tests nor do the tests leave files behind.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shapely.geometry import Point, shape

from DataRetrieval.OSMDataCache import OSMDataCache
from PotentialCalculationPipeline import BUILDING_CONFIGS, run_potential_calculation

from .overpass_mock import OverpassApiMock, OverpassWorld, offset


REGION_NAME = "Olching"
REGION_BBOX_FILTER = "(48.14,11.25,48.28,11.41)"

LABEL_ZEBRA = "Potenzial durch Zebrastreifen"
LABEL_GAP = "Potenzial durch Lückenschluss"
LABEL_MULTI = "Potenzial durch mehrere Faktoren"
BUILDING_LABELS = {
    "educational_buildings": "Potenzial durch Bildungseinrichtung",
    "hospitals": "Potenzial durch Krankenhaus",
    "elderly_homes": "Potenzial durch Seniorenwohnheim",
    "playgrounds": "Potenzial durch Spielplatz",
    "disability_facilities": "Potenzial durch Behinderteneinrichtung",
}

# Names that pass the name filter regex of each building type
BUILDING_NAMES = {
    "educational_buildings": "Grundschule am Test",
    "hospitals": "Klinikum Test",
    "elderly_homes": "Seniorenresidenz Test",
    "playgrounds": None,  # playgrounds are not filtered by name
    "disability_facilities": "Lebenshilfe Werkstatt Test",
}

STREET_LENGTH_M = 150
FEATURE_DISTANCE_M = 10  # within the 20 m proximity search distance

# Coordinate tolerance (degrees, ~1 cm) when locating exported features
COORD_TOLERANCE = 1e-7


class Corridor:
    """A straight tempo-50 street of 150 m running east from ``origin``."""

    def __init__(self, world: OverpassWorld, origin, with_tempo30_neighbours=False, **street_kwargs):
        self.world = world
        self.start = origin
        self.end = offset(*origin, east_m=STREET_LENGTH_M)
        self.street_id = world.add_street([self.start, self.end], **street_kwargs)
        self.neighbour_ids = []

        if with_tempo30_neighbours:
            # T30 - T50 - T30 in a straight line => gap potential for the T50 part
            self.neighbour_ids = [
                world.add_street(
                    [offset(*self.start, east_m=-STREET_LENGTH_M), self.start],
                    maxspeed="30",
                    name="Tempo-30-Straße West",
                ),
                world.add_street(
                    [self.end, offset(*self.end, east_m=STREET_LENGTH_M)],
                    maxspeed="30",
                    name="Tempo-30-Straße Ost",
                ),
            ]

    def point_on_street(self, east_m=STREET_LENGTH_M / 2):
        return offset(*self.start, east_m=east_m)

    def point_beside_street(self, east_m=STREET_LENGTH_M / 2, north_m=FEATURE_DISTANCE_M):
        return offset(*self.start, east_m=east_m, north_m=north_m)


class PipelineEndToEndTestCase(unittest.TestCase):
    # Scenario corridors are 1 km apart from each other and from the background
    ORIGINS = [(11.30, 48.16 + i * 0.01) for i in range(6)]
    BACKGROUND_ORIGIN = (11.36, 48.26)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp_dir = Path(tmp.name)

        self.world = OverpassWorld(BUILDING_CONFIGS)
        self.background = self._add_background()

    def _add_background(self):
        """
        A tempo-50 street plus one feature of every source type, all placed
        far away from each other. They must never become potential.
        This also guarantees every layer exists in the GeoJSON export.
        """
        street = Corridor(self.world, self.BACKGROUND_ORIGIN, name="Hintergrundstraße")
        positions = {"zebra": offset(*self.BACKGROUND_ORIGIN, 0, 500)}
        self.world.add_zebra(positions["zebra"])

        for i, datatype in enumerate(BUILDING_CONFIGS):
            positions[datatype] = offset(*self.BACKGROUND_ORIGIN, 200 * (i + 1), 500)
            self.world.add_building(datatype, positions[datatype], name=BUILDING_NAMES[datatype])

        return {"street": street, "positions": positions}

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------
    def run_pipeline(self):
        overpass = OverpassApiMock(self.world, expected_region_filter=REGION_BBOX_FILTER)
        export_root = self.tmp_dir / "GEOJSON_EXPORT"

        cwd = os.getcwd()
        os.chdir(self.tmp_dir)  # any accidental cache dir ends up in the temp dir
        self.addCleanup(os.chdir, cwd)

        with patch("requests.post", side_effect=overpass) as post, \
             patch.object(OSMDataCache, "load_file_from_cache", return_value=None) as load_cache, \
             patch.object(OSMDataCache, "store_data") as store_cache, \
             contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            run_potential_calculation(
                REGION_NAME,
                export_root=export_root,
                render_plots=False,
                show_plot=False,
            )

        # Every data set must come from the (mocked) API, never from the cache
        self.assertCountEqual(
            overpass.requested,
            [OverpassWorld.STREETS, OverpassWorld.ZEBRAS, *BUILDING_CONFIGS.keys()],
        )
        self.assertEqual(post.call_count, 2 + len(BUILDING_CONFIGS))
        self.assertEqual(load_cache.call_count, 2 + len(BUILDING_CONFIGS))
        # Fetched data is handed to the (patched) cache but never written to disk
        self.assertEqual(store_cache.call_count, 2 + len(BUILDING_CONFIGS))
        self.assertFalse(any((self.tmp_dir / "overpass_cache").glob("*")))

        export_dir = export_root / REGION_NAME
        self.geojson = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in export_dir.glob("*.geojson")
        }
        self.assertCountEqual(
            self.geojson.keys(),
            ["potential_streets", "streets_and_limit", "zebra", *BUILDING_CONFIGS.keys()],
        )

    # ------------------------------------------------------------------
    # GeoJSON helpers
    # ------------------------------------------------------------------
    def potential_types(self) -> dict[int, str]:
        return {
            f["properties"]["osm_id"]: f["properties"]["feature_type"]
            for f in self.geojson["potential_streets"]["features"]
        }

    def feature_at(self, layer: str, coord) -> dict:
        point = Point(coord)
        matches = [
            f for f in self.geojson[layer]["features"]
            if shape(f["geometry"]).distance(point) < COORD_TOLERANCE
        ]
        self.assertEqual(len(matches), 1, f"Expected exactly one {layer} feature at {coord}")
        return matches[0]

    def assert_source_candidate(self, layer: str, coord, expected=True):
        feature = self.feature_at(layer, coord)
        self.assertIs(
            feature["properties"]["potential_candidate"],
            expected,
            f"{layer} feature at {coord} should have potential_candidate={expected}",
        )

    def assert_potential_streets(self, expected: dict[int, str]):
        self.assertEqual(self.potential_types(), expected)

    def assert_background_untouched(self):
        self.assertNotIn(self.background["street"].street_id, self.potential_types())
        for layer, coord in self.background["positions"].items():
            self.assert_source_candidate(layer, coord, expected=False)

    # ------------------------------------------------------------------
    # Scenario helpers
    # ------------------------------------------------------------------
    def add_source(self, corridor: Corridor, source: str, east_m=STREET_LENGTH_M / 2):
        """Place a source of the given potential type at the corridor and return its position."""
        if source == "zebra":
            coord = corridor.point_on_street(east_m)
            self.world.add_zebra(coord)
        elif source == "hospitals":
            # Hospitals are modelled as building polygons (closed ways)
            coord = corridor.point_beside_street(east_m, north_m=FEATURE_DISTANCE_M + 5)
            self.world.add_building(source, coord, name=BUILDING_NAMES[source], size_m=10)
        else:
            coord = corridor.point_beside_street(east_m)
            self.world.add_building(source, coord, name=BUILDING_NAMES[source])
        return coord


class SinglePotentialTypeTests(PipelineEndToEndTestCase):
    """One street, one source: the street gets exactly that potential type."""

    def _assert_single_source_potential(self, source: str, expected_label: str):
        corridor = Corridor(self.world, self.ORIGINS[0])
        coord = self.add_source(corridor, source)

        self.run_pipeline()

        self.assert_potential_streets({corridor.street_id: expected_label})
        self.assert_source_candidate(source, coord)
        self.assert_background_untouched()

        streets = {
            f["properties"]["osm_id"]: f["properties"]
            for f in self.geojson["streets_and_limit"]["features"]
        }
        self.assertEqual(streets[corridor.street_id]["maxspeed_class"], "T50+")

    def test_zebra_crossing_potential(self):
        self._assert_single_source_potential("zebra", LABEL_ZEBRA)

    def test_educational_building_potential(self):
        self._assert_single_source_potential(
            "educational_buildings", BUILDING_LABELS["educational_buildings"]
        )

    def test_hospital_potential(self):
        self._assert_single_source_potential("hospitals", BUILDING_LABELS["hospitals"])

    def test_elderly_home_potential(self):
        self._assert_single_source_potential("elderly_homes", BUILDING_LABELS["elderly_homes"])

    def test_playground_potential(self):
        self._assert_single_source_potential("playgrounds", BUILDING_LABELS["playgrounds"])

    def test_disability_facility_potential(self):
        self._assert_single_source_potential(
            "disability_facilities", BUILDING_LABELS["disability_facilities"]
        )

    def test_gap_potential(self):
        corridor = Corridor(self.world, self.ORIGINS[0], with_tempo30_neighbours=True)

        self.run_pipeline()

        # Only the tempo-50 gap is marked, not the tempo-30 neighbours
        self.assert_potential_streets({corridor.street_id: LABEL_GAP})
        self.assert_background_untouched()

    def test_same_source_type_twice_is_not_multifactor(self):
        corridor = Corridor(self.world, self.ORIGINS[0])
        first = self.add_source(corridor, "educational_buildings", east_m=30)
        second = self.add_source(corridor, "educational_buildings", east_m=120)

        self.run_pipeline()

        self.assert_potential_streets(
            {corridor.street_id: BUILDING_LABELS["educational_buildings"]}
        )
        self.assert_source_candidate("educational_buildings", first)
        self.assert_source_candidate("educational_buildings", second)

    def test_conditional_tempo30_street_has_no_proximity_potential(self):
        conditional = Corridor(
            self.world,
            self.ORIGINS[0],
            name="Schulweg",
            extra_tags={"maxspeed:conditional": "30 @ (Mo-Fr 07:00-17:00)"},
        )
        school = self.add_source(conditional, "educational_buildings")
        reference = Corridor(self.world, self.ORIGINS[1])
        self.add_source(reference, "zebra")

        self.run_pipeline()

        self.assert_potential_streets({reference.street_id: LABEL_ZEBRA})
        self.assert_source_candidate("educational_buildings", school, expected=False)


class MultifactorPotentialTests(PipelineEndToEndTestCase):
    """Several different potential types on one street => multifactor."""

    def _assert_multifactor(self, sources: list[str], with_gap: bool = False):
        corridor = Corridor(self.world, self.ORIGINS[0], with_tempo30_neighbours=with_gap)
        step = STREET_LENGTH_M / (len(sources) + 1)
        coords = {
            source: self.add_source(corridor, source, east_m=step * (i + 1))
            for i, source in enumerate(sources)
        }

        self.run_pipeline()

        self.assert_potential_streets({corridor.street_id: LABEL_MULTI})
        for source, coord in coords.items():
            self.assert_source_candidate(source, coord)
        self.assert_background_untouched()

    def test_zebra_and_school(self):
        self._assert_multifactor(["zebra", "educational_buildings"])

    def test_gap_and_hospital(self):
        self._assert_multifactor(["hospitals"], with_gap=True)

    def test_gap_and_zebra(self):
        self._assert_multifactor(["zebra"], with_gap=True)

    def test_elderly_home_playground_and_disability_facility(self):
        self._assert_multifactor(["elderly_homes", "playgrounds", "disability_facilities"])

    def test_all_potential_types_combined(self):
        self._assert_multifactor(["zebra", *BUILDING_CONFIGS.keys()], with_gap=True)

    def test_different_types_on_separate_streets_are_not_multifactor(self):
        school_street = Corridor(self.world, self.ORIGINS[0])
        school = self.add_source(school_street, "educational_buildings")
        zebra_street = Corridor(self.world, self.ORIGINS[1])
        zebra = self.add_source(zebra_street, "zebra")
        gap_street = Corridor(self.world, self.ORIGINS[2], with_tempo30_neighbours=True)

        self.run_pipeline()

        self.assert_potential_streets({
            school_street.street_id: BUILDING_LABELS["educational_buildings"],
            zebra_street.street_id: LABEL_ZEBRA,
            gap_street.street_id: LABEL_GAP,
        })
        self.assert_source_candidate("educational_buildings", school)
        self.assert_source_candidate("zebra", zebra)
        self.assert_background_untouched()

    def test_multifactor_and_single_factor_streets_side_by_side(self):
        multi_street = Corridor(self.world, self.ORIGINS[0])
        self.add_source(multi_street, "zebra", east_m=40)
        self.add_source(multi_street, "playgrounds", east_m=110)
        single_street = Corridor(self.world, self.ORIGINS[1])
        self.add_source(single_street, "playgrounds")

        self.run_pipeline()

        self.assert_potential_streets({
            multi_street.street_id: LABEL_MULTI,
            single_street.street_id: BUILDING_LABELS["playgrounds"],
        })


if __name__ == "__main__":
    unittest.main()
