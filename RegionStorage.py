# CityStorage.py
from pathlib import Path

import yaml

from RegionDefinition import RegionDefinition

REGIONS_DIR = Path(__file__).parent / "data" / "regions"

class RegionStorage:
    @classmethod
    def get(cls, name: str) -> RegionDefinition:
        key = name.strip().lower()
        path = REGIONS_DIR / f"{key}.yaml"

        if not path.is_file():
            options = sorted(file.stem for file in REGIONS_DIR.glob("*.yaml"))
            raise ValueError(
                f"Unbekannte Region '{name}'. Verfügbar: {', '.join(options)}"
            )

        with path.open(encoding="utf-8") as file:
            data = yaml.safe_load(file)

        return cls._parse(key, data)

    @staticmethod
    def _parse(key: str, data: object) -> RegionDefinition:
        if not isinstance(data, dict):
            raise ValueError(f"Die YAML-Konfiguration für '{key}' muss ein Objekt sein.")

        display_name = data.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError(f"'{key}' benötigt einen display_name.")

        relation_id = data.get("osm_relation_id")
        if relation_id is not None:
            if not isinstance(relation_id, int) or isinstance(relation_id, bool) or relation_id <= 0:
                raise ValueError(f"Ungültige osm_relation_id für '{key}'.")

        bbox_data = data.get("bbox")
        bbox = None

        if bbox_data is not None:
            if (
                not isinstance(bbox_data, list)
                or len(bbox_data) != 4
                or not all(
                    isinstance(value, (int, float)) and not isinstance(value, bool)
                    for value in bbox_data
                )
            ):
                raise ValueError(
                    f"bbox für '{key}' muss vier Zahlen enthalten: "
                    "[south, west, north, east]."
                )

            south, west, north, east = map(float, bbox_data)

            if not (-90 <= south < north <= 90):
                raise ValueError(f"Ungültige Süd-/Nordwerte in der bbox für '{key}'.")
            if not (-180 <= west < east <= 180):
                raise ValueError(f"Ungültige West-/Ostwerte in der bbox für '{key}'.")

            bbox = (south, west, north, east)

        return RegionDefinition(
            key=key,
            display_name=display_name.strip(),
            osm_relation_id=relation_id,
            bbox=bbox,
        )
