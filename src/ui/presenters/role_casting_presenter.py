from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QDialog
from typing import TYPE_CHECKING, List

from core.interfaces import IGameController
from data.game_state import Talent
from utils.formatters import get_fuzzed_skill_range
from ui.presenters.talent_filter_cache import CastingTalentCache

if TYPE_CHECKING:
    from ui.dialogs.role_casting_dialog import RoleCastingDialog

class RoleCastingPresenter(QObject):
    def __init__(self, controller: IGameController, view: 'RoleCastingDialog', scene_id: int, vp_id: int):
        super().__init__(view) # Ensure presenter is child of view for lifecycle management
        self.controller = controller
        self.view = view
        self.scene_id = scene_id
        self.vp_id = vp_id

        self._casting_cache: List[CastingTalentCache] = []
        self._connect_signals()
        self._load_initial_data()

    def _connect_signals(self):
        self.view.name_filter_changed.connect(self._on_name_filter_changed)
        self.view.hire_requested.connect(self._on_hire_requested)
    
    def _load_initial_data(self):
        """Loads eligible talents and builds a cache with pre-calculated fuzzing and demand."""
        # Get all TalentDB objects who are eligible and willing
        eligible_talents_db = self.controller.get_eligible_talent_for_role(
             self.scene_id, self.vp_id
         )
        
        # Build CastingTalentCache objects with all pre-calculated values
        self._casting_cache = []
        for t_db in eligible_talents_db:
            # Calculate all 5 fuzzed skill ranges
            perf_fuzzed = get_fuzzed_skill_range(t_db.performance, t_db.experience, t_db.id)
            act_fuzzed = get_fuzzed_skill_range(t_db.acting, t_db.experience, t_db.id)
            stam_fuzzed = get_fuzzed_skill_range(t_db.stamina, t_db.experience, t_db.id)
            dom_fuzzed = get_fuzzed_skill_range(t_db.dom_skill, t_db.experience, t_db.id)
            sub_fuzzed = get_fuzzed_skill_range(t_db.sub_skill, t_db.experience, t_db.id)
            
            # Pre-calculate popularity
            popularity = round(sum(p.score for p in t_db.popularity_scores) if t_db.popularity_scores else 0)
            
            # Calculate role-specific demand
            _, _, demand = self.controller.calculate_total_demand(
                t_db.id, self.scene_id, self.vp_id
            )
            
            cache_item = CastingTalentCache(
                talent_db=t_db,
                perf_range=(perf_fuzzed, perf_fuzzed) if isinstance(perf_fuzzed, int) else perf_fuzzed,
                act_range=(act_fuzzed, act_fuzzed) if isinstance(act_fuzzed, int) else act_fuzzed,
                stam_range=(stam_fuzzed, stam_fuzzed) if isinstance(stam_fuzzed, int) else stam_fuzzed,
                dom_range=(dom_fuzzed, dom_fuzzed) if isinstance(dom_fuzzed, int) else dom_fuzzed,
                sub_range=(sub_fuzzed, sub_fuzzed) if isinstance(sub_fuzzed, int) else sub_fuzzed,
                popularity=popularity,
                demand=demand
            )
            self._casting_cache.append(cache_item)

        self._load_role_details()
        self.view.update_talent_table(self._casting_cache)

    def _load_role_details(self):
        role_details = self.controller.get_role_details_for_ui(self.scene_id, self.vp_id)
        html = "<ul>"
        html += f"<li><b>Gender:</b> {role_details.get('gender', 'N/A')}</li>"
        html += f"<li><b>Ethnicity:</b> {role_details.get('ethnicity', 'N/A')}</li>"
        if role_details.get('is_protagonist'): html += "<li><b>Protagonist Role</b></li>"
        if role_details.get('disposition') != 'Switch': html += f"<li><b>Disposition:</b> {role_details.get('disposition', 'N/A')}</li>"

        if physical_tags := role_details.get('physical_tags'): html += f"<br><li><b>Physical Tags:</b><br>{', '.join(physical_tags)}</li>"
        if action_roles := role_details.get('action_roles'): html += f"<br><li><b>Action Roles:</b><br>{', '.join(action_roles)}</li>"
        html += "</ul>"
        self.view.update_role_details(html)

    @pyqtSlot(str)
    def _on_name_filter_changed(self, text: str):
        """Filters the cached talent list by name."""
        text_lower = text.lower()
        if not text_lower:
            self.view.update_talent_table(self._casting_cache)
            return
        
        filtered_cache = [
            cache_item for cache_item in self._casting_cache
            if text_lower in cache_item.talent_db.alias.lower()
        ]
        self.view.update_talent_table(filtered_cache)
        
    @pyqtSlot(object)
    def _on_hire_requested(self, talent: Talent):
        """Handles hiring - finds the cached demand instead of recalculating."""
        # Find the cached demand for this talent
        cache_item = next((c for c in self._casting_cache if c.talent_db.id == talent.id), None)
        if cache_item:
            cost = cache_item.demand
        else:
            _, _, cost = self.controller.calculate_total_demand(talent.id, self.scene_id, self.vp_id)
        self.controller.cast_talent_for_virtual_performer(talent.id, self.scene_id, self.vp_id, cost)
        self.view.accept()