"""
End-to-end tests for the full potential calculation pipeline.

Each test describes a small scenario ("a tempo-50 street with a school next to
it"), serves it through a mocked Overpass API and runs
``run_potential_calculation`` from retrieval to GeoJSON export. All assertions
are made on the exported GeoJSON files.

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
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from shapely.geometry import Point, shape

from DataRetrieval.OSMDataCache import OSMDataCache
from PotentialCalculationPipeline import BUILDING_CONFIGS, run_potential_calculation

from tests.unfallatlas_mock import UnfallatlasServerMock

from .overpass_mock import OverpassApiMock, OverpassWorld, offset


# Expected "feature_type" values in potential_streets.geojson
ZEBRA_POTENTIAL = "Potenzial durch Zebrastreifen"
GAP_POTENTIAL = "Potenzial durch Lückenschluss"
SCHOOL_POTENTIAL = "Potenzial durch Bildungseinrichtung"
HOSPITAL_POTENTIAL = "Potenzial durch Krankenhaus"
ELDERLY_HOME_POTENTIAL = "Potenzial durch Seniorenwohnheim"
PLAYGROUND_POTENTIAL = "Potenzial durch Spielplatz"
DISABILITY_FACILITY_POTENTIAL = "Potenzial durch Behinderteneinrichtung"
MULTIFACTOR_POTENTIAL = "Potenzial durch mehrere Faktoren"


# ----------------------------------------------------------------------
# Scenario building blocks
# ----------------------------------------------------------------------
REGION_NAME = "Olching"
REGION_BBOX_FILTER = "(48.14,11.25,48.28,11.41)"

STREET_LENGTH_M = 150
DISTANCE_TO_STREET_M = 10   # within the 20 m proximity search distance
STREET_SPACING_DEG = 0.01   # scenario streets are ~1 km apart
FIRST_STREET_ORIGIN = (11.30, 48.16)
BACKGROUND_ORIGIN = (11.36, 48.26)

# Tolerance (degrees, ~1 cm) when locating exported features by position
COORD_TOLERANCE = 1e-7


@dataclass(frozen=True)
class Source:
    """A feature that can cause potential (zebra crossing, school, ...)."""
    layer: str              # name of the GeoJSON layer the source is exported to
    position: tuple[float, float]


class Street:
    """A straight 150 m street running east from ``origin``."""

    def __init__(self, world: OverpassWorld, origin, **street_tags):
        self.start = origin
        self.end = offset(*origin, east_m=STREET_LENGTH_M)
        self.osm_id = world.add_street([self.start, self.end], **street_tags)
        self._sources_placed = 0

    def next_free_spot(self) -> float:
        """Distance from the street start for the next source, so sources do not overlap."""
        self._sources_placed += 1
        return 20.0 * self._sources_placed


class PipelineEndToEndTestCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp_dir = Path(tmp.name)

        self.world = OverpassWorld(BUILDING_CONFIGS)
        self.unfallatlas = UnfallatlasServerMock(years=[2023, 2024, 2025])
        self._street_count = 0
        self._add_unrelated_background()

    # ------------------------------------------------------------------
    # Given: streets
    # ------------------------------------------------------------------
    def a_tempo50_street(self, name="Teststraße", **tags) -> Street:
        lon, lat = FIRST_STREET_ORIGIN
        origin = (lon, round(lat + self._street_count * STREET_SPACING_DEG, 7))
        self._street_count += 1
        return Street(self.world, origin, maxspeed="50", name=name, **tags)

    def a_tempo50_street_between_tempo30_streets(self) -> tuple[Street, Street, Street]:
        """Tempo 30 - Tempo 50 - Tempo 30 in a straight line: a gap to close."""
        street = self.a_tempo50_street(name="Lückenstraße")
        west = self.world.add_street(
            [offset(*street.start, east_m=-STREET_LENGTH_M), street.start],
            maxspeed="30", name="Tempo-30-Straße West",
        )
        east = self.world.add_street(
            [street.end, offset(*street.end, east_m=STREET_LENGTH_M)],
            maxspeed="30", name="Tempo-30-Straße Ost",
        )
        return street, west, east

    def a_street_with_tempo30_during_school_hours(self) -> Street:
        return self.a_tempo50_street(
            name="Schulweg",
            extra_tags={"maxspeed:conditional": "30 @ (Mo-Fr 07:00-17:00)"},
        )

    # ------------------------------------------------------------------
    # Given: potential sources
    # ------------------------------------------------------------------
    def a_zebra_crossing_on(self, street: Street) -> Source:
        position = offset(*street.start, east_m=street.next_free_spot())
        self.world.add_zebra(position)
        return Source("zebra", position)

    def a_school_next_to(self, street: Street) -> Source:
        return self._building_next_to(street, "educational_buildings", "Grundschule am Test")

    def a_hospital_next_to(self, street: Street) -> Source:
        # Hospitals are modelled as building outlines (closed ways), not points
        return self._building_next_to(street, "hospitals", "Klinikum Test", size_m=10)

    def an_elderly_home_next_to(self, street: Street) -> Source:
        return self._building_next_to(street, "elderly_homes", "Seniorenresidenz Test")

    def a_playground_next_to(self, street: Street) -> Source:
        return self._building_next_to(street, "playgrounds", name=None)

    def a_disability_facility_next_to(self, street: Street) -> Source:
        return self._building_next_to(street, "disability_facilities", "Lebenshilfe Werkstatt Test")

    def _building_next_to(self, street: Street, layer: str, name, size_m=None) -> Source:
        north_m = DISTANCE_TO_STREET_M + (size_m / 2 if size_m else 0)
        position = offset(*street.start, east_m=street.next_free_spot(), north_m=north_m)
        self.world.add_building(layer, position, name=name, size_m=size_m)
        return Source(layer, position)

    def _add_unrelated_background(self):
        """
        A tempo-50 street plus one source of every type, all far away from
        each other and from the scenario streets. None of them may ever be
        marked as potential. This also makes sure every GeoJSON layer exists.
        """
        Street(self.world, BACKGROUND_ORIGIN, maxspeed="50", name="Hintergrundstraße")

        far_away = [offset(*BACKGROUND_ORIGIN, east_m=200 * i, north_m=500) for i in range(6)]
        self.world.add_zebra(far_away[0])
        self.background_sources = [Source("zebra", far_away[0])]

        names = {
            "educational_buildings": "Grundschule am Test",
            "hospitals": "Klinikum Test",
            "elderly_homes": "Seniorenresidenz Test",
            "playgrounds": None,
            "disability_facilities": "Lebenshilfe Werkstatt Test",
        }
        for position, layer in zip(far_away[1:], BUILDING_CONFIGS):
            self.world.add_building(layer, position, name=names[layer])
            self.background_sources.append(Source(layer, position))

    # ------------------------------------------------------------------
    # When
    # ------------------------------------------------------------------
    def run_pipeline(self):
        overpass = OverpassApiMock(self.world, expected_region_filter=REGION_BBOX_FILTER)
        export_root = self.tmp_dir / "GEOJSON_EXPORT"

        cwd = os.getcwd()
        os.chdir(self.tmp_dir)  # any accidental cache dir ends up in the temp dir
        self.addCleanup(os.chdir, cwd)

        with patch("requests.post", side_effect=overpass) as post,              patch("requests.get", side_effect=self.unfallatlas), \
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
        number_of_datasets = 2 + len(BUILDING_CONFIGS)
        self.assertCountEqual(
            overpass.requested,
            [OverpassWorld.STREETS, OverpassWorld.ZEBRAS, *BUILDING_CONFIGS.keys()],
        )
        self.assertEqual(post.call_count, number_of_datasets)
        self.assertEqual(load_cache.call_count, number_of_datasets)
        # Fetched data is handed to the (patched) cache but never written to disk
        self.assertEqual(store_cache.call_count, number_of_datasets)
        self.assertFalse(any((self.tmp_dir / "overpass_cache").glob("*")))

        self.geojson = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in (export_root / REGION_NAME).glob("*.geojson")
        }
        self.crash_layers = {
            name: layer for name, layer in self.geojson.items() if name.startswith("crashes_")
        }
        # Every selected year (default: the latest three) gets its own layer, even without crashes
        self.assertCountEqual(
            self.crash_layers.keys(),
            [f"crashes_{year}" for year in sorted(self.unfallatlas.crashes)[-3:]],
        )
        self.assertCountEqual(
            self.geojson.keys() - self.crash_layers.keys(),
            ["potential_streets", "streets_and_limit", "zebra", *BUILDING_CONFIGS.keys()],
        )
        # Unfallatlas zips are cached in the working directory, never next to the sources
        self.assertTrue(any((self.tmp_dir / "unfallatlas_cache").glob("*.zip")))

        # The unrelated background must never be affected by any scenario
        self.assert_not_marked_as_source(*self.background_sources)

    # ------------------------------------------------------------------
    # Then
    # ------------------------------------------------------------------
    def assert_potential_streets_are(self, expected: dict[Street, str]):
        """Exactly these streets (and no others) are exported with these potential types."""
        exported = {
            f["properties"]["osm_id"]: f["properties"]["feature_type"]
            for f in self.geojson["potential_streets"]["features"]
        }
        self.assertEqual(
            exported,
            {street.osm_id: potential for street, potential in expected.items()},
        )

    def assert_marked_as_source(self, *sources: Source):
        for source in sources:
            self.assertIs(
                self._exported(source)["properties"]["potential_candidate"], True,
                f"{source} should be marked as potential source",
            )

    def assert_not_marked_as_source(self, *sources: Source):
        for source in sources:
            self.assertIs(
                self._exported(source)["properties"]["potential_candidate"], False,
                f"{source} should not be marked as potential source",
            )

    def assert_speed_class(self, street_id: int, expected: str):
        exported = {
            f["properties"]["osm_id"]: f["properties"]["maxspeed_class"]
            for f in self.geojson["streets_and_limit"]["features"]
        }
        self.assertEqual(exported[street_id], expected)

    def _exported(self, source: Source) -> dict:
        point = Point(source.position)
        matches = [
            f for f in self.geojson[source.layer]["features"]
            if shape(f["geometry"]).distance(point) < COORD_TOLERANCE
        ]
        self.assertEqual(len(matches), 1, f"Expected exactly one exported feature for {source}")
        return matches[0]


class SinglePotentialTypeTests(PipelineEndToEndTestCase):
    """One cause of potential on a street: the street gets exactly that potential type."""

    def test_zebra_crossing_gives_zebra_potential(self):
        street = self.a_tempo50_street()
        zebra = self.a_zebra_crossing_on(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: ZEBRA_POTENTIAL})
        self.assert_marked_as_source(zebra)

    def test_school_gives_school_potential(self):
        street = self.a_tempo50_street()
        school = self.a_school_next_to(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: SCHOOL_POTENTIAL})
        self.assert_marked_as_source(school)

    def test_hospital_gives_hospital_potential(self):
        street = self.a_tempo50_street()
        hospital = self.a_hospital_next_to(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: HOSPITAL_POTENTIAL})
        self.assert_marked_as_source(hospital)

    def test_elderly_home_gives_elderly_home_potential(self):
        street = self.a_tempo50_street()
        elderly_home = self.an_elderly_home_next_to(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: ELDERLY_HOME_POTENTIAL})
        self.assert_marked_as_source(elderly_home)

    def test_playground_gives_playground_potential(self):
        street = self.a_tempo50_street()
        playground = self.a_playground_next_to(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: PLAYGROUND_POTENTIAL})
        self.assert_marked_as_source(playground)

    def test_disability_facility_gives_disability_facility_potential(self):
        street = self.a_tempo50_street()
        facility = self.a_disability_facility_next_to(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: DISABILITY_FACILITY_POTENTIAL})
        self.assert_marked_as_source(facility)

    def test_tempo50_between_tempo30_streets_gives_gap_potential(self):
        street, tempo30_west, tempo30_east = self.a_tempo50_street_between_tempo30_streets()

        self.run_pipeline()

        self.assert_potential_streets_are({street: GAP_POTENTIAL})
        self.assert_speed_class(street.osm_id, "T50+")
        self.assert_speed_class(tempo30_west, "T30-")
        self.assert_speed_class(tempo30_east, "T30-")

    def test_two_schools_on_one_street_are_not_multifactor(self):
        street = self.a_tempo50_street()
        first_school = self.a_school_next_to(street)
        second_school = self.a_school_next_to(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: SCHOOL_POTENTIAL})
        self.assert_marked_as_source(first_school, second_school)

    def test_school_next_to_street_with_tempo30_during_school_hours_gives_no_potential(self):
        school_street = self.a_street_with_tempo30_during_school_hours()
        school = self.a_school_next_to(school_street)

        self.run_pipeline()

        self.assert_potential_streets_are({})
        self.assert_not_marked_as_source(school)


class MultifactorPotentialTests(PipelineEndToEndTestCase):
    """Different causes of potential on one street: the street gets multifactor potential."""

    def test_zebra_crossing_and_school(self):
        street = self.a_tempo50_street()
        zebra = self.a_zebra_crossing_on(street)
        school = self.a_school_next_to(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: MULTIFACTOR_POTENTIAL})
        self.assert_marked_as_source(zebra, school)

    def test_gap_and_hospital(self):
        street, _, _ = self.a_tempo50_street_between_tempo30_streets()
        hospital = self.a_hospital_next_to(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: MULTIFACTOR_POTENTIAL})
        self.assert_marked_as_source(hospital)

    def test_gap_and_zebra_crossing(self):
        street, _, _ = self.a_tempo50_street_between_tempo30_streets()
        zebra = self.a_zebra_crossing_on(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: MULTIFACTOR_POTENTIAL})
        self.assert_marked_as_source(zebra)

    def test_elderly_home_playground_and_disability_facility(self):
        street = self.a_tempo50_street()
        elderly_home = self.an_elderly_home_next_to(street)
        playground = self.a_playground_next_to(street)
        facility = self.a_disability_facility_next_to(street)

        self.run_pipeline()

        self.assert_potential_streets_are({street: MULTIFACTOR_POTENTIAL})
        self.assert_marked_as_source(elderly_home, playground, facility)

    def test_all_potential_types_on_one_street(self):
        street, _, _ = self.a_tempo50_street_between_tempo30_streets()
        sources = [
            self.a_zebra_crossing_on(street),
            self.a_school_next_to(street),
            self.a_hospital_next_to(street),
            self.an_elderly_home_next_to(street),
            self.a_playground_next_to(street),
            self.a_disability_facility_next_to(street),
        ]

        self.run_pipeline()

        self.assert_potential_streets_are({street: MULTIFACTOR_POTENTIAL})
        self.assert_marked_as_source(*sources)

    def test_different_types_on_separate_streets_are_not_multifactor(self):
        school_street = self.a_tempo50_street()
        school = self.a_school_next_to(school_street)
        zebra_street = self.a_tempo50_street()
        zebra = self.a_zebra_crossing_on(zebra_street)
        gap_street, _, _ = self.a_tempo50_street_between_tempo30_streets()

        self.run_pipeline()

        self.assert_potential_streets_are({
            school_street: SCHOOL_POTENTIAL,
            zebra_street: ZEBRA_POTENTIAL,
            gap_street: GAP_POTENTIAL,
        })
        self.assert_marked_as_source(school, zebra)

    def test_multifactor_street_next_to_single_factor_street(self):
        multifactor_street = self.a_tempo50_street()
        zebra = self.a_zebra_crossing_on(multifactor_street)
        playground_1 = self.a_playground_next_to(multifactor_street)
        single_factor_street = self.a_tempo50_street()
        playground_2 = self.a_playground_next_to(single_factor_street)

        self.run_pipeline()

        self.assert_potential_streets_are({
            multifactor_street: MULTIFACTOR_POTENTIAL,
            single_factor_street: PLAYGROUND_POTENTIAL,
        })
        self.assert_marked_as_source(zebra, playground_1, playground_2)


if __name__ == "__main__":
    unittest.main()


class CrashStatisticTests(PipelineEndToEndTestCase):
    """Unfallatlas crashes are clipped to the region and exported as their own layer."""

    def test_crashes_inside_region_are_exported_with_class(self):
        inside = offset(*FIRST_STREET_ORIGIN, east_m=50)
        outside = (11.50, 48.20)   # east of the Olching bbox
        self.unfallatlas.add_crash(*inside, 2025, involved=("Rad", "PKW"), category=2)
        self.unfallatlas.add_crash(*inside, 2023, involved=("Fuss",))
        self.unfallatlas.add_crash(*outside, 2025)

        self.run_pipeline()

        self.assertEqual(self.crash_layers["crashes_2024"]["features"], [])
        features = [f for layer in self.crash_layers.values() for f in layer["features"]]
        self.assertEqual(len(features), 2)
        for feature in features:
            lon, lat = feature["geometry"]["coordinates"]
            self.assertAlmostEqual(lon, inside[0], places=6)
            self.assertAlmostEqual(lat, inside[1], places=6)

        by_year = {f["properties"]["UJAHR"]: f["properties"] for f in features}
        self.assertEqual(by_year["2025"]["Unfallklasse"], "Rad-PKW")
        self.assertEqual(by_year["2025"]["Unfallkategorie"], "Unfall mit Schwerverletzten")
        self.assertEqual(by_year["2023"]["Unfallklasse"], "Fuss")
        self.assertNotIn("LINREFX", by_year["2025"])
        for layer in self.crash_layers.values():
            self.assertIn("Unfallatlas", layer["attribution"])

    def test_crash_years_outside_selection_are_ignored(self):
        self.unfallatlas = UnfallatlasServerMock(years=[2021, 2022, 2023, 2024, 2025])
        spot = offset(*FIRST_STREET_ORIGIN, east_m=50)
        for year in [2021, 2022, 2023, 2024, 2025]:
            self.unfallatlas.add_crash(*spot, year)

        self.run_pipeline()

        self.assertCountEqual(
            self.crash_layers.keys(), ["crashes_2023", "crashes_2024", "crashes_2025"]
        )
        for name, layer in self.crash_layers.items():
            self.assertEqual(
                [f["properties"]["UJAHR"] for f in layer["features"]], [name.removeprefix("crashes_")]
            )
