from typing import List
import geopandas as gpd

from PotentialCalculation.PotentialCalculationResult import PotentialCalculationResult


class ProximityPotential:
    @staticmethod
    def find_tempo50_segments_near_features(
        streets_gdf: gpd.GeoDataFrame,
        features_gdf: gpd.GeoDataFrame,
        search_distance_m: float = 15.0,
        metric_crs: str = "EPSG:25832",
    ) -> PotentialCalculationResult:
        """
        Finds OSM IDs of tempo-50/60 street segments that are within
        search_distance_m of given spatial features (schools, hospitals, etc.)
        """

        if streets_gdf is None or streets_gdf.empty:
            return PotentialCalculationResult([], [])

        if features_gdf is None or features_gdf.empty:
            return PotentialCalculationResult([], [])

        # -----------------------------
        # KEEP YOUR ORIGINAL LOGIC (unchanged)
        # -----------------------------
        tempo50_or_60 = streets_gdf[
            streets_gdf["maxspeed_class"].isin({"50", "60"})
        ].copy()

        # Filter out streets with conditional tempo 30
        tempo50_or_60 = tempo50_or_60.loc[
            tempo50_or_60["conditional_speed"] != "30"
        ]

        if tempo50_or_60.empty:
            return PotentialCalculationResult([], [])

        # -----------------------------
        # CRS handling
        # -----------------------------
        if tempo50_or_60.crs != metric_crs:
            tempo50_or_60 = tempo50_or_60.to_crs(metric_crs)

        features = features_gdf.copy()
        if features.crs != metric_crs:
            features = features.to_crs(metric_crs)

        # -----------------------------
        # Buffer features
        # -----------------------------
        features_buffered = features.copy()
        features_buffered["geometry"] = features.geometry.buffer(search_distance_m)

        features_buffered = features_buffered[["osm_id", "geometry"]].rename(
            columns={"osm_id": "feature_id"}
        )

        # -----------------------------
        # Spatial Join
        # -----------------------------
        joined = gpd.sjoin(
            tempo50_or_60,
            features_buffered,
            how="inner",
            predicate="intersects"
        )

        # -----------------------------
        # Result
        # -----------------------------
        street_ids = joined["osm_id"].drop_duplicates().tolist()
        feature_ids = joined["feature_id"].drop_duplicates().tolist()

        return PotentialCalculationResult(
            street_ids=street_ids,
            opt_source_ids=feature_ids
        )