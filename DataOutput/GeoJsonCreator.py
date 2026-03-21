
import geopandas as gpd
import pandas as pd

from pathlib import Path

class GeoJsonCreator:
    def create_geojson_layer_files(folder_name, streets_with_potential : gpd.GeoDataFrame, streets_w_limit_gdf, zebra_gdf, building_data):
        export_dir = Path("./") / "GEOJSON_EXPORT"  / folder_name
        export_dir.mkdir(parents=True, exist_ok=True)
         # --- Streets with potential only

        # Add visualization category
        streets_with_potential
        export_data_dict = {}

        export_data_dict["zebra"] = zebra_gdf.copy()
        export_data_dict["potential_streets"] = streets_with_potential.copy()
        export_data_dict["streets_and_limit"] = streets_w_limit_gdf.copy()

        for key, data in building_data.items():
            export_data_dict[key] = data.copy()


        export_data_dict["potential_streets"]["feature_type"] = export_data_dict["potential_streets"]["maxspeed_class"].map({
            "T30_Potenzial_Zebrastreifen": "zebra_potential",
            "T30_Potenzial_Schule": "school_potential",
            "T30_Potenzial_Luecke": "gap_potential",
            "T30_Potenzial_Krankenhaus" : "hospital_potential",
            "T30_Potenzial_Altenheim": "elderly_home_potential"
        })

        # Bundle speed limits
        mapping = {
            "10": "T30-",
            "20": "T30-",
            "30": "T30-",
            "50": "T50+",
            "60": "T50+"
        }

        export_data_dict["streets_and_limit"]["maxspeed_class"] =  export_data_dict["streets_and_limit"]["maxspeed_class"].replace(mapping)

        # Override when conditional speed is 30
        export_data_dict["streets_and_limit"].loc[export_data_dict["streets_and_limit"]["conditional_speed"] == "30", "maxspeed_class"] = "Conditional-T30"
        
        # Convert to WGS84
        for entry in export_data_dict.keys():
            export_data_dict[entry] = export_data_dict[entry].to_crs("EPSG:4326")

        # Reduce unnecessary columns
        export_data_dict["potential_streets"] = export_data_dict["potential_streets"][[
            "osm_id",
            "name",
            "feature_type",
            "geometry"
        ]]

        export_data_dict["streets_and_limit"] = export_data_dict["streets_and_limit"][[
            "osm_id",
            "name",
            "maxspeed_class",
            "conditional_speed",
            "cond_speed_days",
            "cond_speed_starttime",
            "cond_speed_endtime",
            "cond_speed_special",
            "geometry"
        ]]

        export_data_dict["zebra"] = export_data_dict["zebra"][[
            "geometry",
            "potential_candidate",
            "street"
        ]]

        for building_type in building_data.keys():
            export_data_dict[building_type] = export_data_dict[building_type][[
                "name",
                "geometry",
                "potential_candidate",
                "street",
                "housenumber",
                "website",
                "operator"
            ]]

        # Export

        for entry in export_data_dict.keys():
            filename = entry + ".geojson"
            output_file = export_dir / filename
            export_data_dict[entry].to_file(output_file, driver="GeoJSON")

            print(f"\n✅ GeoJSON successfully written to: {output_file}")
            print(f"Total features exported: {len(export_data_dict[entry])}")