"""htop_tycoon UI screens — modals for hire/fire/release/console/strategy/ending + help/search/new_project/promote."""

from htop_tycoon.ui.screens.console import ConsoleMarketScreen
from htop_tycoon.ui.screens.ending import (
    ENDING_DESCRIPTIONS,
    ENDING_KIND_DESCRIPTIONS,
    ENDING_KIND_LABELS,
    ENDING_LABELS,
    EndingScreen,
    LegacyPanel,
)
from htop_tycoon.ui.screens.fire import FireScreen
from htop_tycoon.ui.screens.help import HelpScreen
from htop_tycoon.ui.screens.hire import HireScreen
from htop_tycoon.ui.screens.new_project import NewProjectScreen
from htop_tycoon.ui.screens.promote import PromoteScreen
from htop_tycoon.ui.screens.release import ReleaseScreen
from htop_tycoon.ui.screens.search import SearchScreen
from htop_tycoon.ui.screens.strategy_picker import StrategyPicker

__all__ = [
    "ConsoleMarketScreen",
    "EndingScreen",
    "LegacyPanel",
    "ENDING_LABELS",
    "ENDING_DESCRIPTIONS",
    "ENDING_KIND_LABELS",
    "ENDING_KIND_DESCRIPTIONS",
    "FireScreen",
    "HelpScreen",
    "HireScreen",
    "NewProjectScreen",
    "PromoteScreen",
    "ReleaseScreen",
    "SearchScreen",
    "StrategyPicker",
]
