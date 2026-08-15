from .models import Holding


def map_holding(data: dict) -> Holding:
    return Holding(
        scheme_code=data["schemeCode"],
        isin=data["isin"],
        scheme_name=data["schemeName"],
        category=data.get("subCategoryDisplayName", ""),
        current_value=float(data["currentValue"]),
        invested_value=float(data["investedValue"]),
        returns_value=float(data["returnsValue"]),
        returns_percentage=float(data["returnsAbsolutePer"]),
        xirr_percentage=float(data["xirrPer"]),
        units=float(data["totalUnitsAllocated"]),
        average_nav=float(data["averageNav"]),
        current_nav=float(data["currentNav"]),
    )


def map_holdings(data: list[dict]) -> list[Holding]:
    return [map_holding(item) for item in data]