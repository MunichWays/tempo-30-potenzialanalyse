from DataRetrieval.SegmentRetrieval import SegmentRetrieval
from DataRetrieval.ZebraCrossingRetrieval import ZebraCrossingRetrieval
from DataRetrieval.EducationalBdgRetrieval import EducationalBuildingRetrieval

import matplotlib.pyplot as plt

from StreetPlot import StreetPlot
from ZebraPotential import ZebraPotential
from EducationBdgPotential import EducationBdgPotential
from GapPotential import Tempo50GapPotential
from SpeedAnnotationUpdater import SpeedAnnotationUpdater
from BoundingBoxStorage import BoundingBoxStorage
from geojson_creation import GeoJsonCreator
from PotentialCalculationResult import PotentialCalculationResult
from PrintOutput import PrintOutput

used_bbox = BoundingBoxStorage.bbox_isarvorstadt # "München"
#######################################
# Phase 1: Daten holen und darstellen
#######################################

########
# Straßen
sr = SegmentRetrieval()
streets_gdf = sr.fetch_as_geodataframe(used_bbox)

zebra_retrieval = ZebraCrossingRetrieval(timeout=120)
zebra_gdf = zebra_retrieval.fetch_zebra_crossings(used_bbox)

StreetPlot.plot_map(streets_gdf = streets_gdf, zebra_gdf = zebra_gdf)

school_retrieval = EducationalBuildingRetrieval()
educational_bdg_gdf = school_retrieval.fetch_education_bdg_with_name(used_bbox)

if educational_bdg_gdf is not None:
    print("Keys", educational_bdg_gdf.keys())
    print(educational_bdg_gdf)
    print(f"Total schools found: {len(educational_bdg_gdf)}")

#######################################
# Phase 2: StVO Regeln prüfen
#######################################

# Zebra crossings
print("Identifying Zebra Crossings ...")
zebra_potential_result : PotentialCalculationResult = ZebraPotential.find_tempo50_segments_near_zebra(streets_gdf = streets_gdf, zebras_gdf = zebra_gdf, search_distance_m = 15)
streets_updated_gdf = SpeedAnnotationUpdater.update_speed_annotation(streets_gdf = streets_gdf, osm_ids_to_annotate = zebra_potential_result.street_ids, new_val = "T30_Potenzial_Zebrastreifen")
zebra_gdf["potential_candidate"] = zebra_gdf["osm_id"].isin(zebra_potential_result.opt_source_ids)

# Educational buildings
print("Identifiying Street near schools")
educational_potential_result : PotentialCalculationResult = EducationBdgPotential.find_tempo50_segments_near_educ_bdgs(streets_gdf = streets_gdf, educational_bdg_gdf = educational_bdg_gdf, search_distance_m = 50)
streets_updated_gdf = SpeedAnnotationUpdater.update_speed_annotation(streets_gdf = streets_updated_gdf, osm_ids_to_annotate = educational_potential_result.street_ids, new_val = "T30_Potenzial_Schule")
educational_bdg_gdf["potential_candidate"] = educational_bdg_gdf["osm_id"].isin(educational_potential_result.opt_source_ids)

# Lückenschluss
print("Identifying Gaps ...")
gap_potential_result : PotentialCalculationResult= Tempo50GapPotential.find_all_tempo_50_gaps(gdf = streets_gdf)
streets_updated_gdf = SpeedAnnotationUpdater.update_speed_annotation(streets_gdf = streets_updated_gdf, osm_ids_to_annotate = gap_potential_result.street_ids, new_val = "T30_Potenzial_Luecke")

# print only the maxspeed_

streets_with_potential = streets_updated_gdf.loc[streets_updated_gdf["maxspeed_class"].isin(["T30_Potenzial_Zebrastreifen", "T30_Potenzial_Luecke", "T30_Potenzial_Schule"])]

# Print if required
PrintOutput.print_streets(streets_with_potential)

other_streets = streets_updated_gdf.loc[~streets_updated_gdf["maxspeed_class"].isin(["T30_Potenzial_Zebrastreifen", "T30_Potenzial_Luecke", "T30_Potenzial_Schule"])]

# TODO: Strip down zebra only for relevant ones
GeoJsonCreator.create_geojson_layer_files(folder_name = "munich_half_final", streets_with_potential = streets_with_potential, streets_w_limit_gdf = streets_gdf, zebra_gdf = zebra_gdf, educational_bdg_gdf = educational_bdg_gdf)



# Plotting

StreetPlot.plot_map(streets_gdf = streets_updated_gdf, zebra_gdf = zebra_gdf, educational_gdf = educational_bdg_gdf)

plt.show()
