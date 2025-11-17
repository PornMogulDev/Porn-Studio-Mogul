import logging
from typing import TYPE_CHECKING, Dict
from dataclasses import asdict
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt6 import sip

from data.game_state import Talent
from core.interfaces import IGameController
from ui.windows.talent_profile_window import TalentProfileWindow
from ui.view_models import ScheduleStatus, TalentScheduleWeekViewModel, TourViewModel
from utils.formatters import get_fuzzed_skill_range, format_skill_range, format_fatigue
from ui.builders.role_details_builder import prepare_role_details_data, format_role_details_html
from ui.builders.preferences_view_model_builder import build_preferences_view_model

if TYPE_CHECKING:
    from ui.ui_manager import UIManager

logger = logging.getLogger(__name__)

class TalentProfilePresenter(QObject):
    """
    Handles the logic for the TalentProfileWindow.
    """
    open_talent_profile_requested = pyqtSignal(int)

    def __init__(self, controller: IGameController, view: TalentProfileWindow, uimanager: 'UIManager', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.uimanager = uimanager
        self.open_talents = {}  # {talent_id: Talent}
        self.current_talent_id = None

        # Pass theme-dependent colors to widgets that need them for dynamic drawing
        current_theme_name = self.controller.settings_manager.get_setting("theme", "light")
        current_theme = self.controller.theme_manager.get_theme(current_theme_name)
        self.view.preferences_widget.set_theme_colors(danger_color=current_theme.danger)

        self._connect_signals()

        # Pass configuration data to the view widgets that need it
        raw_discount_tiers = self.controller.data_manager.game_config.get("hiring_bulk_discount_tiers", {})
        cleaned_discount_tiers = {int(k): v for k, v in raw_discount_tiers.items()}
        self.view.hiring_widget.set_discount_tiers(cleaned_discount_tiers)

    def _connect_signals(self):
        """Connect signals from the view to slots in the presenter."""
        # Connect to the view's high-level signal for tour confirmation
        self.view.tour_sponsorship_confirmed.connect(self._on_tour_sponsorship_confirmed)

        # Connect signals from the panel widgets
        self.view.hiring_widget.hire_confirmed.connect(self._on_hire_confirmed)
        self.view.chemistry_widget.talent_profile_requested.connect(self.uimanager.show_talent_profile)
        self.view.hiring_widget.open_scene_dialog_requested.connect(self.uimanager.show_scene_planner)
        self.view.history_widget.open_scene_dialog_requested.connect(self._on_shot_scene_details_requested)
        
        # Connect to global signals to stay up-to-date
        self.controller.signals.scenes_changed.connect(self._refresh_current_talent_data_on_change)
        self.controller.signals.roster_changed.connect(self._refresh_current_talent_data_on_change)
        self.controller.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

    def _refresh_current_talent_data_on_change(self):
        """A single slot to reload all relevant data for the current talent when game state changes."""
        if self.current_talent_id:
            self._load_and_display_schedule()
            self.refresh_available_roles()

    @pyqtSlot(int)
    def _on_shot_scene_details_requested(self, scene_id: int):
        """
        Slot to handle a request to open a scene's details.
        It fetches the full scene object before calling the UIManager.
        """
        if scene := self.controller.get_scene_by_id(scene_id):
            self.uimanager.show_shot_scene_details(scene.id)
        else:
            logger.warning(f"Could not find scene with ID {scene_id} to show details.")

    def open_talent(self, talent: Talent):
        """Opens a talent in the window, creating a new tab if necessary."""
        if talent.id in self.open_talents:
            self.switch_to_talent(talent.id)
        else:
            self.open_talents[talent.id] = talent
            self.view.add_talent_tab(talent.id, talent.alias)
            self.switch_to_talent(talent.id)

    def switch_to_talent(self, talent_id: int):
        """Switches the view to display data for the given talent_id."""
        if self.current_talent_id == talent_id:
            return
        if talent_id not in self.open_talents:
            return

        self.current_talent_id = talent_id
        self.view.set_active_talent_tab(talent_id)
        self._load_data_for_current_talent()

    def close_talent(self, talent_id: int):
        """Closes a talent's tab and removes it from the open list."""
        if talent_id not in self.open_talents:
            return

        del self.open_talents[talent_id]
        
        self.view.remove_talent_tab(talent_id)
 
        if not self.open_talents:
            self.current_talent_id = None
            self.view.close()
        elif self.current_talent_id == talent_id:
            self.current_talent_id = None

    def _load_data_for_current_talent(self):
        """Loads all data for the current talent and updates the view."""
        if not self.current_talent_id or self.current_talent_id not in self.open_talents:
            return
        talent = self.open_talents[self.current_talent_id]

        self._load_and_display_details(talent)
        self._load_and_display_preferences(talent)
        self._load_and_display_schedule()
        
        history = self.controller.get_scene_history_for_talent(talent.id)
        self.view.history_widget.display_scene_history(history, talent.id)
        
        raw_chemistry_dict = self.controller.get_talent_chemistry(talent.id)

        chemistry_view_model = []
        for other_talent_id, chem_details in raw_chemistry_dict.items(): 
            if other_talent := self.controller.get_talent_by_id(other_talent_id):
                chemistry_view_model.append({
                    'other_talent_id': other_talent_id,
                    'other_talent_alias': other_talent.alias,
                    'score': chem_details['score'] 
                })

        self.view.chemistry_widget.display_chemistry(chemistry_view_model)
        self.refresh_available_roles()

    def _load_and_display_details(self, talent: Talent):
        ethnicity_str = talent.ethnicity
        if talent.primary_ethnicity and talent.ethnicity != talent.primary_ethnicity:
            ethnicity_str = f"{talent.ethnicity}"
        self.view.details_widget.display_basic_info({
            'age': talent.age,
            'gender': talent.gender,
            'orientation': talent.orientation_score,
            'ethnicity': ethnicity_str,
            'nationality': talent.nationality,
            'location': talent.base_location,
            'popularity': round(sum(talent.popularity.values())),
            'fatigue': format_fatigue(talent.fatigue)
        })
        self.view.details_widget.display_skills({
            'performance': format_skill_range(get_fuzzed_skill_range(talent.performance, talent.experience, talent.id)),
            'acting': format_skill_range(get_fuzzed_skill_range(talent.acting, talent.experience, talent.id)),
            'stamina': format_skill_range(get_fuzzed_skill_range(talent.stamina, talent.experience, talent.id)),
            'dom_skill': format_skill_range(get_fuzzed_skill_range(talent.dom_skill, talent.experience, talent.id)),
            'sub_skill': format_skill_range(get_fuzzed_skill_range(talent.sub_skill, talent.experience, talent.id)),
            'experience': int(talent.experience)
        })
        self.view.details_widget.populate_physical_label(talent)

    def _load_and_display_schedule(self):
        """Fetches, processes, and displays the talent's yearly schedule."""
        if not self.current_talent_id: return
        talent = self.open_talents[self.current_talent_id]
        current_year = self.controller.game_state.year
        
        bookings_by_week = self.controller.get_talent_bookings_for_year(talent.id, current_year)
        tours_this_year = self.controller.get_talent_tours_for_year(talent.id, current_year)

        schedule_view_models = []
        tour_map = {}
        for tour in tours_this_year:
            for i in range(tour.duration_weeks):
                week_num = tour.start_week + i
                year_offset = (week_num - 1) // 52
                if tour.start_year + year_offset == current_year:
                    actual_week = (week_num - 1) % 52 + 1
                    tour_map[actual_week] = tour

        ambition_threshold = 7
        base_max_scenes = 2
        max_scenes_per_week = base_max_scenes + 1 if talent.ambition >= ambition_threshold else base_max_scenes
        fatigue_resting_threshold = 75

        for week_num in range(1, 53):
            bookings_this_week = bookings_by_week.get(week_num, [])
            tour_this_week = tour_map.get(week_num)
            
            status_enum = ScheduleStatus.AVAILABLE
            tooltip_text = "Available for booking."
            tour_vm = None
            scene_titles = [scene.title for scene in bookings_this_week]

            if tour_this_week:
                status_enum = ScheduleStatus.ON_TOUR
                tooltip_text = f"On Tour in {tour_this_week.destination_location}"
                tour_vm = TourViewModel.from_dataclass(tour_this_week)

            if talent.fatigue >= fatigue_resting_threshold and not bookings_this_week and not tour_this_week:
                status_enum = ScheduleStatus.UNAVAILABLE
                tooltip_text = "Resting (High Fatigue)"
            elif len(bookings_this_week) >= max_scenes_per_week:
                status_enum = ScheduleStatus.UNAVAILABLE
                tooltip_text = f"Fully Booked:\n- " + "\n- ".join(scene_titles)
            elif bookings_this_week:
                status_enum = ScheduleStatus.PARTIALLY_BOOKED
                tooltip_text = f"Booked for:\n- " + "\n- ".join(scene_titles)

            status_str = status_enum.name.lower()
            vm = TalentScheduleWeekViewModel(
                week_number=week_num, status_str=status_str,
                tooltip=tooltip_text, tour=tour_vm
            )
            schedule_view_models.append(vm)

        self.view.schedule_widget.display_schedule(current_year, schedule_view_models)

    @pyqtSlot()
    def refresh_available_roles(self):
        """Fetches and updates the list of available roles for the current talent."""
        if not self.current_talent_id: return
        if not self.view or sip.isdeleted(self.view): return
            
        available_roles = self.controller.find_available_roles_for_talent(self.current_talent_id)
        
        for role_data in available_roles:
            details_dict = prepare_role_details_data(role_data['scene_id'], role_data['virtual_performer_id'], self.controller)
            tooltip_html = format_role_details_html(details_dict)
            role_data['tooltip_html'] = tooltip_html
            
        talent = self.open_talents[self.current_talent_id]
        studio_location = self.controller.game_state.studio_location
        try:
            self.view.hiring_widget.update_available_roles(available_roles, talent.base_location, studio_location)
        except RuntimeError:
            pass

    def get_tour_sponsorship_preview(self, roles_for_tour: list) -> Dict:
        """
        Calls the controller to get a tour preview DTO and converts it to a dict
        for consumption by the view's dialog.
        """
        if not self.current_talent_id:
            return {'is_feasible': False, 'refusal_reason': 'No active talent.'}
        
        # 1. Call controller, get the DTO back
        result_dto = self.controller.get_tour_sponsorship_preview(self.current_talent_id, roles_for_tour)
        
        # 2. Convert DTO to a plain dict for the view. The view shouldn't know about DTOs.
        return asdict(result_dto)

    @pyqtSlot(int, list, dict, int)
    def _on_tour_sponsorship_confirmed(self, talent_id: int, roles_to_cast: list, tour_details: dict, total_cost: int):
        """
        Handles the final command to sponsor a tour after the view has confirmed it.
        """
        # The view has already done all the UI work. This is just the final, clean call.
        self.controller.sponsor_tour(talent_id, roles_to_cast, tour_details, total_cost)

    @pyqtSlot(list)
    def _on_hire_confirmed(self, roles_to_cast: list):
        """Handles the logic when the user confirms a hiring decision."""
        if not self.current_talent_id: return
        self.controller.cast_talent_for_multiple_roles(self.current_talent_id, roles_to_cast)

    @pyqtSlot(str)
    def _on_setting_changed(self, key: str):
        if key == "unit_system":
            if self.current_talent_id:
                talent = self.open_talents[self.current_talent_id]
                self.view.details_widget.populate_physical_label(talent)
        elif key == "theme":
            current_theme = self.controller.theme_manager.get_theme(self.controller.settings_manager.get_setting("theme", "light"))
            self.view.preferences_widget.set_theme_colors(danger_color=current_theme.danger)
            self._load_data_for_current_talent()
            
    def _load_and_display_preferences(self, talent: Talent):
        """Processes and summarizes talent preferences for UI display."""
        tag_definitions = self.controller.data_manager.tag_definitions
        policy_definitions = self.controller.data_manager.on_set_policies_data

        preferences_data, limits, required_policies, refused_policies = build_preferences_view_model(
            talent=talent,
            tag_definitions=tag_definitions,
            policy_definitions=policy_definitions
        )

        self.view.preferences_widget.display_preferences(
            preferences_data=preferences_data,
            limits=limits,
            required_policies=required_policies,
            refused_policies=refused_policies
        )