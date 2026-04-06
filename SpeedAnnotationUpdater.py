from PotentialCalculation.PotentialCalculationResult import PotentialCalculationResult

from typing import Dict
from collections import defaultdict

class SpeedAnnotationUpdater:

    @staticmethod 
    def get_feature_annotation_for_key(key, building_configs):
        if key == "zebra":
            feature_annotation = "T30_Potenzial_Zebrastreifen"
        elif key == "gap":
            feature_annotation = "T30_Potenzial_Luecke"
        elif key in building_configs.keys():
            feature_annotation = building_configs[key]["speed_annotation"]
        else:
            print("Unknown potential type", key)
            feature_annotation = "Unknown"

        return feature_annotation
    

    @staticmethod 
    def collect_annotations_for_osm_ids(potential_results : Dict[str, PotentialCalculationResult], building_configs):  
        osm_id_to_annotations = defaultdict(list)
        for key, potential_result in potential_results.items():
            annotation = SpeedAnnotationUpdater.get_feature_annotation_for_key(key, building_configs)  # or get_annotation(key)

            for osm_id in potential_result.street_ids:
                osm_id_to_annotations[osm_id].append(annotation)

        return osm_id_to_annotations
    

    @staticmethod 
    def determine_final_annotation(id_annotation_dict):
        final_osm_annotation = {}

        for osm_id, annotations in id_annotation_dict.items():
            if len(annotations) == 1:
                final_osm_annotation[osm_id] = annotations.pop()
            else:
                final_osm_annotation[osm_id] = "T30_Potenzial_Multifaktor"

        return final_osm_annotation
    

    @staticmethod 
    def annotate_gdf_with_potential_type(streets_gdf, potential_results, building_configs):
        streets_copy_gdf = streets_gdf.copy()

        annotations = SpeedAnnotationUpdater.collect_annotations_for_osm_ids(potential_results, building_configs)

        final_annotations = SpeedAnnotationUpdater.determine_final_annotation(annotations)

        for osm_id, annotation in final_annotations.items():
            streets_copy_gdf.loc[streets_copy_gdf["osm_id"] == osm_id, "feature_type"] = annotation

        return streets_copy_gdf
    
    #######################################
    # Create street dataset w. Annotations
    #######################################
    #all_potential_street_ids = []
    #for key, potential_result in potential_results.keys():
    #    all_potential_street_ids.extend(potential_result.street_ids)


# for key, potential_result in potential_results.items():
#     if key == "zebra":
#         feature_annotation = "T30_Potenzial_Zebrastreifen"
#     elif key == "gap":
#         feature_annotation = "T30_Potenzial_Luecke"
#     elif key in building_configs.keys():
#         feature_annotation = building_configs[key]["speed_annotation"]
#     else:
#         print("Unknown potential type", key)
#         feature_annotation = "Unknown"
    
#     streets_updated_gdf = SpeedAnnotationUpdater.update_speed_annotation(streets_gdf = streets_gdf, osm_ids_to_annotate = potential_result.street_ids, new_val = feature_annotation)



    # collect all streets to update
    # Identify ids in multiple datasets
    # allocate ids to the correct type


    @staticmethod 
    def annotate_ids_with_feature_type(streets_gdf, osm_ids_to_annotate, new_val):
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