import requests
import time
from collections import defaultdict

from DataRetrieval.OSMDataCache import OSMDataCache


class OSMDataRetrieval:
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self, timeout=180):
        self.timeout = timeout
        self.cache = OSMDataCache(datatype="unified")

    # --------------------------------------------------
    # Tag Aggregation
    # --------------------------------------------------
    def aggregate_tags(self, config_dict):
        aggregated = defaultdict(set)

        for cfg in config_dict.values():
            for key, values in cfg["tags"].items():
                aggregated[key].update(values)

        return {k: sorted(v) for k, v in aggregated.items()}

    # --------------------------------------------------
    # Query Builder
    # --------------------------------------------------
    def _build_query(self, bbox, aggregated_tags):
        def build_blocks(selector):
            blocks = []
            for key, values in aggregated_tags.items():
                regex = "|".join(values)

                blocks.append(f'node["{key}"~"{regex}"]{selector};')
                blocks.append(f'way["{key}"~"{regex}"]{selector};')
                blocks.append(f'relation["{key}"~"{regex}"]{selector};')

            return "\n".join(blocks)

        if isinstance(bbox, str):
            area = f'area[admin_level=6]["name"="{bbox}"]->.a;'
            selector = "(area.a)"
        else:
            south, west, north, east = bbox
            area = ""
            selector = f"({south},{west},{north},{east})"

        return f"""
        [out:json][timeout:{self.timeout}];
        (
            {area}

            // Streets
            way["highway"]{selector};

            // Zebra crossings
            node["crossing"="zebra"]{selector};
            way["crossing"="zebra"]{selector};

            // Dynamic tags
            {build_blocks(selector)}
        );
        out body;
        >;
        out skel qt;
        """

    # --------------------------------------------------
    # Fetch with Retry
    # --------------------------------------------------
    def _fetch_with_retry(self, query):
        headers = {"User-Agent": "Speed-limit-30-tool"}

        for attempt in range(5):
            try:
                response = requests.post(
                    self.OVERPASS_URL,
                    data={"data": query},
                    timeout=self.timeout,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException:
                wait = min(60, 2 ** attempt)
                print(f"Retry in {wait}s...")
                time.sleep(wait)

        raise RuntimeError("Overpass request failed")

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------
    def fetch(self, bbox, config_dict):
        cached = self.cache.load_file_from_cache(bbox)
        if cached:
            print("Using unified cache")
            return cached

        aggregated_tags = self.aggregate_tags(config_dict)
        query = self._build_query(bbox, aggregated_tags)

        print("Fetching unified OSM data...")
        data = self._fetch_with_retry(query)

        self.cache.store_data(data, bbox)
        return data