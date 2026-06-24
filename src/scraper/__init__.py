"""Factoría de scrapers. Retorna el backend seleccionado sin exponer imports cruzados."""

from src.pipeline.infojobs_scraper import (
    BotBlockedError,
    InfoJobsParser,
    RawOfferDetail,
    SearchStub,
)


def create_scraper(backend: str = "curl") -> object:
    """Crea una instancia del scraper backend.

    Args:
        backend: "curl" (default) | "camoufox"

    Returns:
        Instancia con interfaz: warmup(), search(), detail(url), close()
    """
    if backend == "camoufox":
        from src.scraper.camoufox_scraper import CamoufoxScraper

        return CamoufoxScraper()
    from src.pipeline.infojobs_scraper import InfoJobsScraper

    return InfoJobsScraper(delay=6.0, jitter=4.0)


__all__ = [
    "create_scraper",
    "BotBlockedError",
    "InfoJobsParser",
    "RawOfferDetail",
    "SearchStub",
]
