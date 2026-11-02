from dataclasses import dataclass


@dataclass(frozen=True)
class RegionDefinition:
    key: str
    display_name: str
    osm_relation_id: int | None = None
    bbox: tuple[float, float, float, float] | None = None