import logging
from typing import TYPE_CHECKING
from collections import defaultdict
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from data.game_state import Talent
from core.interfaces import IGameController
from ui.windows.talent_profile_window import TalentProfileWindow

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
        self.view.history_widget.open_scene_dialog_requested.connect(self.uimanager.show_scene_planner)
        
        # Connect to global signals to stay up-to-date
        self.controller.signals.scenes_changed.connect(self.refresh_available_roles)
        self.controller.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

    def open_talent(self, talent: Talent):
        """Opens a talent in the window, creating a new tab if necessary."""
        if talent.id in self.open_talents:
            # If talent is already open, just switch to it.
            # The switch_to_talent method has a guard to prevent redundant reloads,
            # but it will ensure the view is updated if needed.
            self.switch_to_talent(talent.id)
            # We still need to ensure the correct tab is selected visually.
            self.view.set_active_talent_tab(talent.id) # This just updates the UI.
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
        
        # Affinities
        affinities = {tag: affinity for tag, affinity in talent.tag_affinities.items() if affinity > 0}
        self.view.affinities_widget.display_affinities(sorted(affinities.items()))
        
        # Preferences & Requirements
        self._load_and_display_preferences(talent)
        
        # Scene History & Chemistry
        history = self.controller.get_scene_history_for_talent(talent.id)
        self.view.history_widget.display_scene_history(history, talent.id)
        
        chemistry = self.controller.talent_service.get_talent_chemistry(talent.id)
        self.view.chemistry_widget.display_chemistry(chemistry)

        # Hiring Tab
        self.refresh_available_roles()

    def _load_and_display_details(self, talent: Talent):
        self.view.details_widget.display_basic_info({
            'age': talent.age,
            'gender': talent.gender,
            'orientation': talent.orientation_score,
            'ethnicity': talent.ethnicity,
            'popularity': sum(talent.popularity.values()),
        })
        self.view.details_widget.display_skills({
            'performance': talent.performance,
            'acting': talent.acting,
            'stamina': talent.stamina,
            'ambition': talent.ambition,
            'professionalism': talent.professionalism
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
        tag_definitions = self.controller.data_manager.tag_definitions
        
        avg_prefs_by_tag = {
            tag: sum(roles.values()) / len(roles)
            for tag, roles in talent.tag_preferences.items() if roles
        }
        
        prefs_by_orientation = defaultdict(dict)
        prefs_by_concept = defaultdict(dict)
        
        for tag, avg_score in avg_prefs_by_tag.items():
            tag_def = tag_definitions.get(tag)
            if not tag_def: continue
            
            if orientation := tag_def.get('orientation'):
                prefs_by_orientation[orientation][tag] = avg_score
            if concept := tag_def.get('concept'):
                prefs_by_concept[concept][tag] = avg_score

        likes, dislikes, processed_tags = [], [], set()
        DISLIKE_THRESHOLD, LIKE_THRESHOLD, EXCEPTION_DEVIATION = 0.8, 1.2, 0.2

        for orientation, tags_with_scores in prefs_by_orientation.items():
            scores = list(tags_with_scores.values())
            if scores and all(score < DISLIKE_THRESHOLD for score in scores):
                dislikes.append(f"{orientation} scenes")
                processed_tags.update(tags_with_scores.keys())

        for concept, tags_with_scores in prefs_by_concept.items():
            unprocessed = {tag: score for tag, score in tags_with_scores.items() if tag not in processed_tags}
            if not unprocessed: continue
            
            scores = list(unprocessed.values())
            avg_score = sum(scores) / len(scores)
            is_like, is_dislike = avg_score >= LIKE_THRESHOLD, avg_score <= DISLIKE_THRESHOLD
            
            if is_like or is_dislike:
                summary = f"{concept} scenes (~{avg_score:.2f})"; (likes if is_like else dislikes).append(summary)
                for tag, score in unprocessed.items():
                    if abs(score - avg_score) > EXCEPTION_DEVIATION:
                        roles = ", ".join([f"{r}: {p:.2f}" for r, p in sorted(talent.tag_preferences[tag].items())])
                        exception = f"  • Except: {tag} ({roles})"; (likes if score > avg_score else dislikes).append(exception)
                processed_tags.update(unprocessed.keys())

        for tag, avg_score in avg_prefs_by_tag.items():
            if tag in processed_tags: continue
            if avg_score >= LIKE_THRESHOLD or avg_score <= DISLIKE_THRESHOLD:
                roles = ", ".join([f"{r}: {p:.2f}" for r, p in sorted(talent.tag_preferences[tag].items())])
                display = f"{tag} ({roles})"; (likes if avg_score >= LIKE_THRESHOLD else dislikes).append(display)

        # Policy requirements
        policy_names = {p['id']: p['name'] for p in self.controller.data_manager.on_set_policies_data.values()}
        required_policies = [policy_names.get(pid, pid) for pid in sorted(talent.policy_requirements.get('requires', []))]
        refused_policies = [policy_names.get(pid, pid) for pid in sorted(talent.policy_requirements.get('refuses', []))]

        self.view.preferences_widget.display_preferences(
            likes=sorted(likes),
            dislikes=sorted(dislikes),
            limits=sorted(talent.hard_limits),
            required_policies=required_policies,
            refused_policies=refused_policies
        )