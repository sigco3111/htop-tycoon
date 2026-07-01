"""htop-tycoon v3.0 — modal screen package (spec §4.1).

Each modal is a Textual ``ModalScreen`` subclass. The app pushes these
via ``self.app.push_screen(StrategyPickerScreen())`` etc.

Screens in this first pass:
- ``StrategyPickerScreen`` — pick 1 of 4 strategies (spec §4.1)
- ``GameStarterScreen`` — pick genre + theme + platform, then start game
- ``EmployeePanelScreen`` — employee detail (hiring / promoting / firing)
- ``ArchiveScreen`` — past game results
- ``EndingScreen`` — game-over summary
"""
