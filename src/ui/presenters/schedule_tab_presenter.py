from typing import TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSlot

from core.interfaces import IGameController
from ui.view_models import (
    ScheduleWeekViewModel, ScheduleBlocViewModel, ScheduleSceneViewModel
)

if TYPE_CHECKING:
    from ui.ui_manager import UIManager
    from ui.tabs.schedule_tab import ScheduleTab

class ScheduleTabPresenter(QObject):
    """
    Presenter for the ScheduleTab. Handles all logic for fetching schedule data,
    managing time state, and processing user interactions.
    """
    def __init__(self, controller: IGameController, view: 'ScheduleTab', ui_manager: 'UIManager', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager

        # --- Internal State ---
        self.current_week = 1
        self.current_year = 1

        # --- Signal Connections ---
        self.controller.signals.scenes_changed.connect(self.refresh_schedule)
        self.controller.signals.time_changed.connect(self._on_time_changed)
        
        self.view.year_changed.connect(self.on_year_changed)
        self.view.plan_bloc_requested.connect(self.on_plan_bloc_requested)
        self.view.item_double_clicked.connect(self.on_item_double_clicked)
        self.view.help_requested.connect(self.on_help_requested)

    def load_initial_data(self):
        """
        Entry point called by the MainWindow. Sets up the initial time state
        and performs the first data load.
        """
        initial_week = self.controller.game_state.week
        initial_year = self.controller.game_state.year
        self._on_time_changed(initial_week, initial_year)

    @pyqtSlot(int, int)
    def _on_time_changed(self, new_week: int, new_year: int):
        """Handles time changes from the game controller."""
        self.current_week = new_week
        self.current_year = new_year

        # Tell the view to update its year selector's range and value
        self.view.update_year_selector(new_year, new_year, new_year + 10)
        
        # A time change always necessitates a schedule refresh
        self.refresh_schedule()

    @pyqtSlot()
    def refresh_schedule(self):
        """
        Fetches all schedule data, processes it into a view model, and sends
        it to the view for rendering. This is the core data-to-view pipeline.
        """
        viewing_year = self.view.get_selected_year()
        
        all_blocs = self.controller.get_blocs_for_schedule_view(viewing_year)
        blocs_by_week = {}
        for bloc in all_blocs:
            week = bloc.scheduled_week
            if week not in blocs_by_week: blocs_by_week[week] = []
            blocs_by_week[week].append(bloc)
        
        # --- Build View Model ---
        schedule_weeks_vm = []
        start_week = self.current_week if viewing_year == self.current_year else 1
        
        for week_num in range(start_week, 53):
            week_vm = ScheduleWeekViewModel(
                display_text=f"Week {week_num}",
                user_data={'type': 'week_header', 'week': week_num, 'year': viewing_year}
            )

            if week_num in blocs_by_week:
                for bloc in sorted(blocs_by_week[week_num], key=lambda b: b.id):
                    scene_count = len(bloc.scenes)
                    plural_s = 's' if scene_count > 1 else ''
                    
                    prod_settings_tooltip = "\n".join(
                        f"  - {cat.replace('_', ' ').title()}: {tier}" 
                        for cat, tier in bloc.production_settings.items()
                    )

                    bloc_vm = ScheduleBlocViewModel(
                        display_text=f"Shooting Bloc ({scene_count} scene{plural_s})",
                        tooltip=f"Production Settings:\n{prod_settings_tooltip}",
                        user_data={'type': 'bloc', 'id': bloc.id}
                    )

                    for scene in sorted(bloc.scenes, key=lambda s: s.title):
                        status_text = scene.display_status
                        scene_vm = ScheduleSceneViewModel(
                            display_text=f"  - {scene.title} [{status_text}]",
                            tooltip=f"'{scene.title}' - Status: {status_text}",
                            user_data={'type': 'scene', 'id': scene.id}
                        )
                        bloc_vm.scenes.append(scene_vm)
                    
                    week_vm.blocs.append(bloc_vm)
            
            schedule_weeks_vm.append(week_vm)
            
        self.view.display_schedule(schedule_weeks_vm)

    @pyqtSlot(int)
    def on_year_changed(self, year: int):
        """When the user changes the year in the view, just refresh the schedule."""
        self.refresh_schedule()

    @pyqtSlot()
    def on_plan_bloc_requested(self):
        """Opens the dialog to plan a new shooting bloc for the current game week."""
        self.ui_manager.show_shooting_bloc_dialog(self.current_week, self.current_year)

    @pyqtSlot(dict)
    def on_item_double_clicked(self, item_data: dict):
        """Handles double-click events forwarded from the view."""
        item_type = item_data.get('type')

        if item_type == 'scene':
            self.ui_manager.show_scene_planner(item_data.get('id'))
        
        elif item_type == 'week_header':
            week = item_data.get('week')
            year = item_data.get('year')
            if week is not None and year is not None:
                self.ui_manager.show_shooting_bloc_dialog(week, year)

    @pyqtSlot(str)
    def on_help_requested(self, topic_key: str):
        """Forwards a help request to the global help handler."""
        self.controller.signals.show_help_requested.emit(topic_key)