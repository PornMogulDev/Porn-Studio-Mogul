import logging
from PyQt6.QtCore import QObject, pyqtSlot
from typing import TYPE_CHECKING

from core.interfaces import IGameController
from data.game_state import Talent
from utils.formatters import get_fuzzed_skill_range
from ui.presenters.talent_filter_cache import CastingTalentCache

if TYPE_CHECKING:
    from ui.widgets.hiring_dashboard.scene_role_selector_widget import SceneRoleSelectorWidget
    from ui.widgets.hiring_dashboard.role_details_widget import RoleDetailsWidget
    from ui.widgets.hiring_dashboard.talent_table_widget import HiringTalentTableWidget
    from ui.widgets.hiring_dashboard.talent_profile_widget import HiringTalentProfileWidget

logger = logging.getLogger(__name__)

class HiringDashboardPresenter(QObject):
    """
    Presenter coordinating all hiring dashboard widgets.
    Manages the workflow: scene/role selection -> talent filtering -> hiring.
    """
    
    def __init__(self, controller: IGameController,
                 scene_role_widget: 'SceneRoleSelectorWidget',
                 role_details_widget: 'RoleDetailsWidget',
                 talent_table_widget: 'HiringTalentTableWidget',
                 talent_profile_widget: 'HiringTalentProfileWidget',
                 parent=None):
        super().__init__(parent)
        self.controller = controller
        self.scene_role_widget = scene_role_widget
        self.role_details_widget = role_details_widget
        self.talent_table_widget = talent_table_widget
        self.talent_profile_widget = talent_profile_widget
        
        # Current state
        self.current_scene_id = None
        self.current_vp_id = None
        self._casting_cache = []
        self._filtered_cache = []
        
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect all widget signals."""
        # Scene/Role selection
        self.scene_role_widget.scene_changed.connect(self._on_scene_changed)
        self.scene_role_widget.role_changed.connect(self._on_role_changed)
        self.scene_role_widget.refresh_requested.connect(self.load_initial_data)
        
        # Talent filtering
        self.talent_table_widget.name_filter_changed.connect(self._on_name_filter_changed)
        self.talent_table_widget.additional_filters_changed.connect(self._on_additional_filters_changed)
        self.talent_table_widget.talent_selected.connect(self._on_talent_selected)
        
        # Hiring
        self.talent_profile_widget.hire_requested.connect(self._on_hire_requested)
        
        # Controller signals
        self.controller.signals.scenes_changed.connect(self.load_initial_data)
    
    def load_initial_data(self):
        """Load scenes available for casting."""
        scenes = self.controller.get_castable_scenes()
        self.scene_role_widget.populate_scenes(scenes)
        
        # Initialize talent table model
        self.talent_table_widget.initialize_model(
            self.controller.get_available_cup_sizes()
        )
    
    @pyqtSlot(int)
    def _on_scene_changed(self, scene_id: int):
        """Handle scene selection change."""
        self.current_scene_id = scene_id
        self.current_vp_id = None
        
        # Load uncast roles for this scene
        roles = self.controller.get_uncast_roles_for_scene(scene_id)
        self.scene_role_widget.populate_roles(roles)
        
        # Clear other widgets
        self.role_details_widget.clear()
        self.talent_table_widget.update_talent_table([])
        self.talent_profile_widget.clear()
        self._casting_cache = []
        self._filtered_cache = []
    
    @pyqtSlot(int, int)
    def _on_role_changed(self, scene_id: int, vp_id: int):
        """Handle role selection change."""
        self.current_scene_id = scene_id
        self.current_vp_id = vp_id
        
        # Load role details
        self._load_role_details()
        
        # Load eligible talent
        self._load_eligible_talent()
        
        # Clear talent profile
        self.talent_profile_widget.clear()
    
    def _load_role_details(self):
        """Load and display role details."""
        role_details = self.controller.get_role_details_for_ui(
            self.current_scene_id, self.current_vp_id
        )
        
        # Build HTML (same as RoleCastingPresenter)
        html = "<ul>"
        html += f"<li><b>Gender:</b> {role_details.get('gender', 'N/A')}</li>"
        html += f"<li><b>Ethnicity:</b> {role_details.get('ethnicity', 'N/A')}</li>"
        if role_details.get('is_protagonist'): 
            html += "<li><b>Protagonist Role</b></li>"
        if role_details.get('disposition') != 'Switch': 
            html += f"<li><b>Disposition:</b> {role_details.get('disposition', 'N/A')}</li>"

        if physical_tags := role_details.get('physical_tags'): 
            html += f"<br><li><b>Physical Tags:</b><br>{', '.join(physical_tags)}</li>"
        if action_roles := role_details.get('action_roles'): 
            html += f"<br><li><b>Action Roles:</b><br>{', '.join(action_roles)}</li>"
        html += "</ul>"
        
        self.role_details_widget.update_role_details(html)
    
    def _load_eligible_talent(self):
        """Load eligible talent for the selected role."""
        try:
            # Get all TalentDB objects who are eligible and willing
            eligible_talents_db = self.controller.get_eligible_talent_for_role(
                self.current_scene_id, self.current_vp_id
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
                    t_db.id, self.current_scene_id, self.current_vp_id
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

            # Apply initial filters and update table
            self._apply_all_filters()
            
        except Exception as e:
            logger.error(f"Error loading eligible talent: {e}", exc_info=True)
            self._casting_cache = []
            self._filtered_cache = []
            self.talent_table_widget.update_talent_table([])
    
    def _apply_all_filters(self):
        """Apply all current filters to the talent cache."""
        filters = self.talent_table_widget.get_current_filters()
        
        # Start with full cache
        filtered = self._casting_cache.copy()
        
        # Apply name filter
        name_filter = filters.get('name', '').strip().lower()
        if name_filter:
            filtered = [
                cache_item for cache_item in filtered
                if name_filter in cache_item.talent_db.alias.lower()
            ]
        
        # Apply age filter
        age_min = filters.get('age_min', 18)
        age_max = filters.get('age_max', 99)
        if age_min > 18 or age_max < 99:
            filtered = [
                cache_item for cache_item in filtered
                if age_min <= cache_item.talent_db.age <= age_max
            ]
        
        # Apply go-to list filter
        if filters.get('go_to_list_only', False):
            # Filter to only show talent in go-to lists
            filtered = [
                cache_item for cache_item in filtered
                if self.controller.is_talent_in_go_to_list(cache_item.talent_db.id)
            ]
        
        self._filtered_cache = filtered
        self.talent_table_widget.update_talent_table(self._filtered_cache)
    
    @pyqtSlot(str)
    def _on_name_filter_changed(self, text: str):
        """Handle name filter change."""
        if self._casting_cache:
            self._apply_all_filters()
    
    @pyqtSlot(dict)
    def _on_additional_filters_changed(self, filters: dict):
        """Handle additional filter changes."""
        if self._casting_cache:
            self._apply_all_filters()
    
    @pyqtSlot(object)
    def _on_talent_selected(self, talent: Talent):
        """Handle talent selection from table."""
        # Find the cached demand for this talent
        cache_item = next(
            (c for c in self._filtered_cache if c.talent_db.id == talent.id), 
            None
        )
        
        if cache_item:
            # Convert to Talent dataclass and display
            talent_dataclass = cache_item.talent_db.to_dataclass(Talent)
            self.talent_profile_widget.display_talent(talent_dataclass, cache_item.demand)
    
    @pyqtSlot(object)
    def _on_hire_requested(self, talent: Talent):
        """Handle hiring request for talent."""
        try:
            # Find the cached demand for this talent
            cache_item = next(
                (c for c in self._filtered_cache if c.talent_db.id == talent.id), 
                None
            )
            
            if cache_item:
                cost = cache_item.demand
            else:
                _, _, cost = self.controller.calculate_total_demand(
                    talent.id, self.current_scene_id, self.current_vp_id
                )
            
            # Perform the hiring
            self.controller.cast_talent_for_virtual_performer(
                talent.id, self.current_scene_id, self.current_vp_id, cost
            )
            
            # Refresh data after successful hire
            self._on_role_changed(self.current_scene_id, self.current_vp_id)
            
        except Exception as e:
            logger.error(f"Error hiring talent {talent.id}: {e}", exc_info=True)
    
    def refresh(self):
        """Refresh all data."""
        self.load_initial_data()
        if self.current_scene_id and self.current_vp_id:
            self._on_role_changed(self.current_scene_id, self.current_vp_id)