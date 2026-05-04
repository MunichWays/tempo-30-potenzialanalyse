import matplotlib.pyplot as plt
import time

from DataRetrieval.OSMDataRetrieval import OSMDataRetrieval
from DataExtractors.StreetsExtractor import StreetsExtractor
from DataExtractors.ZebraExtractor import ZebraExtractor
from DataExtractors.BuildingExtractor import BuildingExtractor

from config.building_configs import building_configs

from PotentialCalculation.ZebraPotential import ZebraPotential
from PotentialCalculation.ProximityPotential import ProximityPotential
from PotentialCalculation.GapPotential import Tempo50GapPotential
from PotentialCalculation.PotentialCalculationResult import PotentialCalculationResult

from SpeedAnnotationUpdater import SpeedAnnotationUpdater
from BoundingBoxStorage import BoundingBoxStorage

from DataOutput.GeoJsonCreator import GeoJsonCreator
from DataOutput.PrintOutput import PrintOutput
from DataOutput.StreetPlot import StreetPlot

area_under_creation = "isarvorstadt"

if(area_under_creation != "München"):
    used_bbox = BoundingBoxStorage.get(area_under_creation)
else:
    used_bbox : str = "München" # Special case -> Handled differently in overpass query

#######################################
# Retrieve (and print) raw data
#######################################


# 1️⃣ Fetch Overpass once
retrieval = OSMDataRetrieval()
raw_data = retrieval.fetch(used_bbox, building_configs)

# 2️⃣ Extract relevant data and separate
streets_gdf = StreetsExtractor.extract(raw_data)
zebra_gdf = ZebraExtractor.extract(raw_data)

building_data = {
    key: BuildingExtractor.extract(raw_data, cfg)
    for key, cfg in building_configs.items()
}

print("Streets:", len(streets_gdf))
print("Zebra:", len(zebra_gdf))
for k, v in building_data.items():
    print(k, len(v))


#######################################
# Identify potential
#######################################

potential_results : dict[str, PotentialCalculationResult] = {}


# Zebra crossings
print("Identifying Zebra Crossings ...")
potential_results["zebra"] = ZebraPotential.find_tempo50_segments_near_zebra(streets_gdf = streets_gdf, zebras_gdf = zebra_gdf, search_distance_m = 15)

for key in building_data.keys():
    print(f"Identifiying Street near {key}")
    potential_results[key] = ProximityPotential.find_tempo50_segments_near_features(streets_gdf = streets_gdf, features_gdf = building_data[key], search_distance_m = 20)

print("Identifying Gaps ...")
potential_results["gap"] = Tempo50GapPotential.find_all_tempo_50_gaps(gdf = streets_gdf)


#######################################
# Annotate features as relevant for potential
#######################################

zebra_gdf["potential_candidate"] = zebra_gdf["osm_id"].isin(potential_results["zebra"].opt_source_ids)

for key, bdg_data in building_data.items():
    corresponding_result = potential_results[key]
    bdg_data["potential_candidate"] = bdg_data["osm_id"].isin(corresponding_result.opt_source_ids)

#######################################
# Create street dataset w. Annotations
#######################################

streets_updated_gdf = SpeedAnnotationUpdater.annotate_gdf_with_potential_type(streets_gdf, potential_results, building_configs)


#######################################
# File / Print / Map Output
#######################################

streets_with_potential = streets_updated_gdf[
    streets_updated_gdf["feature_type"].str.startswith("T30_Potenzial", na=False)
]

# Print if required
PrintOutput.print_streets(streets_with_potential)

GeoJsonCreator.create_geojson_layer_files(folder_name = area_under_creation, streets_with_potential = streets_with_potential,
                                          streets_w_limit_gdf = streets_gdf, zebra_gdf = zebra_gdf, building_data = building_data)


# Plotting
StreetPlot.plot_map(streets_gdf = streets_updated_gdf, zebra_gdf = zebra_gdf, bdg_data = building_data)

plt.show()
