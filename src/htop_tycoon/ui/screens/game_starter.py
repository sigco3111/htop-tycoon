"""htop-tycoon v3.0 — GameStarterScreen (spec §4.1).

Modal for starting a new game project. Player picks:
- genre    (e.g., rpg / action / strategy / ...)
- theme    (e.g., fantasy / ninja / sci_fi / ...)
- platform (PC / Console A / B / C / OWN_CONSOLE)

Spec §4.1: key ``n`` opens this screen. On dismiss, the chosen triple
is returned to the caller (typically HtopTycoonApp.action_start_game).
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Select, Static

from htop_tycoon.domain import Platform

# Spec §1.3 / §2.7: 12 genres and 30 themes are defined in the data layer.
# This first pass hard-codes a curated subset; the full data files ship
# in a follow-up (read via data/ YAMLs).
GENRE_OPTIONS: list[tuple[str, str]] = [
    ("RPG", "rpg"), ("Action", "action"), ("Simulation", "simulation"),
    ("Adventure", "adventure"), ("Puzzle", "puzzle"), ("Strategy", "strategy"),
    ("Sports", "sports"), ("Rhythm", "rhythm"), ("Fighting", "fighting"),
    ("Horror", "horror"), ("Educational", "educational"), ("Online", "online"),
]
THEME_OPTIONS: list[tuple[str, str]] = [
    ("판타지 (Fantasy)", "fantasy"), ("SF (SciFi)", "sf"), ("현대 (Modern)", "modern"),
    ("역사 (History)", "history"), ("미래 (Future)", "future"), ("동화 (Fairy Tale)", "fairy_tale"),
    ("무협 (Martial Arts)", "martial_arts"), ("학원 (School)", "school"),
    ("요괴 (Yokai)", "yokai"), ("좀비 (Zombie)", "zombie"), ("우주 (Space)", "space"),
    ("잠입 (Stealth)", "stealth"), ("해적 (Pirate)", "pirate"), ("사무라이 (Samurai)", "samurai"),
    ("요리 (Cooking)", "cooking"), ("음악 (Music)", "music"), ("운동 (Sports)", "sports"),
    ("패션 (Fashion)", "fashion"), ("연애 (Romance)", "romance"),
    ("추리 (Mystery)", "mystery"), ("법정 (Court)", "court"),
    ("시간여행 (Time Travel)", "time_travel"), ("마법 (Magic)", "magic"),
    ("로봇 (Robot)", "robot"), ("동물 (Animal)", "animal"),
    ("의학 (Medical)", "medical"), ("자동차 (Cars)", "cars"),
    ("비행 (Aviation)", "aviation"), ("주식 (Stocks)", "stocks"),
    ("게임 (Games)", "games"),
]
PLATFORM_OPTIONS: list[tuple[str, str]] = [
    (Platform.PC.name, Platform.PC.name),
    ("CONSOLE_A", Platform.CONSOLE_A.name),
    ("CONSOLE_B", Platform.CONSOLE_B.name),
    ("CONSOLE_C", Platform.CONSOLE_C.name),
    ("OWN_CONSOLE", Platform.OWN_CONSOLE.name),
]


class GameStarterScreen(ModalScreen[tuple[str, str, str] | None]):
    """Spec §4.1: 'n → genre+direction pick → game starts → progress shown'."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "취소"),
    ]

    DEFAULT_CSS = """
    GameStarterScreen {
        align: center middle;
    }
    #starter {
        width: 80;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    .picker-row {
        height: 3;
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="starter"):
            yield Static("[bold]새 게임 (New Game)[/]\n장르/주제/플랫폼을 선택하세요.", id="title")
            with Horizontal(classes="picker-row"):
                yield Static("장르:\n")
                yield Select(GENRE_OPTIONS, id="genre", value="rpg")
            with Horizontal(classes="picker-row"):
                yield Static("주제:\n")
                yield Select(THEME_OPTIONS, id="theme", value="fantasy")
            with Horizontal(classes="picker-row"):
                yield Static("플랫폼:\n")
                yield Select(PLATFORM_OPTIONS, id="platform", value=Platform.PC.name)
            yield Button("시작 (Start)", id="start")
            yield Static("", id="status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            genre = self.query_one("#genre", Select).value
            theme = self.query_one("#theme", Select).value
            platform = self.query_one("#platform", Select).value
            # Select.value is a StringEnum; convert to its .value (the underlying string).
            self.dismiss(
                (
                    genre.value if hasattr(genre, "value") else str(genre),
                    theme.value if hasattr(theme, "value") else str(theme),
                    platform.value if hasattr(platform, "value") else str(platform),
                )
            )

    async def action_dismiss(self, value: tuple[str, str, str] | None = None) -> None:
        self.dismiss(value)


__all__ = ["GameStarterScreen"]
