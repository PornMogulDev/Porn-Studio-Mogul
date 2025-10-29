import logging
from typing import TYPE_CHECKING
from collections import defaultdict
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from data.game_state import Talent
from core.interfaces import IGameController
from ui.windows.talent_profile_window import TalentProfileWindow
from utils.formatters import get_fuzzed_skill_range, format_skill_range, format_fatigue

if TYPE_CHECKING:
    from ui.ui_manager import UIManager

logger = logging.getLogger(__name__)

class TalentProfilePresenter(QObject):
    """
    Handles the logic for the TalentProfileDialog.
    """
    # Signal to request opening another talent's profile.
    open_talent_profile_requested = pyqtSignal(int)

    def __init__(self, controller: IGameController, view: TalentProfileWindow, uimanager: 'UIManager', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.uimanager = uimanager
        self.open_talents = {}  # {talent_id: Talent}
        self.current_talent_id = None

        self._connect_signals()

    def _connect_signals(self):
        """Connect signals from the view to slots in the presenter."""
        # Connect signals from the new panel widgets
        self.view.hiring_widget.hire_confirmed.connect(self._on_hire_confirmed)
        self.view.chemistry_widget.talent_profile_requested.connect(self.open_talent_profile_requested)
        self.view.hiring_widget.open_scene_dialog_requested.connect(self.uimanager.show_scene_planner)
        self.view.history_widget.open_scene_dialog_requested.connect(self._on_shot_scene_details_requested)
        
        # Connect to global signals to stay up-to-date
        self.controller.signals.scenes_changed.connect(self.refresh_available_roles)
        self.controller.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

    @pyqtSlot(int)
    def _on_shot_scene_details_requested(self, scene_id: int):
        """
        Slot to handle a request to open a scene's details.
        It fetches the full scene object before calling the UIManager.
        """
        if scene := self.controller.get_scene_for_planner(scene_id):
            self.uimanager.show_shot_scene_details(scene)
        else:
            logger.warning(f"Could not find scene with ID {scene_id} to show details.")

    def open_talent(self, talent: Talent):
        """Opens a talent in the window, creating a new tab if necessary."""
        if talent.id in self.open_talents:
            # If talent is already open, just switch to it.
            # The switch_to_talent method has a guard to prevent redundant reloads,
            # but it will ensure the view is updated if needed.
            self.switch_to_talent(talent.id)
        else:
            self.open_talents[talent.id] = talent
            self.view.add_talent_tab(talent.id, talent.alias)
            # Explicitly call switch_to_talent to ensure the first-time load occurs.
            self.switch_to_talent(talent.id)

    def switch_to_talent(self, talent_id: int):
        """Switches the view to display data for the given talent_id."""
        # Guard against redundant reloads if the tab is already active
        if self.current_talent_id == talent_id:
            return
        if talent_id not in self.open_talents:
            return

        self.current_talent_id = talent_id
        self.view.set_active_talent_tab(talent_id)
        # The view is already showing the correct tab, we just need to load data.
        self._load_data_for_current_talent()

    def close_talent(self, talent_id: int):
        """Closes a talent's tab and removes it from the open list."""
        if talent_id not in self.open_talents:
            return

        del self.open_talents[talent_id]
        
        # When the view removes the tab, if it was the active one,
        # the QTabBar will automatically select a new tab and emit currentChanged.
        # This will naturally trigger our switch_to_talent logic.
        self.view.remove_talent_tab(talent_id)
 
        if not self.open_talents:
            self.current_talent_id = None
            self.view.close()
        elif self.current_talent_id == talent_id:
            # The closed tab was the active one. Clear the current_talent_id.
            # The currentChanged signal from the tab bar will set the new one.
            self.current_talent_id = None

    def _load_data_for_current_talent(self):
        """Loads all data for the current talent and updates the view."""
        if not self.current_talent_id or self.current_talent_id not in self.open_talents:
            return
        talent = self.open_talents[self.current_talent_id]

        # Details & Skills
        self._load_and_display_details(talent)
        
        # Preferences & Requirements
        self._load_and_display_preferences(talent)
        
        # Scene History & Chemistry
        history = self.controller.get_scene_history_for_talent(talent.id)
        self.view.history_widget.display_scene_history(history, talent.id)
        
        current_theme = self.controller.get_current_theme()
        chemistry = self.controller.talent_service.get_talent_chemistry(talent.id)
        self.view.chemistry_widget.display_chemistry(chemistry, current_theme)

        # Hiring Tab
        self.refresh_available_roles()

    def _load_and_display_details(self, talent: Talent):
        self.view.details_widget.display_basic_info({
            'age': talent.age,
            'gender': talent.gender,
            'orientation': talent.orientation_score,
            'ethnicity': talent.ethnicity,
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

    @pyqtSlot()
    def refresh_available_roles(self):
        """Fetches and updates the list of available roles for the current talent."""
        if not self.current_talent_id: return
        available_roles = self.controller.hire_talent_service.find_available_roles_for_talent(self.current_talent_id)
        self.view.hiring_widget.update_available_roles(available_roles)

    @pyqtSlot(list)
    def _on_hire_confirmed(self, roles_to_cast: list):
        """Handles the logic when the user confirms a hiring decision."""
        if not self.current_talent_id: return
         # The view has already done the basic validation. We can proceed.
        self.controller.cast_talent_for_multiple_roles(self.current_talent_id, roles_to_cast)

    @pyqtSlot(str)
    def _on_setting_changed(self, key: str):
        if key == "unit_system":
            if self.current_talent_id:
                talent = self.open_talents[self.current_talent_id]
                self.view.details_widget.populate_physical_label(talent)
            
    def _load_and_display_preferences(self, talent: Talent):
        """Processes and summarizes talent preferences for UI display."""
        # Define thresholds for categorization and display
        LOVES_THRESHOLD = 1.4
        LIKES_THRESHOLD = 1.01 # Anything above 1.0 is a like
        DISLIKES_THRESHOLD = 0.99 # Anything below 1.0 is a dislike
        HATES_THRESHOLD = 0.60
        REFUSAL_THRESHOLD = 0.2 # Preference so low they might refuse the role
        NOTABLE_HIGH_THRESHOLD = 1.2
        NOTABLE_LOW_THRESHOLD = 0.8

        tag_definitions = self.controller.data_manager.tag_definitions
        
        prefs_by_orientation = defaultdict(list)

        # 1. Group all preference scores by their orientation
        for tag, roles in talent.tag_preferences.items():
            tag_def = tag_definitions.get(tag)
            if not tag_def or not (orientation := tag_def.get('orientation')):
                continue
            for role, score in roles.items():
                prefs_by_orientation[orientation].append({'tag': tag, 'role': role, 'score': score})

        # 2. Process each orientation group to create the final data structure
        preferences_data = []
        for orientation, items in sorted(prefs_by_orientation.items()):
            if not items:
                continue

            scores = [item['score'] for item in items]
            avg_score = sum(scores) / len(scores)
        
            # Determine summary string based on the average score
            if avg_score >= LOVES_THRESHOLD:
                summary = "Loves"
            elif avg_score >= LIKES_THRESHOLD:
                summary = "Likes"
            elif avg_score > HATES_THRESHOLD: # Covers the range from 0.60 to 0.99
                summary = "Dislikes"
            else: # Anything 0.60 or below
                summary = "Hates"
        
            # Check for potential refusals
            has_refusals = any(item['score'] < REFUSAL_THRESHOLD for item in items)
        
            # Filter for notable items to display as children
            notable_items = []
            for item in items:
                if item['score'] > NOTABLE_HIGH_THRESHOLD or item['score'] < NOTABLE_LOW_THRESHOLD:
                    notable_items.append({
                        'name': f"{item['tag']} ({item['role']})",
                        'score': item['score']
                    })
                    
            # Only add the orientation if there's something worth showing
            if notable_items or has_refusals:
                preferences_data.append({
                    'orientation': orientation,
                    'summary': summary,
                    'average': avg_score,
                    'has_refusals': has_refusals,
                    'items': sorted(notable_items, key=lambda x: x['score'], reverse=True)
                })

        # Policy requirements
        policy_names = {p['id']: p['name'] for p in self.controller.data_manager.on_set_policies_data.values()}
        required_policies = [policy_names.get(pid, pid) for pid in sorted(talent.policy_requirements.get('requires', []))]
        refused_policies = [policy_names.get(pid, pid) for pid in sorted(talent.policy_requirements.get('refuses', []))]

        self.view.preferences_widget.display_preferences(
            preferences_data=preferences_data,
            limits=sorted(talent.hard_limits),
            required_policies=required_policies,
            refused_policies=refused_policies
        )