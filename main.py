import matplotlib.pyplot as plt

from DataRetrieval.SegmentRetrieval import SegmentRetrieval
from DataRetrieval.ZebraCrossingRetrieval import ZebraCrossingRetrieval
from DataRetrieval.SpecificBuildingRetrieval import SpecificBuildingRetrieval

from PotentialCalculation.ZebraPotential import ZebraPotential
from PotentialCalculation.ProximityPotential import ProximityPotential
from PotentialCalculation.GapPotential import Tempo50GapPotential
from PotentialCalculation.PotentialCalculationResult import PotentialCalculationResult

from SpeedAnnotationUpdater import SpeedAnnotationUpdater
from BoundingBoxStorage import BoundingBoxStorage

from DataOutput.GeoJsonCreator import GeoJsonCreator
from DataOutput.PrintOutput import PrintOutput
from DataOutput.StreetPlot import StreetPlot

area_under_creation = "München"

if(area_under_creation != "München"):
    used_bbox = BoundingBoxStorage.get(area_under_creation)
else:
    used_bbox : str = "München" # Special case -> Handled differently in overpass query

#######################################
# Retrieve (and print) raw data
#######################################

sr = SegmentRetrieval()
streets_gdf = sr.fetch_as_geodataframe(used_bbox)

zebra_retrieval = ZebraCrossingRetrieval(timeout=120)
zebra_gdf = zebra_retrieval.fetch_zebra_crossings(used_bbox)

StreetPlot.plot_map(streets_gdf = streets_gdf, zebra_gdf = zebra_gdf)

building_configs = {
    "educational_buildings": {
        "amenities": ["school", "kindergarten"],
        "regex": r"(kindergarten|grundschule|hauptschule|realschule|mittelschule|gymnasium|gesamtschule)",
        "speed_annotation" : "T30_Potenzial_Schule"
    },
    "hospitals": {
        "amenities": ["hospital"],
        "regex": r"(krankenhaus|klinikum)",
        "speed_annotation" : "T30_Potenzial_Krankenhaus"
    },
    "elderly_homes": {
        "amenities": ["nursing_home", "retirement_home", "care_home", "social_facility"],
        "regex": r"(alten|pflegeheim|pflege-heim|senioren|stift)",
        "speed_annotation" : "T30_Potenzial_Altenheim"
    }
}
building_data = SpecificBuildingRetrieval.retrieve_building_data(bbox = used_bbox, building_configs = building_configs)

#######################################
# Identify potential
#######################################

# Zebra crossings
print("Identifying Zebra Crossings ...")
zebra_potential_result : PotentialCalculationResult = ZebraPotential.find_tempo50_segments_near_zebra(streets_gdf = streets_gdf, zebras_gdf = zebra_gdf, search_distance_m = 15)

# Buildings
building_potential_results : dict[str, PotentialCalculationResult] = {}
for key in building_data.keys():
    print(f"Identifiying Street near {key}")
    building_potential_results[key] = ProximityPotential.find_tempo50_segments_near_features(streets_gdf = streets_gdf, features_gdf = building_data[key], search_distance_m = 50)

print("Identifying Gaps ...")
gap_potential_result : PotentialCalculationResult= Tempo50GapPotential.find_all_tempo_50_gaps(gdf = streets_gdf)

#######################################
# Create street dataset w. Annotations
#######################################
streets_updated_gdf = SpeedAnnotationUpdater.update_speed_annotation(streets_gdf = streets_gdf, osm_ids_to_annotate = zebra_potential_result.street_ids, new_val = "T30_Potenzial_Zebrastreifen")

for key, potential_result in building_potential_results.items():
    new_val = building_configs[key]["speed_annotation"]
    streets_updated_gdf = SpeedAnnotationUpdater.update_speed_annotation(streets_gdf = streets_updated_gdf, osm_ids_to_annotate = potential_result.street_ids, new_val = new_val)

streets_updated_gdf = SpeedAnnotationUpdater.update_speed_annotation(streets_gdf = streets_updated_gdf, osm_ids_to_annotate = gap_potential_result.street_ids, new_val = "T30_Potenzial_Luecke")

#######################################
# Annotate sources
#######################################

zebra_gdf["potential_candidate"] = zebra_gdf["osm_id"].isin(zebra_potential_result.opt_source_ids)

for key, bdg_data in building_data.items():
    corresponding_result = building_potential_results[key]
    bdg_data["potential_candidate"] = bdg_data["osm_id"].isin(corresponding_result.opt_source_ids)

#######################################
# File / Print / Map Output
#######################################

streets_with_potential = streets_updated_gdf[
    streets_updated_gdf["maxspeed_class"].str.startswith("T30_Potenzial", na=False)
]

# Print if required
PrintOutput.print_streets(streets_with_potential)

GeoJsonCreator.create_geojson_layer_files(folder_name = area_under_creation, streets_with_potential = streets_with_potential,
                                          streets_w_limit_gdf = streets_gdf, zebra_gdf = zebra_gdf, building_data = building_data)


# Plotting
StreetPlot.plot_map(streets_gdf = streets_updated_gdf, zebra_gdf = zebra_gdf, bdg_data = building_data)

plt.show()
