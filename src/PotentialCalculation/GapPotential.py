import math
import geopandas as gpd
from shapely.geometry import Point
from typing import List
import pandas as pd
from pyproj import Transformer
from tqdm import tqdm

from PotentialCalculation.PotentialCalculationResult import PotentialCalculationResult

# create once (cheap but still better than recreating every call)
_TRANSFORMER_3857_TO_4326 = Transformer.from_crs(
    "EPSG:3857",
    "EPSG:4326",
    always_xy=True,
)

def point_to_lonlat(pt):
    lon, lat = _TRANSFORMER_3857_TO_4326.transform(pt.x, pt.y)
    return lon, lat


DEBUG_STREET = "landwehrstraße"  # lowercase, None = off
DEBUG_ON = False

def dbg(seg, msg):
    #pass
    if DEBUG_ON and str(seg.get("name", "")).lower() == DEBUG_STREET:
        print(msg)


class Tempo50GapPotential:

    # -----------------------------------------------------
    # Vorbereitung
    # -----------------------------------------------------
    @staticmethod
    def prepare_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        gdf = gdf.to_crs("EPSG:25832").copy()  # proper length calc

        gdf["length_m"] = gdf.geometry.length
        gdf = gdf.to_crs("EPSG:3857").copy() # proper angle calc

        gdf["start_pt"] = gdf.geometry.apply(lambda g: Point(g.coords[0]))
        gdf["end_pt"] = gdf.geometry.apply(lambda g: Point(g.coords[-1]))
        
        gdf[["angle_start", "angle_end"]] = gdf.geometry.apply(
            lambda g: pd.Series(Tempo50GapPotential.calculate_segment_end_angles(g))
        )

        return gdf

    # -----------------------------------------------------
    # Winkelberechnung
    # -----------------------------------------------------
    @staticmethod
    def calculate_segment_end_angles(line) -> tuple[float, float]:
        """
        Returns compass bearings (0° = North, clockwise) for both ends of a LineString:
        - angle_start: from first point to second point
        - angle_end:   from last point to second-last point
        """

        coords = list(line.coords)

        if len(coords) < 2:
            raise ValueError("LineString must have at least two points")

        # --- start angle: first -> second
        x1, y1 = coords[0]
        x2, y2 = coords[1]

        dx_start = x2 - x1
        dy_start = y2 - y1
        angle_start = math.degrees(math.atan2(dx_start, dy_start)) % 360

        # --- end angle: last -> second-last
        xn, yn = coords[-1]
        xp, yp = coords[-2]

        dx_end = xp - xn
        dy_end = yp - yn
        angle_end = math.degrees(math.atan2(dx_end, dy_end)) % 360

        return angle_start, angle_end


    @staticmethod
    def axis_angle_diff(a1: float, a2: float) -> float:
        """
        Smallest difference between two compass bearings,
        ignoring opposite direction (i.e. 0° == 180°).
        """
        diff = abs(a1 - a2) % 360
        diff = min(diff, 360 - diff)
        return min(diff, abs(diff - 180))

    # -----------------------------------------------------
    # Fall 1:
    # Enden grenzen ausschließlich an Tempo 30
    # -----------------------------------------------------
    @staticmethod
    def check_if_segment_ends_only_touch_tempo_30(seg, gdf: gpd.GeoDataFrame) -> bool:
        for pt in (seg.start_pt, seg.end_pt):
            touching = gdf[
                (gdf.geometry.touches(pt)) &
                (gdf.index != seg.name)
            ]

            if touching.empty:
                return False

            if not touching["maxspeed_class"].isin({"30", "30_Zone"}).all():
                return False

        return True

    # -----------------------------------------------------
    # Fall 2:
    # In beide Richtungen weiterfahren → Tempo 30
    # -----------------------------------------------------
    @staticmethod
    def check_if_straight_line_direction_for_both_ends_has_tempo_30(
        seg,
        gdf,
        max_total_length: float = 500,
        min_total_length: float = 30
    ) -> bool:

        base_angles = {
            "Standard": seg.angle_start,
            "Reverse": seg.angle_end,
        }

        base_points = {
            "Standard": seg.start_pt,
            "Reverse": seg.end_pt,
        }

        lengths = {}

        for dir in ["Standard", "Reverse"]:
            used_point = base_points[dir]
            base_angle = base_angles[dir]

            if Tempo50GapPotential.all_directions_tempo30(seg, used_point, gdf):
                lengths[dir] = 0.0
                continue

            ok, length = Tempo50GapPotential.follow_straight_chain(seg, used_point, base_angle, gdf)
            if not ok:
                return False

            lengths[dir] = length

        total_corridor_length = lengths["Standard"] + lengths["Reverse"] + seg.length_m
        dbg(seg, f'{seg.osm_id} std length: {lengths["Standard"]}, reverse {lengths["Reverse"]}, seg {seg.length_m}')
        
        if total_corridor_length <= max_total_length:
            if total_corridor_length >= min_total_length:
                return True

        return False
       
    
    def all_directions_tempo30(seg, point, gdf):
        """
        If every connected segment at this point is Tempo-30, return True.
        """
        touching = gdf[(gdf.geometry.touches(point)) & (gdf.index != seg.name)]
        if touching.empty:
            return False
        
    
        return (touching["maxspeed_class"].isin({"30", "30_Zone"}) | (touching["conditional_speed"] == "30")).all()


    def follow_straight_chain(start_seg, start_point, start_angle, gdf, max_depth = 10, angle_tol = 30):

        current_seg = start_seg
        current_point = start_point
        current_angle = start_angle

        visited = {start_seg.osm_id}
        depth = 0
        total_length = 0.0  # ⬅️ NUR fremde Segmente
        dbg(start_seg,f"\n🔎Start to follow segment {current_seg.osm_id} ({current_seg.name})")

        gdf_spatial_index = gdf.sindex
        while depth < max_depth:
            depth += 1

            # Performance increase through filtering via spacial index
            possible = list(gdf_spatial_index.intersection(current_point.bounds))
            candidates = gdf.iloc[possible]

            candidates = candidates[
                (candidates.geometry.touches(current_point)) &
                (candidates.index != current_seg.name)
            ]

            if candidates.empty:
                dbg(start_seg, "❌ No candidates")
                return False, total_length

            best_cand = None
            best_diff = 999

            for _, cand in candidates.iterrows():
                if cand.start_pt.equals(current_point):
                    cand_angle = cand.angle_start
                elif cand.end_pt.equals(current_point):
                    cand_angle = cand.angle_end
                else:
                    continue

                diff = Tempo50GapPotential.axis_angle_diff(current_angle, cand_angle)
                if diff < best_diff:
                    best_diff = diff
                    best_cand = cand

            if best_cand is None:
                dbg(start_seg, "❌ No candidate passed endpoint + angle checks")
                return False, total_length

            dbg(start_seg,
                f"✅ Best candidate: osm_id={best_cand.osm_id}, "
                f"name={best_cand.name}, "
                f"angle_diff={best_diff:.1f}°, "
                f"class={best_cand.maxspeed_class}"
            )

            if best_cand.osm_id in visited:
                dbg(start_seg, "⛔ Rejected: loop detected")
                return False, total_length

            if best_diff > angle_tol:
                dbg(start_seg, "⛔ Rejected: angle to steep")
                return False, total_length

            # ➜ Erfolg: Tempo 30 erreicht
            if best_cand.maxspeed_class in {"30", "30_Zone"} or best_cand.conditional_speed == "30":
                dbg(start_seg, "✅ Accepted: Found end candidate")
                return True, total_length

            visited.add(best_cand.osm_id)
            total_length += best_cand.length_m

            # weiterlaufen
            if best_cand.start_pt.equals(current_point):
                current_point = best_cand.end_pt
                current_angle = best_cand.angle_end
            else:
                current_point = best_cand.start_pt
                current_angle = best_cand.angle_start

            current_seg = best_cand

        dbg(start_seg,"⛔ Rejected: Reeched end of search")
        return False, total_length


    # -----------------------------------------------------
    # Hauptfunktion
    # -----------------------------------------------------
    @staticmethod
    def find_all_tempo_50_gaps(gdf: gpd.GeoDataFrame) -> List[int]:
        gdf = Tempo50GapPotential.prepare_gdf(gdf)

        classified_permanent_tempo50_or_60 = gdf[
            (gdf["maxspeed_class"].isin({"50", "60"})) &
            (gdf["length_m"] < 500) & 
            (gdf["conditional_speed"] != "30")
        ]

        result = []

        for _, seg in tqdm(classified_permanent_tempo50_or_60.iterrows(),
                        total=len(classified_permanent_tempo50_or_60),
                        desc="Checking segments"):
            
            if Tempo50GapPotential.check_if_straight_line_direction_for_both_ends_has_tempo_30(seg, gdf):
                dbg(seg, "Found landwehrst. segment with potential!")
                result.append(seg.osm_id)

        return PotentialCalculationResult(street_ids = result)