
from RegionDefinition import RegionDefinition

class OverpassQueryCreation:
    def build_query(
        retrieval,
        region_definition: RegionDefinition,
        filters: str,
        output: str = "out body;\n>;\nout skel qt;",
    ) -> str:
        setup, region_filter = OverpassQueryCreation.build_region_filter(region_definition)

        return f"""[out:json][timeout:{retrieval.timeout}];
        {setup}
        (
        {filters.format(region=region_filter)}
        );
        {output}
        """


    def build_boundary_relation_selector(region_definition: RegionDefinition) -> str:
        """Overpass statement selecting the boundary relation used as search area."""
        if region_definition.osm_relation_id is not None:
            return f"rel({region_definition.osm_relation_id});"
        elif region_definition.key == "münchen": # Special handling, will be removed later!
            return 'rel["boundary"="administrative"][admin_level=6]["name"="München"];'

        raise ValueError("RegionDefinition has no boundary relation")


    def build_region_filter(
        region_definition: RegionDefinition,
    ) -> tuple[str, str]:
        if region_definition.osm_relation_id is not None:
            setup = (
                f"rel({region_definition.osm_relation_id});\n"
                "map_to_area->.searchArea;"
            )
            return setup, "(area.searchArea)"

        elif region_definition.bbox is not None:
            south, west, north, east = region_definition.bbox
            return "", f"({south},{west},{north},{east})"
        elif region_definition.key == "münchen": # Special handling, will be removed later!
            setup = (
                'area[admin_level=6]["name"="München"]->.searchArea;'
            )
            return setup, "(area.searchArea)"

        raise ValueError("RegionDefinition needs a bbox or an OSM relation ID")
