import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
from shapely.geometry import Polygon, box

from DataRetrieval.CrashDataRetrieval import CrashDataRetrieval

from tests.unfallatlas_mock import HEADER, UnfallatlasServerMock, build_zip, crash_row

REGION = box(11.0, 48.0, 11.2, 48.2)
INSIDE = (11.1, 48.1)
OUTSIDE_BBOX = (11.5, 48.1)


class CrashDataRetrievalTests(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cache_dir = Path(tmp.name) / "cache"
        self.server = UnfallatlasServerMock(years=[2022, 2023, 2024, 2025])

    def fetch(self, years_back=3, region=REGION):
        retrieval = CrashDataRetrieval(years_back=years_back, cache_dir=self.cache_dir, chunksize=2)
        with patch("requests.get", side_effect=self.server), \
             patch("time.sleep"), \
             contextlib.redirect_stdout(io.StringIO()):
            return retrieval.fetch_for_region(region)

    def downloads(self):
        return [url for url in self.server.requested if url.endswith(".zip")]

    def test_only_crashes_inside_region_are_kept(self):
        self.server.add_crash(*INSIDE, 2025)
        self.server.add_crash(*OUTSIDE_BBOX, 2025)

        crashes = self.fetch(years_back=1)[2025]

        self.assertEqual(len(crashes), 1)
        self.assertAlmostEqual(crashes.geometry.iloc[0].x, INSIDE[0])
        self.assertAlmostEqual(crashes.geometry.iloc[0].y, INSIDE[1])
        self.assertEqual(crashes.crs.to_epsg(), 4326)

    def test_clip_uses_polygon_not_only_its_bbox(self):
        triangle = Polygon([(11.0, 48.0), (11.2, 48.0), (11.0, 48.2)])
        self.server.add_crash(11.05, 48.05, 2025)   # inside the triangle
        self.server.add_crash(11.15, 48.15, 2025)   # inside the bbox, outside the triangle

        crashes = self.fetch(years_back=1, region=triangle)[2025]

        self.assertEqual(len(crashes), 1)
        self.assertAlmostEqual(crashes.geometry.iloc[0].x, 11.05)

    def test_latest_years_are_selected(self):
        for year in [2022, 2023, 2024, 2025]:
            self.server.add_crash(*INSIDE, year)

        crashes = self.fetch(years_back=3)

        self.assertEqual(list(crashes), [2023, 2024, 2025])
        for year, crashes_of_year in crashes.items():
            self.assertEqual(crashes_of_year["UJAHR"].tolist(), [str(year)])
        self.assertEqual(len(self.downloads()), 3)

    def test_cached_zips_are_not_downloaded_again(self):
        self.server.add_crash(*INSIDE, 2025)
        self.fetch(years_back=1)
        self.fetch(years_back=1)

        self.assertEqual(len(self.downloads()), 1)
        self.assertEqual([p.name for p in self.cache_dir.iterdir()], ["Unfallorte2025_EPSG25832_CSV.zip"])

    def test_cached_years_are_used_when_index_is_unreachable(self):
        self.cache_dir.mkdir()
        (self.cache_dir / "Unfallorte2024_EPSG25832_CSV.zip").write_bytes(
            build_zip([crash_row(*INSIDE, 2024)])
        )

        retrieval = CrashDataRetrieval(years_back=3, cache_dir=self.cache_dir)
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("offline")), \
             contextlib.redirect_stdout(io.StringIO()):
            crashes = retrieval.fetch_for_region(REGION)

        self.assertEqual(list(crashes), [2024])
        self.assertEqual(crashes[2024]["UJAHR"].tolist(), ["2024"])

    def test_old_column_names_are_normalized(self):
        old_header = [("IstSonstig" if c == "IstSonstige" else c) for c in HEADER]
        self.cache_dir.mkdir()
        (self.cache_dir / "Unfallorte2025_EPSG25832_CSV.zip").write_bytes(
            build_zip([crash_row(*INSIDE, 2025, involved=("Sonstige",), header=old_header)],
                      header=old_header)
        )

        crashes = self.fetch(years_back=1)[2025]

        self.assertEqual(crashes["IstSonstige"].tolist(), ["1"])
        self.assertEqual(crashes["UGEMEINDE"].tolist(), ["000"])  # leading zeros kept

    def test_region_without_crashes_keeps_raw_columns(self):
        self.server.add_crash(*OUTSIDE_BBOX, 2025)

        crashes = self.fetch(years_back=1)[2025]

        self.assertTrue(crashes.empty)
        self.assertEqual(list(crashes.columns), [*HEADER, "geometry"])

    def test_raw_records_are_returned_unclassified(self):
        self.server.add_crash(*INSIDE, 2025)

        crashes = self.fetch(years_back=1)[2025]

        self.assertEqual(list(crashes.columns), [*HEADER, "geometry"])
        self.assertEqual(crashes["XGCSWGS84"].tolist(), ["11,1"])


if __name__ == "__main__":
    unittest.main()
