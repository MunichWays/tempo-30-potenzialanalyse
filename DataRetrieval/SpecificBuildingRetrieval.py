# Define your configuration dictionary
from DataRetrieval.BuildingRetrieval import BuildingRetrieval

class SpecificBuildingRetrieval:
    def retrieve_building_data(bbox, building_configs):


        # Store results here
        building_data = {}

        # Loop through the configs
        for datatype, config in building_configs.items():
            retrieval = BuildingRetrieval(
                datatype=datatype,
                tags=config["tags"],
                name_filter_regex=config.get("regex", None)
            )
            
            gdf = retrieval.fetch(bbox)
            building_data[datatype] = gdf
            
            if gdf is not None:
                print(f"\n=== {datatype} ===")
                print("Names:")
                print(gdf["name"].head())
                print(f"Total {datatype} found: {len(gdf)}")
            else:
                print(f"Found no data for {datatype}")
        
        return building_data
