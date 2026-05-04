
building_configs = {
    "educational_buildings": {
        "tags": {
            "amenity": ["school", "kindergarten"]
        },
        "regex": r"(kindergarten|grundschule|hauptschule|realschule|mittelschule|gymnasium|gesamtschule|sonderpädagogisches|berufschul|berufoberschule|montessori|japanische|simmernschule)",
        "speed_annotation" : "T30_Potenzial_Schule"
    },
    "hospitals": {
        "tags": {
            "amenity" :  ["hospital"]
        },
        "regex": r"(krankenhaus|klinikum)",
        "speed_annotation" : "T30_Potenzial_Krankenhaus"
    },
    "elderly_homes": {
        "tags": {
            "amenity": ["nursing_home", "retirement_home", "care_home"],
            "social_facility": ["nursing_home", "assisted_living"]
        },
        "regex": r"(pflegeheim|pflege-heim|senior|alten|residenz|stift)",
        "speed_annotation" : "T30_Potenzial_Altenheim"
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
            "amenity": ["social_facility", "clinic","craft"],
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