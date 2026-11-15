from PotentialCalculation.PotentialCalculationResult import PotentialCalculationResult

from typing import Dict
from collections import defaultdict


def _merge_dicts(left, right):
    """Merge two dictionaries, taking values from the right on shared keys.

    Example input: left={"school": "old"},
    right={"school": "new", "gap": "T30_Potenzial_Luecke"}.
    Example output: {"school": "new", "gap": "T30_Potenzial_Luecke"}.
    """
    return {**left, **right}


class SpeedAnnotationUpdater:
    """Assign a justification label for a street segment that has any number
      of indicators for a reduction of speed limit.

    Since the different reasons for speed limits (gap, crossing, building) are
    calculated independently, the results are combined here.
    The label `T30_Potenzial_Multifaktor` is used for streets with multiple reasons.
    """

    @staticmethod
    def _get_feature_annotation_for_key(key, building_configs):
        """Find the label for one potential key.

        Example input: key="school",
        building_configs={"school": {"speed_annotation": "T30_Potenzial_Schule"}}.
        Example output: "T30_Potenzial_Schule".
        Unknown keys print a message and return "Unknown".
        """
        annotations = _merge_dicts(
            {
                name: config["speed_annotation"]
                for name, config in building_configs.items()
                if name == key and name not in ("zebra", "gap")
            },
            {
                "zebra": "T30_Potenzial_Zebrastreifen",
                "gap": "T30_Potenzial_Luecke",
            },
        )
        if key not in annotations:
            print("Unknown potential type", key)
        return annotations.get(key, "Unknown")


    @staticmethod
    def _collect_annotations_for_osm_ids(potential_results : Dict[str, PotentialCalculationResult], building_configs):
        """Collect every reason's label under its selected street IDs.

        Example input: potential_results={
            "zebra": PotentialCalculationResult([7, 8], []),
            "gap": PotentialCalculationResult([8], []),
        }, building_configs={}.
        Example output: dict(result) == {
            7: ["T30_Potenzial_Zebrastreifen"],
            8: ["T30_Potenzial_Zebrastreifen", "T30_Potenzial_Luecke"],
        }.
        """
        osm_id_to_annotations = defaultdict(list)
        for key, potential_result in potential_results.items():
            annotation = SpeedAnnotationUpdater._get_feature_annotation_for_key(key, building_configs)

            for osm_id in potential_result.street_ids:
                osm_id_to_annotations[osm_id].append(annotation)

        return osm_id_to_annotations


    @staticmethod
    def annotate_gdf_with_potential_type(streets_gdf, potential_results, building_configs):
        """Return a copy of streets with reason labels assigned by OSM ID.

        Example input: streets_gdf is a DataFrame with osm_id [7, 8, 9]
        and feature_type ["street", "street", "street"];
        potential_results={"zebra": PotentialCalculationResult([7, 8], []),
                           "gap": PotentialCalculationResult([8], [])};
        building_configs={}.
        Example output: a copy with feature_type
        ["T30_Potenzial_Zebrastreifen", "T30_Potenzial_Multifaktor", "street"].
        The input DataFrame is unchanged.
        """
        streets_copy_gdf = streets_gdf.copy()

        annotations = SpeedAnnotationUpdater._collect_annotations_for_osm_ids(potential_results, building_configs)

        final_annotations = dict(map(
            lambda item: (
                item[0],
                item[1].pop() if len(item[1]) == 1 else "T30_Potenzial_Multifaktor",
            ),
            annotations.items(),
        ))

        for osm_id, annotation in final_annotations.items():
            streets_copy_gdf.loc[streets_copy_gdf["osm_id"] == osm_id, "feature_type"] = annotation

        return streets_copy_gdf

    @staticmethod
    def _annotate_ids_with_feature_type(streets_gdf, osm_ids_to_annotate, new_val):
        """Assign one label to selected IDs and return the updated table.

        Example input: streets_gdf is a DataFrame with osm_id [7, 8, 9]
        and feature_type ["street", "street", "street"];
        osm_ids_to_annotate=[7, 9]; new_val="T30_Potenzial_Zebrastreifen".
        Example output: a copy with feature_type
        ["T30_Potenzial_Zebrastreifen", "street",
         "T30_Potenzial_Zebrastreifen"]. With no IDs, return the input itself.
        """
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
