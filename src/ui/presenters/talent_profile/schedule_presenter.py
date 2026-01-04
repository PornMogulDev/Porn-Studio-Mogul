from PyQt6.QtCore import QObject
from typing import List

from data.game_state import Talent
from ui.view_models import TalentScheduleWeekViewModel, TourViewModel, ScheduleStatus
from utils import time_utils

class SchedulePresenter(QObject):
    """
    Sub-presenter responsible for calculating and displaying the talent's schedule.
    """
    def __init__(self, controller, widget, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.widget = widget

    def set_talent(self, talent: Talent):
        """Calculates schedule status for the current year and updates the widget."""
        if not talent:
            return

        current_absolute_week = self.controller.game_state.absolute_week
        current_year, _ = time_utils.from_absolute(current_absolute_week)
        
        # Call the controller to get the pre-calculated status
        weekly_statuses = self.controller.get_talent_schedule_status(talent.id, current_year)

        schedule_view_models = []
        
        for result in weekly_statuses:
            # Map DTO to ViewModel
            
            # Handle Tour ViewModel mapping
            tour_vm = None
            if result.tour:
                tour_vm = TourViewModel.from_dataclass(result.tour)
            
            # Format tooltip (Presentation Logic)
            tooltip_parts = []
            if result.tour:
                tooltip_parts.append(f"<b>On Tour:</b> {result.tour.destination_location}")
            
            if result.is_on_cooldown:
                tooltip_parts.append("<b>Tour Cooldown:</b> Recovering from travel.")
            
            if result.is_fatigued:
                tooltip_parts.append("<b>Resting:</b> High Fatigue")

            if result.booked_scene_titles:
                header = "<b>Fully Booked:</b>" if result.status_enum == ScheduleStatus.UNAVAILABLE else "<b>Booked for:</b>"
                details = "<br>".join([f"- {t}" for t in result.booked_scene_titles])
                tooltip_parts.append(f"{header}<br>{details}")

            tooltip_text = "<br>".join(tooltip_parts) if tooltip_parts else "Available for booking."
            
            # Map Enum to string
            status_str = result.status_enum.name.lower()
            
            vm = TalentScheduleWeekViewModel(
                week_number=result.week_number,
                status_str=status_str,
                tooltip=tooltip_text,
                tour=tour_vm,
                is_on_cooldown=result.is_on_cooldown
            )
            schedule_view_models.append(vm)

        self.widget.display_schedule(current_year, schedule_view_models)