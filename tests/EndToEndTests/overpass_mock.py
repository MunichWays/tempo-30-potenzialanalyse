"""
Helpers to fake the Overpass API for end-to-end tests.

``OverpassWorld`` is a tiny in-memory OSM data set. Tests place streets, zebra
crossings and buildings in metres relative to an origin, and the world renders
them as Overpass JSON responses (``{"elements": [...]}``) in the same shape the
real API returns for the queries built by the retrieval classes.

``OverpassApiMock`` replaces ``requests.post``: it looks at the Overpass query,
decides which data set is requested (streets, zebra crossings or one of the
building types) and answers with the matching response from the world.
"""

import copy
import math
from collections import defaultdict
from unittest.mock import Mock

METERS_PER_DEG_LAT = 111_195.0


def offset(lon: float, lat: float, east_m: float = 0.0, north_m: float = 0.0) -> tuple[float, float]:
    """Shift a WGS84 coordinate by the given number of metres."""
    meters_per_deg_lon = METERS_PER_DEG_LAT * math.cos(math.radians(lat))
    return (
        round(lon + east_m / meters_per_deg_lon, 7),
        round(lat + north_m / METERS_PER_DEG_LAT, 7),
    )


class OverpassWorld:
    STREETS = "streets"
    ZEBRAS = "zebra_crossing"

    def __init__(self, building_configs: dict):
        self.building_configs = building_configs
        self._next_id = 1
        self._street_nodes: dict[tuple[float, float], dict] = {}
        self._elements: dict[str, list[dict]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Building blocks
    # ------------------------------------------------------------------
    def _new_id(self) -> int:
        new_id = self._next_id
        self._next_id += 1
        return new_id

    def _node(self, lon: float, lat: float, tags: dict | None = None) -> dict:
        node = {"type": "node", "id": self._new_id(), "lat": lat, "lon": lon}
        if tags:
            node["tags"] = tags
        return node

    def _street_node(self, coord: tuple[float, float]) -> int:
        # Adjacent streets share their end nodes, just like in OSM
        if coord not in self._street_nodes:
            node = self._node(*coord)
            self._street_nodes[coord] = node
            self._elements[self.STREETS].append(node)
        return self._street_nodes[coord]["id"]

    # ------------------------------------------------------------------
    # Public API for tests
    # ------------------------------------------------------------------
    def add_street(
        self,
        coords: list[tuple[float, float]],
        maxspeed: str | None = "50",
        name: str = "Teststraße",
        highway: str = "secondary",
        extra_tags: dict | None = None,
    ) -> int:
        tags = {"highway": highway, "name": name}
        if maxspeed is not None:
            tags["maxspeed"] = maxspeed
        tags.update(extra_tags or {})

        way_id = self._new_id()
        self._elements[self.STREETS].append({
            "type": "way",
            "id": way_id,
            "nodes": [self._street_node(c) for c in coords],
            "tags": tags,
        })
        return way_id

    def add_zebra(self, coord: tuple[float, float]) -> int:
        node = self._node(*coord, tags={"highway": "crossing", "crossing": "zebra"})
        self._elements[self.ZEBRAS].append(node)
        return node["id"]

    def add_building(
        self,
        datatype: str,
        coord: tuple[float, float],
        name: str | None = None,
        size_m: float | None = None,
    ) -> int:
        """
        Add a feature of the given building type (key of BUILDING_CONFIGS).

        Without ``size_m`` the feature is a tagged node at ``coord``. With
        ``size_m`` it is a closed way (square polygon centred on ``coord``)
        followed by its untagged member nodes, as returned by
        ``out tags body; >; out skel qt;``.
        """
        if datatype not in self.building_configs:
            raise KeyError(f"Unknown building type {datatype}")

        tag_key, tag_values = next(iter(self.building_configs[datatype]["tags"].items()))
        tags = {tag_key: tag_values[0]}
        if name is not None:
            tags["name"] = name

        elements = self._elements[datatype]

        if size_m is None:
            node = self._node(*coord, tags=tags)
            elements.append(node)
            return node["id"]

        half = size_m / 2
        corners = [
            self._node(*offset(*coord, -half, -half)),
            self._node(*offset(*coord, half, -half)),
            self._node(*offset(*coord, half, half)),
            self._node(*offset(*coord, -half, half)),
        ]
        way_id = self._new_id()
        elements.append({
            "type": "way",
            "id": way_id,
            "nodes": [n["id"] for n in corners] + [corners[0]["id"]],
            "tags": tags,
        })
        elements.extend(corners)
        return way_id

    def response(self, datatype: str) -> dict:
        return {
            "version": 0.6,
            "generator": "Overpass API mock",
            "elements": copy.deepcopy(self._elements[datatype]),
        }


class OverpassApiMock:
    """Callable replacement for ``requests.post`` against the Overpass API."""

    def __init__(self, world: OverpassWorld, expected_region_filter: str | None = None):
        self.world = world
        self.expected_region_filter = expected_region_filter
        self.requested: list[str] = []

        # Every building config produces a unique amenity filter in its query
        self._building_markers = {
            datatype: '"amenity"~"{}"'.format("|".join(config["tags"]["amenity"]))
            for datatype, config in world.building_configs.items()
        }

    def classify(self, query: str) -> str:
        if '"crossing"="zebra"' in query:
            return OverpassWorld.ZEBRAS

        matches = [d for d, marker in self._building_markers.items() if marker in query]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise AssertionError(f"Ambiguous Overpass query, matches {matches}:\n{query}")

        if 'way["highway"]' in query:
            return OverpassWorld.STREETS

        raise AssertionError(f"Unexpected Overpass query:\n{query}")

    def __call__(self, url, data=None, timeout=None, headers=None, **kwargs):
        query = data["data"]
        if self.expected_region_filter is not None and self.expected_region_filter not in query:
            raise AssertionError(
                f"Query does not use region filter {self.expected_region_filter}:\n{query}"
            )

        datatype = self.classify(query)
        self.requested.append(datatype)

        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = self.world.response(datatype)
        return response
