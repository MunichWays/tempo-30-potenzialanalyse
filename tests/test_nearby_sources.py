"""Associate fast roads with nearby sources, using a caller-selected search radius."""

import unittest

from tests.fixtures.fixture_data import frame
from PotentialCalculation.ProximityPotential import ProximityPotential
from PotentialCalculation.ZebraPotential import ZebraPotential


DETECTORS = {
    "facilities": ProximityPotential.find_tempo50_segments_near_features,
    "crossings": ZebraPotential.find_tempo50_segments_near_zebra,
}


class NearbySourceTests(unittest.TestCase):
    def test_fast_roads_and_their_contributing_sources_are_selected(self):
        """Unit under test: ProximityPotential.find_tempo50_segments_near_features and
        ZebraPotential.find_tempo50_segments_near_zebra.

        Nearby sources select 50/60 roads; slow and unknown classes remain unchanged.

        Fixture: proximity_speeds; roads 4/5 have classes 50/60 and sources 104/105.
        """
        streets = frame("proximity_speeds")
        sources = frame("proximity_speeds", "features")

        for kind, detect in DETECTORS.items():
            with self.subTest(source_kind=kind):
                result = detect(streets, sources, search_distance_m=8)
                self.assertCountEqual(result.street_ids, [4, 5])
                self.assertCountEqual(result.opt_source_ids, [104, 105])

    def test_distance_is_measured_to_the_feature_edge(self):
        """Unit under test: ProximityPotential.find_tempo50_segments_near_features and
        ZebraPotential.find_tempo50_segments_near_zebra.

        A large facility can adjoin a road even when its centre is far away.

        Fixture: proximity_polygons; polygon edges 1/2 reach roads 10/20,
        while polygon 3 is distant. Crossing geometries use the same operation.
        """
        streets = frame("proximity_polygons")
        sources = frame("proximity_polygons", "features")

        for kind, detect in DETECTORS.items():
            with self.subTest(source_kind=kind):
                result = detect(streets, sources, search_distance_m=18)
                self.assertCountEqual(result.street_ids, [10, 20])
                self.assertCountEqual(result.opt_source_ids, [1, 2])

    def test_each_osm_identity_is_reported_once(self):
        """Unit under test: ProximityPotential.find_tempo50_segments_near_features and
        ZebraPotential.find_tempo50_segments_near_zebra.

        Several spatial matches must not duplicate road or source identities.

        Fixture: proximity_duplicates; some rows share IDs and use arbitrary indices.
        """
        streets = frame("proximity_duplicates")
        sources = frame("proximity_duplicates", "features")

        for kind, detect in DETECTORS.items():
            with self.subTest(source_kind=kind):
                result = detect(streets, sources, search_distance_m=8)
                self.assertCountEqual(result.street_ids, [900, 700])
                self.assertCountEqual(result.opt_source_ids, [100, 200])
