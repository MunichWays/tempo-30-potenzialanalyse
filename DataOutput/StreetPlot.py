import matplotlib.pyplot as plt

SPEED_COLOR_MAP = {
    "10": "#90EE90",              # lightgreen
    "20" : "#90EE90",
    "30": "#198119",               # green
    # Tempo 30 Zonendaten nicht existent in München # "30_Zone": "#1f9e89",         # teal
    "Zeitweise_30" : "#CBFD07",
    "50": "lightblue", # "#fca456",       
    "60": "darkblue",
    "Keine_Daten" : "#dddddd", 
    "T30_Potenzial_Zebrastreifen" : "purple",
    "T30_Potenzial_Luecke" : "darkred", 
    "T30_Potenzial_Schule" : "orange",
    "T30_Potenzial_Krankenhaus" : "red"
    #"50_StdInnerorts": "#d62728"  # red
}

from shapely.geometry import Point, LineString, MultiLineString
import geopandas as gpd

ZEBRASTREIFEN_FARBE = "black" # violett
BILDUNGSEINRICHTUNG_FARBE = "violet"
KRANKENHAUS_FARBE = "red"

class StreetPlot:

    # Debug only
    @staticmethod 
    def _extract_start_end_points(gdf):
        """
        Returns two GeoDataFrames:
        - start points
        - end points
        """
        starts = []
        ends = []

        for _, row in gdf.iterrows():
            geom = row.geometry

            if isinstance(geom, LineString):
                coords = list(geom.coords)
                starts.append(Point(coords[0]))
                ends.append(Point(coords[-1]))

            elif isinstance(geom, MultiLineString):
                # use first and last sub-geometry
                first = list(geom.geoms[0].coords)
                last = list(geom.geoms[-1].coords)
                starts.append(Point(first[0]))
                ends.append(Point(last[-1]))

        return (
            gpd.GeoDataFrame(geometry=starts, crs=gdf.crs),
            gpd.GeoDataFrame(geometry=ends, crs=gdf.crs),
        )

    def plot_debug_points(ax, streets_gdf):
           # -------------------------------------------------
        # DEBUG: plot start / end points of street segments
        # -------------------------------------------------
        start_gdf, end_gdf = StreetPlot._extract_start_end_points(streets_gdf)

        start_gdf.plot(
            ax=ax,
            color="limegreen",
            marker="o",
            markersize=25,
            label="Start point",
            zorder=5,
        )

        end_gdf.plot(
            ax=ax,
            color="red",
            marker="x",
            markersize=30,
            label="End point",
            zorder=5,
        )

    def plot_map(streets_gdf, zebra_gdf = None, educational_gdf = None, krankenhaus_gdf = None, figsize=(9, 9), debug_endpoints: bool = False):
        streets_gdf = streets_gdf.copy()

        streets_gdf.loc[streets_gdf["conditional_speed"] == "30", "maxspeed_class"] = "Zeitweise_30"

        # assign colors, fallback = gray
        streets_gdf["plot_color"] = streets_gdf["maxspeed_class"].map(SPEED_COLOR_MAP).fillna("#7f7f7f")

        fig, ax = plt.subplots(figsize=figsize)

        # plot streets
        streets_gdf.plot(
            ax=ax,
            color=streets_gdf["plot_color"],
            linewidth=1.5
        )
           # -------------------------------------------------
        # DEBUG: plot start / end points of street segments
        # -------------------------------------------------
        if debug_endpoints:
            StreetPlot.plot_debug_points(ax, streets_gdf)

        # plot zebra crossings if provided
        if zebra_gdf is not None and len(zebra_gdf) > 0:
            zebra_gdf.plot(
                ax=ax,
                color = ZEBRASTREIFEN_FARBE,
                marker="x",
                markersize=30,
                label="Zebrastreifen"
            )
            
        if educational_gdf is not None and len(educational_gdf) > 0:
            educational_gdf.plot(
                ax=ax,
                color = BILDUNGSEINRICHTUNG_FARBE,
                marker="o",
                markersize=15,
                label="Bildungseinrichtung"
            )

        if krankenhaus_gdf is not None and len(krankenhaus_gdf) > 0:
            krankenhaus_gdf.plot(
                ax=ax,
                color = KRANKENHAUS_FARBE,
                marker="o",
                markersize=15,
                label="Bildungseinrichtung"
            )
            

        # build street legend manually (categorical)
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color=color, lw=3, label=label)
            for label, color in SPEED_COLOR_MAP.items()
        ]

        # add zebra legend item
        if zebra_gdf is not None and len(zebra_gdf) > 0:
            legend_elements.append(
                Line2D([0], [0], color= ZEBRASTREIFEN_FARBE, lw=0, marker="x", markersize=10, label="Zebrastreifen")
            )

        if educational_gdf is not None and len(educational_gdf) > 0:
            legend_elements.append(
                Line2D([0], [0], color= BILDUNGSEINRICHTUNG_FARBE, lw=0, marker="o", markersize=10, label="Bildungseinrichtung")
            )

        if krankenhaus_gdf is not None and len(krankenhaus_gdf) > 0:
            legend_elements.append(
                Line2D([0], [0], color= KRANKENHAUS_FARBE, lw=0, marker="o", markersize=10, label="Krankenhaus")
            )

        ax.legend(
            handles=legend_elements,
            title="Speed limit",
            loc="upper right"
        )

        ax.set_axis_off()
        ax.set_title("Straßenabschnitte nach Tempolimit")