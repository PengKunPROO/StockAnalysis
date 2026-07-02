"""Datasource plugin auto-discovery and registry."""
from app.datasources.tonghuashun import TonghuashunSource
from app.datasources.yfinance import USStockSource
from app.datasources.sample import SampleSource

_registry: dict[str, object] = {}
_built: bool = False


def _build_registry():
    global _registry, _built
    if _built:
        return
    # Order matters: first registered = primary for market
    _registry["tonghuashun"] = TonghuashunSource()
    _registry["yfinance"] = USStockSource()
    _registry["sample"] = SampleSource()
    _built = True


def get_sources() -> dict[str, object]:
    _build_registry()
    return _registry


def get_source_for_market(market: str) -> object | None:
    _build_registry()
    for source in _registry.values():
        if market in source.markets:
            return source
    return None


def get_healthy_sources() -> list[str]:
    _build_registry()
    return [name for name, src in _registry.items() if src.health_check()]
