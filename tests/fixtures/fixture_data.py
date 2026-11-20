"""Load the single, directly viewable GeoJSON fixture; never generate geometry.

The atlas is stored in WGS84 for uMap. Metric fixtures were authored on a
micrometre grid. After reprojection, snap back to that grid to remove numerical
round-trip noise (nanometres) at exact query and corridor-length boundaries.
This does not buffer features or alter the production detector's tolerances.
"""

import json
from pathlib import Path

import geopandas as gpd
from shapely import set_precision


FIXTURE_PATH = Path(__file__).with_name("scenarios.geojson")
METADATA = {"scenario", "role", "fixture_id", "fixture_crs", "fixture_index",
            "test_file", "label", "description", "expected_outcome", "_umap_options",
            "group_id", "group_title", "input_details", "expected_details",
            "input_case"}


def features(scenario, role):
    """Fresh decoded objects ensure one test cannot mutate another's fixtures."""
    collection = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    selected = [f for f in collection["features"]
                if f["properties"]["scenario"] == scenario and f["properties"]["role"] == role]
    if not selected:
        raise ValueError(f"No fixture features for {scenario!r}/{role!r}")
    return selected


def frame(scenario, role="streets", crs=None):
    """Select inputs, strip display metadata, optionally return original WGS84.

    With no crs argument, return the scenario's metric CRS. Reprojection/row
    order/property variants are applied explicitly by the individual tests.
    """
    selected = features(scenario, role)
    native_crs = selected[0]["properties"]["fixture_crs"]
    rows = [{"type": "Feature", "geometry": f["geometry"],
             "properties": {k: v for k, v in f["properties"].items() if k not in METADATA}}
            for f in selected]
    result = gpd.GeoDataFrame.from_features(rows, crs="EPSG:4326")
    if "fixture_index" in selected[0]["properties"]:
        result.index = [f["properties"]["fixture_index"] for f in selected]
    if crs == "EPSG:4326":
        return result
    result = result.to_crs(native_crs)
    # Preserve vertex order and ring orientation while restoring the metric grid.
    # Reset GEOS precision afterwards: detectors should still perform ordinary
    # floating-point operations, not inherit a fixed-precision arithmetic model.
    result.geometry = result.geometry.map(
        lambda g: set_precision(set_precision(g, 1e-6, mode="pointwise"), 0, mode="pointwise")
    )
    return result if crs is None or crs == native_crs else result.to_crs(crs)
