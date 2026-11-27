import unittest

import pandas as pd

from CrashStatistic.CrashClassification import CrashClassification


def crash(rad=0, pkw=0, fuss=0, krad=0, gkfz=0, sonstige=0, kategorie="3"):
    return {
        "IstRad": rad, "IstPKW": pkw, "IstFuss": fuss, "IstKrad": krad,
        "IstGkfz": gkfz, "IstSonstige": sonstige, "UKATEGORIE": kategorie,
    }


def classify(*crashes):
    return CrashClassification.classify(pd.DataFrame(list(crashes)))


class CrashClassificationTests(unittest.TestCase):

    def test_single_participant(self):
        result = classify(crash(rad=1), crash(pkw="1"))
        self.assertEqual(result["Unfallklasse"].tolist(), ["Rad", "PKW"])

    def test_two_participants_follow_fixed_order(self):
        result = classify(crash(pkw=1, rad=1), crash(fuss=1, sonstige=1))
        self.assertEqual(result["Unfallklasse"].tolist(), ["Rad-PKW", "Fuss-Sonstig"])

    def test_three_or_more_participants(self):
        result = classify(crash(rad=1, pkw=1, fuss=1))
        self.assertEqual(result["Unfallklasse"].tolist(), ["3+ Arten"])

    def test_no_participant(self):
        result = classify(crash())
        self.assertEqual(result["Unfallklasse"].tolist(), ["Keine dieser Arten"])

    def test_missing_or_invalid_values_are_unclear(self):
        result = classify(crash(rad=None, pkw=1), crash(rad=2), crash(rad="x"))
        self.assertEqual(result["Unfallklasse"].tolist(), ["Unklar"] * 3)

    def test_severity_is_readable(self):
        result = classify(crash(rad=1, kategorie="1"), crash(rad=1, kategorie="2"), crash(rad=1))
        self.assertEqual(
            result["Unfallkategorie"].tolist(),
            ["Unfall mit Getöteten", "Unfall mit Schwerverletzten", "Unfall mit Leichtverletzten"],
        )

    def test_empty_input(self):
        result = CrashClassification.classify(pd.DataFrame(columns=["IstRad", "UKATEGORIE"]))
        self.assertIn("Unfallklasse", result.columns)
        self.assertTrue(result.empty)

    def test_input_is_not_modified(self):
        crashes = pd.DataFrame([crash(rad=1)])
        CrashClassification.classify(crashes)
        self.assertNotIn("Unfallklasse", crashes.columns)


if __name__ == "__main__":
    unittest.main()
