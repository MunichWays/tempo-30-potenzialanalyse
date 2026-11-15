"""Principal gap assumptions, from enclosure to logical street continuation.

A gap needs slow anchors at both ends of a connected fast corridor. Measure the
whole fast corridor, excluding its slow anchors; gaps longer than 500 m do not
qualify. At junctions, the continuation rules determine the logical Straßenführung.
All examples are in fixtures/scenarios.geojson.
"""

from contextlib import redirect_stderr
import io
import unittest

from tests.fixtures.fixture_data import frame
from PotentialCalculation.GapPotential import Tempo50GapPotential


class GapPotentialTests(unittest.TestCase):
    def detect(self, scenario):
        with redirect_stderr(io.StringIO()):
            return Tempo50GapPotential.find_all_tempo_50_gaps(frame(scenario)).street_ids

    def test_01_single_enclosed_road_is_detected(self):
        """Unit under test: Tempo50GapPotential.find_all_tempo_50_gaps.

        A fast road connected to slow roads at both ends is a gap."""
        self.assertEqual(self.detect("gap_single_enclosed"), [2])

    def test_02_multiple_enclosed_roads_are_detected(self):
        """Unit under test: Tempo50GapPotential.find_all_tempo_50_gaps.

        Connected fast roads form one gap; slow anchor lengths do not count."""
        for scenario in ("gap_multiple_enclosed", "gap_at_max_length"):
            with self.subTest(scenario=scenario):
                self.assertCountEqual(self.detect(scenario), [2, 3])

    def test_03_one_open_side_is_not_a_gap(self):
        """Unit under test: Tempo50GapPotential.find_all_tempo_50_gaps.

        A slow anchor at only one end is insufficient, whichever end is open."""
        for scenario in ("gap_open_left", "gap_open_right"):
            with self.subTest(scenario=scenario):
                self.assertEqual(self.detect(scenario), [])

    def test_04_a_disconnected_anchor_does_not_close_a_gap(self):
        """Unit under test: Tempo50GapPotential.find_all_tempo_50_gaps.

        A separate parallel slow road is not an anchor for the fast road’s open end."""
        self.assertEqual(self.detect("gap_disconnected"), [])

    def test_05_gaps_longer_than_500_metres_are_not_detected(self):
        """Unit under test: Tempo50GapPotential.find_all_tempo_50_gaps.

        Reject a gap over 500 m, whether it consists of one road or several."""
        for scenario in ("gap_single_too_long", "gap_too_long"):
            with self.subTest(scenario=scenario):
                self.assertEqual(self.detect(scenario), [])

    def test_06_follow_the_straight_continuation_at_a_mixed_junction(self):
        """Unit under test: Tempo50GapPotential.find_all_tempo_50_gaps.

        Follow the slow straight continuation rather than the fast side branch."""
        self.assertEqual(self.detect("gap_straight_continuation"), [2])

    def test_07_an_all_slow_junction_can_anchor_a_bend(self):
        """Unit under test: Tempo50GapPotential.find_all_tempo_50_gaps.

        If every continuation is slow, the corridor may end at a bend."""
        self.assertEqual(self.detect("gap_all_slow_junction"), [2])

    def test_08_a_slow_side_turn_does_not_replace_the_straight_continuation(self):
        """Unit under test: Tempo50GapPotential.find_all_tempo_50_gaps.

        An open straight branch cannot be closed by taking a sharp slow side turn."""
        self.assertEqual(self.detect("gap_sharp_turn"), [])

    def test_09_a_fast_loop_without_slow_anchors_is_not_a_gap(self):
        """Unit under test: Tempo50GapPotential.find_all_tempo_50_gaps.

        Returning to the start does not establish enclosure by slow roads."""
        self.assertEqual(self.detect("gap_loop"), [])
