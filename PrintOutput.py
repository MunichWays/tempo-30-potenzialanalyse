
from geopandas import gpd

class PrintOutput:
    def print_streets(streets_with_potential):
        streets_with_potential = streets_with_potential.to_crs("EPSG:25832").copy()  # proper length calc
        streets_with_potential["length_m"] = streets_with_potential.geometry.length
        streets_with_potential = streets_with_potential.drop(["highway", "maxspeed_tag", "zone_maxspeed_tag"], axis = 1)

        print("Printing segments with T30 potential")
        #for index in range(0, len(streets_with_potential)):
        #    print(streets_with_potential.iloc[index])
        print("len", len(streets_with_potential))
        print(streets_with_potential)


        merged_gdf = (
            streets_with_potential
            .dissolve(by="name", as_index=False, aggfunc={
                "length_m": "sum",
                "osm_id": lambda x: list(x)
            })
        )

        merged_gdf_filter_short = merged_gdf.loc[merged_gdf["length_m"] > 20]

        print("Printing merged segments with T30 potential with more than 20 m")
        #for index in range(0, len(merged_gdf)):
        #    print(merged_gdf.iloc[index])
        print(merged_gdf_filter_short)