import pandas as pd


# Order defines how combinations are named ("Rad-PKW", not "PKW-Rad")
PARTICIPANT_COLUMNS = {
    "IstRad": "Rad",
    "IstPKW": "PKW",
    "IstFuss": "Fuss",
    "IstKrad": "Krad",
    "IstGkfz": "Gkfz",
    "IstSonstige": "Sonstig",
}

CATEGORY_NAMES = {
    1: "Unfall mit Getöteten",
    2: "Unfall mit Schwerverletzten",
    3: "Unfall mit Leichtverletzten",
}

UNCLEAR = "Unklar"
NONE_OF_THESE = "Keine dieser Arten"
THREE_OR_MORE = "3+ Arten"


class CrashClassification:
    @staticmethod
    def classify(crashes: pd.DataFrame) -> pd.DataFrame:
        """
        Add "Unfallklasse" (combination of involved road user types) and
        "Unfallkategorie" (readable severity) to a copy of the crash data.
        """
        result = crashes.copy()

        flags = pd.DataFrame(
            {
                column: pd.to_numeric(result[column], errors="coerce")
                if column in result.columns
                else pd.Series(float("nan"), index=result.index)
                for column in PARTICIPANT_COLUMNS
            },
            index=result.index,
        )

        valid = flags.isin([0, 1]).all(axis=1)
        involved = flags.where(valid, 0).astype(bool)
        counts = involved.sum(axis=1)

        names = involved.apply(
            lambda row: "-".join(
                PARTICIPANT_COLUMNS[column] for column, flag in row.items() if flag
            ),
            axis=1,
        ) if len(result) else pd.Series(dtype=str, index=result.index)

        classes = names.where(counts <= 2, THREE_OR_MORE)
        classes = classes.where(counts > 0, NONE_OF_THESE)
        classes = classes.where(valid, UNCLEAR)

        result["Unfallklasse"] = classes.astype(str) if len(result) else pd.Series(dtype=str)

        if "UKATEGORIE" in result.columns:
            category = pd.to_numeric(result["UKATEGORIE"], errors="coerce")
            result["Unfallkategorie"] = category.map(CATEGORY_NAMES)

        return result
