
from sklearn.cluster import DBSCAN
import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

class PlaygroundConsolidation:
    def summarize_playground_features(playgroundGDF : gpd.GeoDataFrame, eps_meters = 15, min_samples = 1):
        """
        Group nearby GeoJSON Point features where:
            properties["potential_candidate"] == False

        Nearby points are merged into a single centroid point.

        Parameters
        ----------
        geojson_data : dict
            GeoJSON FeatureCollection

        eps_meters : float
            Maximum distance between points to belong to same cluster

        min_samples : int
            DBSCAN min_samples parameter

        Returns
        -------
        dict
            GeoJSON FeatureCollection with grouped features
        """

        # Convert to GeoDataFrame
        gdf = playgroundGDF.copy()

        # Ensure CRS
        gdf = gdf.set_crs("EPSG:4326")

        # Convert to metric CRS for distance calculations
        gdf_metric = gdf.to_crs("EPSG:32632")

        mask = (gdf_metric["potential_candidate"] == False) & (gdf_metric.geometry.geom_type == "Point")
        subset = gdf_metric[mask].copy()

        if subset.empty:
            return gdf

        # Coordinates for clustering
        coords = pd.DataFrame({
            "x": subset.geometry.x,
            "y": subset.geometry.y
        })

        # Cluster nearby points
        clustering = DBSCAN(
            eps=eps_meters,
            min_samples=min_samples
        ).fit(coords)

        subset["cluster_id"] = clustering.labels_

        output_features = []
        processed_clusters = set()

        # Process clustered non-candidates
        for _, row in subset.iterrows():

            cluster_id = row["cluster_id"]

            if cluster_id in processed_clusters:
                continue

            cluster = subset[subset["cluster_id"] == cluster_id]

            # Single feature -> keep original
            if len(cluster) == 1:
                geometry = row.geometry

            # Multiple features -> merge to centroid
            else:
                geometry = cluster.geometry.unary_union.centroid

            output_features.append({
                "type": "Feature",
                "properties": {
                    "potential_candidate": False
                },
                "geometry": mapping(geometry)
            })

            processed_clusters.add(cluster_id)

        # Add untouched candidate features
        untouched = gdf_metric[~mask]

        for _, row in untouched.iterrows():
            output_features.append({
                "type": "Feature",
                "properties": {
                    "potential_candidate": row.potential_candidate
                },
                "geometry": mapping(row.geometry)
            })

        # Convert back to WGS84
        output_gdf = gpd.GeoDataFrame.from_features(output_features)
        output_gdf = output_gdf.set_crs("EPSG:32632")
        output_gdf = output_gdf.to_crs("EPSG:4326")

        return output_gdf
