from typing import Tuple
import hashlib
from pathlib import Path
import json

from RegionDefinition import RegionDefinition

class OSMDataCache:
    def __init__(self, datatype, cache_dir: str = "./overpass_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.datatype = datatype

    def load_file_from_cache(self, region_definition):
        cache_file = self._cache_path(region_definition)

        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return None

    def _cache_path(self : str, region_definition: RegionDefinition) -> Path:
        return self.cache_dir / f"{self.datatype}_{region_definition.key}.json"
    
    def store_data(self, data, region_definition):
        cache_file = self._cache_path(region_definition)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)