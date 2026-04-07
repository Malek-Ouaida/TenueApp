from .models import (
    Outfit,
    OutfitItem,
    OutfitSeason,
    OutfitSource,
    WearContext,
    WearItemRole,
    WearItemSource,
    WearLog,
    WearLogItem,
    WearLogSnapshot,
    WearLogSource,
)

__all__ = [
    "InvalidWearHistoryCursorError",
    "Outfit",
    "OutfitItem",
    "OutfitSeason",
    "OutfitSource",
    "WearCalendarDaySnapshot",
    "WearContext",
    "WearItemRole",
    "WearItemSource",
    "WearLog",
    "WearLogDetailSnapshot",
    "WearLoggedItemSnapshot",
    "WearLogItem",
    "WearLogSnapshot",
    "WearLogSource",
    "WearLogTimelineItemSnapshot",
    "WearRepository",
    "WearService",
    "WearServiceError",
]


def __getattr__(name: str):
    if name == "WearRepository":
        from .repository import WearRepository

        return WearRepository

    if name in {
        "InvalidWearHistoryCursorError",
        "WearCalendarDaySnapshot",
        "WearLogDetailSnapshot",
        "WearLoggedItemSnapshot",
        "WearLogTimelineItemSnapshot",
        "WearService",
        "WearServiceError",
    }:
        from .service import (
            InvalidWearHistoryCursorError,
            WearCalendarDaySnapshot,
            WearLogDetailSnapshot,
            WearLoggedItemSnapshot,
            WearLogTimelineItemSnapshot,
            WearService,
            WearServiceError,
        )

        return {
            "InvalidWearHistoryCursorError": InvalidWearHistoryCursorError,
            "WearCalendarDaySnapshot": WearCalendarDaySnapshot,
            "WearLogDetailSnapshot": WearLogDetailSnapshot,
            "WearLoggedItemSnapshot": WearLoggedItemSnapshot,
            "WearLogTimelineItemSnapshot": WearLogTimelineItemSnapshot,
            "WearService": WearService,
            "WearServiceError": WearServiceError,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
