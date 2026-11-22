from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt

from DataOutput.GeoJsonCreator import GeoJsonCreator
from DataOutput.PrintOutput import PrintOutput
from DataOutput.StreetPlot import StreetPlot
from DataRetrieval.SegmentRetrieval import SegmentRetrieval
from DataRetrieval.SpecificBuildingRetrieval import SpecificBuildingRetrieval
from DataRetrieval.ZebraCrossingRetrieval import ZebraCrossingRetrieval
from PotentialCalculation.GapPotential import Tempo50GapPotential
from PotentialCalculation.PotentialCalculationResult import PotentialCalculationResult
from PotentialCalculation.ProximityPotential import ProximityPotential
from PotentialCalculation.ZebraPotential import ZebraPotential
from RegionDefinition import RegionDefinition
from RegionStorage import RegionStorage
from SpeedAnnotationUpdater import SpeedAnnotationUpdater


BUILDING_CONFIGS = {
    "educational_buildings": {
        "tags": {"amenity": ["school", "kindergarten"]},
        "regex": r"(kindergarten|grundschule|hauptschule|realschule|mittelschule|gymnasium|gesamtschule|sonderpädagogisches|berufschul|berufoberschule|montessori|japanische|simmernschule)",
        "speed_annotation": "T30_Potenzial_Schule"
    },
    "hospitals": {
        "tags": {"amenity": ["hospital"]},
        "regex": r"(krankenhaus|klinikum)",
        "speed_annotation": "T30_Potenzial_Krankenhaus"
    },
    "elderly_homes": {
        "tags": {
            "amenity": ["nursing_home", "retirement_home", "care_home"],
            "social_facility": ["nursing_home", "assisted_living"]
        },
        "regex": r"(pflegeheim|pflege-heim|senior|alten|residenz|stift)",
        "speed_annotation": "T30_Potenzial_Altenheim"
    },
    "playgrounds": {
        "tags": {
            "amenity": ["playground"],
            "leisure": ["playground"]
        },
        "regex": None,
        "speed_annotation": "T30_Potenzial_Spielplatz"
    },
    "disability_facilities": {
        "tags": {
            "amenity": ["social_facility", "clinic", "craft"],
            "social_facility": [
                "assisted_living",
                "group_home",
                "workshop",
                "rehabilitation",
                "day_care"
            ],
            "healthcare": ["rehabilitation", "physiotherapy"]
        },
        "regex": r"(behinderung|behindert|lebenshilfe|inklusion|förderstätte|werkstatt|werkstätten)",
        "speed_annotation": "T30_Potenzial_Behinderteneinrichtung"
    }
}


@dataclass
class RetrievedData:
    streets: gpd.GeoDataFrame
    zebras: gpd.GeoDataFrame
    buildings: dict[str, gpd.GeoDataFrame]


@dataclass
class AnnotatedData:
    streets: gpd.GeoDataFrame
    potential_streets: gpd.GeoDataFrame


def retrieve_data(region: RegionDefinition) -> RetrievedData:
    """Fetch streets, crossings, and configured building features."""
    streets = SegmentRetrieval().fetch_as_geodataframe(region_definition=region)
    zebras = ZebraCrossingRetrieval(timeout=120).fetch_zebra_crossings(
        region_definition=region
    )
    buildings = SpecificBuildingRetrieval.retrieve_building_data(
        region_definition=region,
        building_configs=BUILDING_CONFIGS
    )
    return RetrievedData(streets=streets, zebras=zebras, buildings=buildings)


def calculate_potential(data: RetrievedData) -> dict[str, PotentialCalculationResult]:
    """Run each potential calculation against the retrieved GeoDataFrames."""
    results = {
        "zebra": ZebraPotential.find_tempo50_segments_near_zebra(
            streets_gdf=data.streets,
            zebras_gdf=data.zebras,
            search_distance_m=2
        )
    }

    for key, features in data.buildings.items():
        results[key] = ProximityPotential.find_tempo50_segments_near_features(
            streets_gdf=data.streets,
            features_gdf=features,
            search_distance_m=20
        )

    results["gap"] = Tempo50GapPotential.find_all_tempo_50_gaps(
        gdf=data.streets
    )
    return results


def annotate_potential(
    data: RetrievedData,
    results: dict[str, PotentialCalculationResult]
) -> AnnotatedData:
    """Mark candidate source features and annotate streets with potential types."""
    data.zebras["potential_candidate"] = data.zebras["osm_id"].isin(
        results["zebra"].opt_source_ids
    )

    for key, features in data.buildings.items():
        features["potential_candidate"] = features["osm_id"].isin(
            results[key].opt_source_ids
        )

    streets = SpeedAnnotationUpdater.annotate_gdf_with_potential_type(
        data.streets,
        results,
        BUILDING_CONFIGS
    )
    potential_streets = streets[
        streets["feature_type"].str.startswith("T30_Potenzial", na=False)
    ]
    return AnnotatedData(streets=streets, potential_streets=potential_streets)


def export_results(
    region_name: str,
    data: RetrievedData,
    annotated: AnnotatedData,
    *,
    export_root: Path = Path("./GEOJSON_EXPORT"),
    render_plots: bool = True,
    show_plot: bool = True
) -> None:
    """Print and export calculated results, optionally rendering the maps."""
    PrintOutput.print_streets(annotated.potential_streets)
    GeoJsonCreator.create_geojson_layer_files(
        folder_name=region_name,
        streets_with_potential=annotated.potential_streets,
        streets_w_limit_gdf=data.streets,
        zebra_gdf=data.zebras,
        building_data=data.buildings,
        output_root=export_root
    )

    if render_plots:
        StreetPlot.plot_map(
            streets_gdf=annotated.streets,
            zebra_gdf=data.zebras,
            bdg_data=data.buildings
        )
        if show_plot:
            plt.show()


def run_potential_calculation(
    region_name: str = "München",
    *,
    export_root: Path = Path("./GEOJSON_EXPORT"),
    render_plots: bool = True,
    show_plot: bool = True
) -> dict[str, PotentialCalculationResult]:
    """Orchestrate retrieval, calculation, annotation, and export stages."""
    print(f"Calculating potential for: {region_name}")
    region = RegionStorage.get(region_name)

    print("Retrieving input data ...")
    data = retrieve_data(region)

    if render_plots:
        StreetPlot.plot_map(streets_gdf=data.streets, zebra_gdf=data.zebras)

    print("Calculating potential ...")
    results = calculate_potential(data)

    print("Annotating potential ...")
    annotated = annotate_potential(data, results)

    print("Exporting results ...")
    export_results(
        region_name,
        data,
        annotated,
        export_root=export_root,
        render_plots=render_plots,
        show_plot=show_plot
    )
    return results
