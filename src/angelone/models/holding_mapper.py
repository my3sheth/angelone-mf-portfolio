from angelone.models.holding import PortfolioHolding


def map_holding(data: dict) -> PortfolioHolding:
    return PortfolioHolding(
        scheme_code=data["schemeCode"],
        isin=data["isin"],
        scheme_name=data["schemeName"],
        current_value=data["currentValue"],
        invested_value=data["investedValue"],
        returns_value=data["returnsValue"],
        returns_absolute_percent=data["returnsAbsolutePer"],
        xirr_percent=data["xirrPer"],
        total_units=data["totalUnitsAllocated"],
        average_nav=data["averageNav"],
        current_nav=data["currentNav"],
        category=data.get("subCategoryDisplayName", ""),
        subcategory=data.get("subCategory", ""),
        benchmark_name=data.get("benchmarkName", ""),
        benchmark_return_percent=float(
            data.get("retPerCompBenchmark", 0) or 0
        ),
        sip_enabled=data["sipEnabled"],
        next_sip_date=data.get("nextSipDate"),
        last_updated_date=data["lastUpdatedDate"],
    )