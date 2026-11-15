"""Package the fixtures as two local uMap layers, with object details on the map.

Run from any directory: python tests/fixtures/build_fixture_map.py --output /tmp/tests.umap
This only packages the GeoJSON; it does not generate or calculate test data.
"""

import argparse
import json
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"


def _build_map():
    """Place display areas beneath the independently selectable test objects."""
    layers = [json.loads((FIXTURES / name).read_text(encoding="utf-8"))
              for name in ("groups.geojson", "scenarios.geojson")]
    return {
        "type": "umap",
        "geometry": {"type": "Point", "coordinates": [5.31, 55.03]},
        "properties": {"name": "Analysis test examples", "zoom": 12,
                       "popupShape": "Default", "onLoadPanel": "none"},
        "layers": layers,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(_build_map(), ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
