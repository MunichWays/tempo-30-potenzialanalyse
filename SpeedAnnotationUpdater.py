

class SpeedAnnotationUpdater:
    @staticmethod 
    def update_speed_annotation(streets_gdf, osm_ids_to_annotate, new_val):
        if(len(osm_ids_to_annotate) > 0):
            gap_potential_street_gdf = streets_gdf[streets_gdf["osm_id"].isin(osm_ids_to_annotate)]

            gap_potential_filtered_for_names = gap_potential_street_gdf[gap_potential_street_gdf["name"].notna()]
            gap_potential_filtered_for_explicit_50_data = gap_potential_filtered_for_names[gap_potential_filtered_for_names["maxspeed_class"] == "50"]

            osm_ids_to_update = gap_potential_filtered_for_explicit_50_data["osm_id"].to_list()

            streets_copy_gdf = streets_gdf.copy()
            streets_copy_gdf.loc[streets_copy_gdf["osm_id"].isin(osm_ids_to_update), "maxspeed_class"] = new_val

            print("Updated streets with T30 potential")
            return streets_copy_gdf
        else:
            return streets_gdf