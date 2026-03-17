


class BoundingBoxStorage:
    bbox_munich = (
        48.061,   # south
        11.360,   # west
        48.248,   # north
        11.722    # east
    )

    bbox_half_randompart_of_munich = (
        (48.061 + 48.118 ) / 2,  # south
        (11.360 + 11.555 ) / 2,  # west
        (48.248 + 48.145 ) / 2,  # north
        (11.722 + 11.590 ) / 2   # east
    )

    bbox_randompart_of_munich = (
        (48.061 + 48.118 * 2) / 3,  # south
        (11.360 + 11.555 * 2) / 3,  # west
        (48.248 + 48.145 * 2) / 3,  # north
        (11.722 + 11.590 *2) / 3   # east
    )

    bbox_isarvorstadt = (
        48.118,  # south
        11.555,  # west
        48.145,  # north
        11.590   # east
    )

    bbox_custom = (
        48.121986,
        11.548176,
        48.139688, 
        11.583366
    )

    bbox_custom_mini = (
        48.129664,
        11.553154,
        48.134962,
        11.558647
    )

    bbox_custom_mini_landwehr = (
        48.129,
        11.546,
        48.140,
        11.559
    )

    bbox_regensburg = (
        48.980,   # south
        12.040,   # west
        49.070,   # north
        12.160    # east
    )

    bbox_nuernberg = (
        49.380,   # south
        11.000,   # west
        49.520,   # north
        11.160    # east
    )