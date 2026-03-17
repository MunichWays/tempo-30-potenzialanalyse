
class BoundingBoxStorage:
    BBOXES = {
        "munich": (
            48.061,   # south
            11.360,   # west
            48.248,   # north
            11.722    # east
        ),

        "half_of_munich": (
            (48.061 + 48.118) / 2,
            (11.360 + 11.555) / 2,
            (48.248 + 48.145) / 2,
            (11.722 + 11.590) / 2
        ),

        "one_third_of_munich": (
            (48.061 + 48.118 * 2) / 3,
            (11.360 + 11.555 * 2) / 3,
            (48.248 + 48.145 * 2) / 3,
            (11.722 + 11.590 * 2) / 3
        ),

        "isarvorstadt": (
            48.118,
            11.555,
            48.145,
            11.590
        ),

        "custom_mini_landwehr": (
            48.129,
            11.546,
            48.140,
            11.559
        ),

        "regensburg": (
            48.980,
            12.040,
            49.070,
            12.160
        ),

        "nuernberg": (
            49.380,
            11.000,
            49.520,
            11.160
        ),
    }

    @classmethod
    def get(cls, name: str):
        return cls.BBOXES.get(name)