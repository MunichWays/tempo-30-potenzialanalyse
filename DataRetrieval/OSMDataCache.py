from typing import Tuple
import hashlib
from pathlib import Path
import json

class OSMDataCache:
    def __init__(self, datatype, cache_dir: str = "./overpass_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.datatype = datatype

    def load_file_from_cache(self, bbox):
        cache_file = self._cache_path(bbox)

        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return None

    def _bbox_cache_key(self, bbox: Tuple[float, float, float, float]) -> str:
        if(not isinstance(bbox, str)):
            bbox_str = "_".join(f"{v:.6f}" for v in bbox)
        else:
            bbox_str = bbox
        return hashlib.md5(bbox_str.encode("utf-8")).hexdigest()

    def _cache_path(self : str, bbox: Tuple[float, float, float, float]) -> Path:
        return self.cache_dir / f"{self.datatype}_{self._bbox_cache_key(bbox)}.json"
    
    def store_data(self, data, bbox):
        cache_file = self._cache_path(bbox)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)