import pandas as pd

def validate_eia(df: pd.DataFrame) -> list:
    """
    Runs data quality checks on EIA raw data.
    Returns a list of issue strings (empty list = all clean).
    """
    issues = []

    if df["value"].isnull().any():
        n = df["value"].isnull().sum()
        issues.append(f"EIA: {n} rows have null 'value'")

    negative_demand = df[(df["type"] == "D") & (df["value"] < 0)]
    if len(negative_demand) > 0:
        issues.append(f"EIA: {len(negative_demand)} rows have negative demand")

    expected_types = {"D", "DF", "NG", "TI"}
    found_types = set(df["type"].unique())
    missing_types = expected_types - found_types
    if missing_types:
        issues.append(f"EIA: missing expected types: {missing_types}")

    hours_per_type = df.groupby("type")["period"].nunique()
    if hours_per_type.nunique() > 1:
        issues.append(f"EIA: inconsistent hour counts per type: {hours_per_type.to_dict()}")

    return issues


def validate_gridstatus(df: pd.DataFrame) -> list:
    """
    Runs data quality checks on GridStatus raw data.
    Returns a list of issue strings (empty list = all clean).
    """
    issues = []

    if df["lmp"].isnull().any():
        n = df["lmp"].isnull().sum()
        issues.append(f"GridStatus: {n} rows have null 'lmp'")

    extreme_prices = df[(df["lmp"] < -500) | (df["lmp"] > 2000)]
    if len(extreme_prices) > 0:
        issues.append(f"GridStatus: {len(extreme_prices)} rows have extreme LMP (<-500 or >2000 $/MWh)")

    expected_hubs = {"TH_NP15_GEN-APND", "TH_SP15_GEN-APND", "TH_ZP26_GEN-APND"}
    found_hubs = set(df["location"].unique())
    missing_hubs = expected_hubs - found_hubs
    if missing_hubs:
        issues.append(f"GridStatus: missing expected hubs: {missing_hubs}")

    return issues


def run_validation(df_eia: pd.DataFrame, df_gridstatus: pd.DataFrame) -> dict:
    """
    Runs all validation checks and returns a summary dict.
    """
    eia_issues = validate_eia(df_eia)
    gs_issues = validate_gridstatus(df_gridstatus)

    summary = {
        "eia_clean": len(eia_issues) == 0,
        "eia_issues": eia_issues,
        "gridstatus_clean": len(gs_issues) == 0,
        "gridstatus_issues": gs_issues,
    }

    if eia_issues:
        print("EIA validation issues found:")
        for issue in eia_issues:
            print(f"  - {issue}")
    else:
        print("EIA data: all checks passed")

    if gs_issues:
        print("GridStatus validation issues found:")
        for issue in gs_issues:
            print(f"  - {issue}")
    else:
        print("GridStatus data: all checks passed")

    return summary
