

class SpeedAnnotationUpdater:
    @staticmethod 
    def update_speed_annotation(streets_gdf, osm_ids_to_annotate, new_val):
        if(len(osm_ids_to_annotate) > 0):
            streets_copy_gdf = streets_gdf.copy()

            streets_copy_gdf.loc[
                streets_copy_gdf["osm_id"].isin(osm_ids_to_annotate),
                "feature_type"
            ] = new_val

            print("Annotated streets with T30 potential")
            return streets_copy_gdf
        else:
            return streets_gdf