from typing import List
import geopandas as gpd

from PotentialCalculationResult import PotentialCalculationResult

class EducationBdgPotential:
    @staticmethod
    def find_tempo50_segments_near_educ_bdgs(
        streets_gdf: gpd.GeoDataFrame,
        educational_bdg_gdf: gpd.GeoDataFrame,
        search_distance_m: float = 15.0,
        metric_crs: str = "EPSG:25832"
    ) -> List[int]:
        """
        Ermittelt OSM_IDs von Tempo-50-Straßenabschnitten,
        die sich ≤ search_distance_m zu einem Zebrastreifen befinden.
        """

        if streets_gdf is None or streets_gdf.empty:
            return PotentialCalculationResult([], [])

        if educational_bdg_gdf is None or educational_bdg_gdf.empty:
            return PotentialCalculationResult([], [])

        # -----------------------------
        # Tempo-50-Straßen filtern
        # -----------------------------
        tempo50_or_60 = streets_gdf[
            streets_gdf["maxspeed_class"].isin(
                {"50", "60"}
            )
        ].copy()

        # Filter out streets with conditional tempo 30, since they already have a speed limit
        tempo50_or_60 = tempo50_or_60.loc[tempo50_or_60["conditional_speed"] != "30"]

        if tempo50_or_60.empty:
            return PotentialCalculationResult([], [])

        # -----------------------------
        # In metrisches CRS projizieren
        # -----------------------------
        if tempo50_or_60.crs != metric_crs:
            tempo50_or_60 = tempo50_or_60.to_crs(metric_crs)

        buildings = educational_bdg_gdf.copy()
        if buildings.crs != metric_crs:
            buildings = buildings.to_crs(metric_crs)

        # -----------------------------
        # Zebrastreifen puffern
        # -----------------------------
        buildings_buffered = buildings.copy()
        buildings_buffered["geometry"] = buildings.geometry.buffer(
            search_distance_m
        )

        buildings_buffered = buildings_buffered[["osm_id", "geometry"]].rename(
            columns={"osm_id": "educ_id"}
        )

        # -----------------------------
        # Spatial Join
        # -----------------------------
        joined = gpd.sjoin(
            tempo50_or_60,
            buildings_buffered,
            how="inner",
            predicate="intersects"
        )

        # -----------------------------
        # Ergebnis
        # -----------------------------

        street_ids = joined["osm_id"].drop_duplicates().tolist()
        educ_ids = joined["educ_id"].drop_duplicates().tolist()

        return PotentialCalculationResult(street_ids = street_ids, opt_source_ids = educ_ids)
