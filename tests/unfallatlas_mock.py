"""
Helpers to fake the Unfallatlas open data server in tests.

``UnfallatlasServerMock`` replaces ``requests.get``: it serves an ``index.json``
listing the configured years and one zip per year containing a CSV in the
format of the real data set (UTF-8 with BOM, ";" separator, decimal comma).
"""

import io
import json
import zipfile
from unittest.mock import MagicMock

HEADER = [
    "UIDENTSTLAE", "ULAND", "UREGBEZ", "UKREIS", "UGEMEINDE", "UJAHR", "UMONAT",
    "USTUNDE", "UWOCHENTAG", "UKATEGORIE", "UART", "UTYP1", "ULICHTVERH",
    "IstStrassenzustand", "IstRad", "IstPKW", "IstFuss", "IstKrad", "IstGkfz",
    "IstSonstige", "LINREFX", "LINREFY", "XGCSWGS84", "YGCSWGS84", "PLST",
]

PARTICIPANTS = ["Rad", "PKW", "Fuss", "Krad", "Gkfz", "Sonstige"]


def crash_row(lon: float, lat: float, year: int, involved=("PKW",), category: int = 3,
              header: list[str] = HEADER) -> list[str]:
    values = {
        "UIDENTSTLAE": f"{year}{lon}{lat}",
        "ULAND": "09", "UREGBEZ": "1", "UKREIS": "79", "UGEMEINDE": "000",
        "UJAHR": str(year), "UMONAT": "05", "USTUNDE": "15", "UWOCHENTAG": "3",
        "UKATEGORIE": str(category), "UART": "5", "UTYP1": "3", "ULICHTVERH": "0",
        "IstStrassenzustand": "0",
        "LINREFX": "0,0", "LINREFY": "0,0",
        "XGCSWGS84": str(lon).replace(".", ","),
        "YGCSWGS84": str(lat).replace(".", ","),
        "PLST": "1",
    }
    for participant in PARTICIPANTS:
        values[f"Ist{participant}"] = "1" if participant in involved else "0"
    values["IstSonstig"] = values["IstSonstige"]
    return [values[column] for column in header]


def build_zip(rows: list[list[str]], header: list[str] = HEADER) -> bytes:
    lines = [";".join(header)] + [";".join(row) for row in rows]
    csv_bytes = ("﻿" + "\r\n".join(lines) + "\r\n").encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("csv/schema.ini", "[dummy]")
        archive.writestr("csv/Unfallorte_LR_BasisDLM.csv", csv_bytes)
    return buffer.getvalue()


class UnfallatlasServerMock:
    """Callable replacement for ``requests.get`` against the Unfallatlas server."""

    def __init__(self, years: list[int]):
        self.crashes: dict[int, list[list[str]]] = {year: [] for year in years}
        self.requested: list[str] = []

    def add_crash(self, lon: float, lat: float, year: int, **kwargs) -> None:
        self.crashes[year].append(crash_row(lon, lat, year, **kwargs))

    def __call__(self, url, stream=False, timeout=None, **kwargs):
        self.requested.append(url)
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        if url.endswith("index.json"):
            response.text = json.dumps({
                "datasets": [{"files": [
                    {"name": f"Unfallorte{year}_EPSG25832_{kind}.zip"}
                    for year in self.crashes for kind in ("CSV", "Shape")
                ]}]
            })
            return response

        year = next(year for year in self.crashes if f"Unfallorte{year}_EPSG25832_CSV.zip" in url)
        content = build_zip(self.crashes[year])
        response.iter_content.return_value = iter([content])
        return response
