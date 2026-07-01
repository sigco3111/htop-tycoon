"""htop-tycoon v3.0 — UI widget package (spec §4.1).

Widgets are pure Textual: they read from a reactive reference to the
current ``GameState`` (passed in via ``HtopTycoonApp``) and render
textual output. They never call into the engine directly — the engine
emits ``Event`` objects, the UI consumes them.
"""
from htop_tycoon.ui.widgets.employee_table import EmployeeTable
from htop_tycoon.ui.widgets.footer import HtopFooter
from htop_tycoon.ui.widgets.header import HtopHeader
from htop_tycoon.ui.widgets.metric_bar import MetricBar
from htop_tycoon.ui.widgets.org_tree import OrgTree
from htop_tycoon.ui.widgets.strategy_status import StrategyStatus

__all__ = [
    "EmployeeTable",
    "HtopFooter",
    "HtopHeader",
    "MetricBar",
    "OrgTree",
    "StrategyStatus",
]
