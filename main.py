import matplotlib.pyplot as plt

from DataRetrieval.SegmentRetrieval import SegmentRetrieval
from DataRetrieval.ZebraCrossingRetrieval import ZebraCrossingRetrieval
from DataRetrieval.BuildingRetrieval import BuildingRetrieval

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

sr = SegmentRetrieval()
streets_gdf = sr.fetch_as_geodataframe(used_bbox)

zebra_retrieval = ZebraCrossingRetrieval(timeout=120)
zebra_gdf = zebra_retrieval.fetch_zebra_crossings(used_bbox)

StreetPlot.plot_map(streets_gdf = streets_gdf, zebra_gdf = zebra_gdf)

school_retrieval = BuildingRetrieval(datatype = "educational_buildings", amenities = ["school, kindergarten"], name_filter_regex = r"(kindergarten|grundschule|hauptschule|realschule|mittelschule|gymnasium|gesamtschule)")
educational_bdg_gdf = school_retrieval.fetch(used_bbox)

if educational_bdg_gdf is not None:
    print("Keys", educational_bdg_gdf.keys())
    print(educational_bdg_gdf)
    print(f"Total schools found: {len(educational_bdg_gdf)}")

#######################################
# Identify potential
#######################################

# Zebra crossings
print("Identifying Zebra Crossings ...")
zebra_potential_result : PotentialCalculationResult = ZebraPotential.find_tempo50_segments_near_zebra(streets_gdf = streets_gdf, zebras_gdf = zebra_gdf, search_distance_m = 15)
print("Identifiying Street near schools")
educational_potential_result : PotentialCalculationResult = ProximityPotential.find_tempo50_segments_near_features(streets_gdf = streets_gdf, features_gdf = educational_bdg_gdf, search_distance_m = 50)
print("Identifying Gaps ...")
gap_potential_result : PotentialCalculationResult= Tempo50GapPotential.find_all_tempo_50_gaps(gdf = streets_gdf)

#######################################
# Create street dataset w. Annotations
#######################################
streets_updated_gdf = SpeedAnnotationUpdater.update_speed_annotation(streets_gdf = streets_gdf, osm_ids_to_annotate = zebra_potential_result.street_ids, new_val = "T30_Potenzial_Zebrastreifen")
streets_updated_gdf = SpeedAnnotationUpdater.update_speed_annotation(streets_gdf = streets_updated_gdf, osm_ids_to_annotate = educational_potential_result.street_ids, new_val = "T30_Potenzial_Schule")
streets_updated_gdf = SpeedAnnotationUpdater.update_speed_annotation(streets_gdf = streets_updated_gdf, osm_ids_to_annotate = gap_potential_result.street_ids, new_val = "T30_Potenzial_Luecke")

#######################################
# Annotate sources
#######################################

zebra_gdf["potential_candidate"] = zebra_gdf["osm_id"].isin(zebra_potential_result.opt_source_ids)
educational_bdg_gdf["potential_candidate"] = educational_bdg_gdf["osm_id"].isin(educational_potential_result.opt_source_ids)

#######################################
# File / Print / Map Output
#######################################

streets_with_potential = streets_updated_gdf.loc[streets_updated_gdf["maxspeed_class"].isin(["T30_Potenzial_Zebrastreifen", "T30_Potenzial_Luecke", "T30_Potenzial_Schule"])]

# Print if required
PrintOutput.print_streets(streets_with_potential)

GeoJsonCreator.create_geojson_layer_files(folder_name = area_under_creation, streets_with_potential = streets_with_potential, streets_w_limit_gdf = streets_gdf, zebra_gdf = zebra_gdf, educational_bdg_gdf = educational_bdg_gdf)



# Plotting

StreetPlot.plot_map(streets_gdf = streets_updated_gdf, zebra_gdf = zebra_gdf, educational_gdf = educational_bdg_gdf)

plt.show()
