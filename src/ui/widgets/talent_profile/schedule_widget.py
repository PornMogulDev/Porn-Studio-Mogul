import logging
from typing import List

from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel
from PyQt6.QtCore import Qt

from ui.view_models import TalentScheduleWeekViewModel

logger = logging.getLogger(__name__)

class ScheduleWidget(QWidget):
    """
    A widget to display a talent's weekly schedule for a year in a grid format.
    It relies on QSS properties for styling, making it theme-agnostic.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid_layout = QGridLayout()
        self._grid_layout.setSpacing(2)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._grid_layout)
        self._week_labels = [] # To keep references to labels for cleanup

    def _clear_grid(self):
        """Removes all existing week labels from the grid layout."""
        for label in self._week_labels:
            self._grid_layout.removeWidget(label)
            label.deleteLater()
        self._week_labels.clear()

    def display_schedule(self, year: int, week_data: List[TalentScheduleWeekViewModel]):
        """
        Populates the grid with schedule information for a given year.

        Args:
            year: The year being displayed (for future use).
            week_data: A list of view models, one for each week.
        """
        self._clear_grid()

        num_cols = 13 # 13 weeks per row, 4 rows total
        for i, vm in enumerate(week_data):
            label = QLabel(str(vm.week_number))
            label.setObjectName("scheduleWeekLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setToolTip(vm.tooltip)

            # Set the custom property that the QSS in ThemeManager will use for styling
            label.setProperty("status", vm.status_str)

            # Add a second property for tour status
            if vm.tour and vm.tour.status in ['planned', 'active']:
                 label.setProperty("on_tour", True)

            # Force the widget to re-evaluate its style based on the new property
            label.style().unpolish(label)
            label.style().polish(label)

            row = i // num_cols
            col = i % num_cols
            self._grid_layout.addWidget(label, row, col)
            self._week_labels.append(label)