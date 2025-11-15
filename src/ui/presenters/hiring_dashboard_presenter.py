import logging
from PyQt6.QtCore import QObject, pyqtSlot
from typing import TYPE_CHECKING, List, Dict

from data.game_state import Talent
from database.db_models import TalentDB
from utils.formatters import get_fuzzed_skill_range
from ui.presenters.talent_filter_cache import TalentFilterCache, CastingTalentCache
from ui.presenters.talent_filter_panel_presenter import TalentFilterPanelPresenter
from ui.presenters.talent_table_presenter import TalentTablePresenter
from ui.presenters.role_details_presenter import RoleDetailsPresenter


if TYPE_CHECKING:
    from core.interfaces import IGameController
    from ui.ui_manager import UIManager
    from ui.windows.hiring_dashboard import HiringDashboardTab

logger = logging.getLogger(__name__)

class HiringDashboardPresenter(QObject):
    """
    Coordinator presenter for the hiring dashboard.
    This presenter instantiates and manages the interactions between the
    filter panel, talent table, and role details presenters. It contains
    the business logic for fetching and filtering talent based on the
    user's selections across all components.
    """
    
    def __init__(self, controller: 'IGameController',
                 ui_manager: 'UIManager',
                 view: 'HiringDashboardTab',
                 parent=None):
        super().__init__(parent)
        self.controller = controller
        self.ui_manager = ui_manager
        self.view = view
        
        # Instantiate child presenters and wire them to their views
        self.filter_presenter = TalentFilterPanelPresenter(
            view=self.view.talent_filter_panel,
            controller=self.controller,
            settings_manager=self.controller.settings_manager,
            parent=self
        )
        self.table_presenter = TalentTablePresenter(
            controller=self.controller,
            view=self.view.talent_table_widget,
            parent=self
        )
        self.role_details_presenter = RoleDetailsPresenter(
            controller=self.controller,
            view=self.view.role_details_widget,
            parent=self
        )
        
        # State
        self.current_scene_id = None
        self.current_vp_id = None
        
        # --- Caching Mechanism ---
        self._all_talents_for_filtering: List[TalentDB] = []
        self._talent_filter_cache: Dict[int, TalentFilterCache] = {}
        self._cache_is_dirty = True

        self._connect_signals()
    
    def _connect_signals(self):
        """Connect signals between presenters and the controller."""
        # Listen for filter changes from the filter panel presenter
        self.filter_presenter.filters_applied.connect(self._on_filters_applied)
        # The coordinator listens to the raw view signal to orchestrate role details
        self.filter_presenter.view.role_selected.connect(self._on_role_selected)

        # Listen for actions from the talent table presenter
        self.table_presenter.open_talent_profile_requested.connect(self._on_open_talent_profile)
        self.table_presenter.filters_changed.connect(self._trigger_filter_application) # For name filter

        # Listen for global game state changes
        self.controller.signals.talent_pool_changed.connect(self._invalidate_filter_cache)

    def refresh(self):
        """
        Loads initial data into the sub-presenters and triggers the initial
        talent list population. This is the main entry point for this presenter.
        """
        self.filter_presenter.load_initial_data()
        self.role_details_presenter.clear()
        self._trigger_filter_application()

    @pyqtSlot()
    def _invalidate_filter_cache(self):
        """Marks the cache as dirty and reloads data when the talent pool changes."""
        self._cache_is_dirty = True
        self.filter_presenter.load_initial_data() 
        self._trigger_filter_application()
        
    @pyqtSlot()
    def _trigger_filter_application(self):
        """Gathers all filters and calls the main filtering logic."""
        all_filters = self.filter_presenter.view.gather_current_filters()
        all_filters['text'] = self.table_presenter.get_name_filter()
        self._on_filters_applied(all_filters)
    
    @pyqtSlot(int, int)
    def _on_role_selected(self, scene_id: int, vp_id: int):
        """Handles role selection, updating details and clearing the table."""
        self.current_scene_id = scene_id if vp_id > -1 else None
        self.current_vp_id = vp_id if vp_id > -1 else None

        if self.current_scene_id and self.current_vp_id:
            self.role_details_presenter.display_role(self.current_scene_id, self.current_vp_id)
        else:
            self.role_details_presenter.clear()

        # Clear table; user must click "Apply" to see new results.
        self.table_presenter.update_data([])
        if not (self.current_scene_id and self.current_vp_id):
            self._trigger_filter_application()
    
    @pyqtSlot(dict)
    def _on_filters_applied(self, filters: dict):
        """Main logic trigger. Decides whether to do a general or role-specific search."""
        if self._cache_is_dirty: self._build_filter_cache()

        scene_id = filters.get('scene_id'); vp_id = filters.get('vp_id')
        if scene_id is not None and vp_id is not None and vp_id > -1:
            self._execute_role_specific_filter(scene_id, vp_id, filters)
        else:
            self._execute_general_filter(filters)

    def _build_filter_cache(self):
        self._all_talents_for_filtering = self.controller.get_filtered_talents({})
        self._talent_filter_cache.clear()
        for t_db in self._all_talents_for_filtering:
            perf = get_fuzzed_skill_range(t_db.performance, t_db.experience, t_db.id)
            act = get_fuzzed_skill_range(t_db.acting, t_db.experience, t_db.id)
            stam = get_fuzzed_skill_range(t_db.stamina, t_db.experience, t_db.id)
            dom = get_fuzzed_skill_range(t_db.dom_skill, t_db.experience, t_db.id)
            sub = get_fuzzed_skill_range(t_db.sub_skill, t_db.experience, t_db.id)
            pop = round(sum(p.score for p in t_db.popularity_scores) if t_db.popularity_scores else 0)
            self._talent_filter_cache[t_db.id] = TalentFilterCache(
                talent_db=t_db,
                perf_range=(perf, perf) if isinstance(perf, int) else perf,
                act_range=(act, act) if isinstance(act, int) else act,
                stam_range=(stam, stam) if isinstance(stam, int) else stam,
                dom_range=(dom, dom) if isinstance(dom, int) else dom,
                sub_range=(sub, sub) if isinstance(sub, int) else sub,
                popularity=pop)
        self._cache_is_dirty = False

    def _talent_passes_cached_skill_filters(self, cache_item: TalentFilterCache, filters: dict) -> bool:
        skill_filters = {
            'performance': cache_item.perf_range, 'acting': cache_item.act_range,
            'stamina': cache_item.stam_range, 'dominance': cache_item.dom_range,
            'submission': cache_item.sub_range}
        for skill, (t_min, t_max) in skill_filters.items():
            u_min, u_max = filters.get(f'{skill}_min', 0), filters.get(f'{skill}_max', 100)
            if not (t_min <= u_max and t_max >= u_min): return False
        return True

    def _execute_general_filter(self, filters: dict):
        """Filters all talent without considering a specific role (no demand)."""
        db_filters = {k: v for k, v in filters.items() if not k.startswith(('performance', 'acting', 'stamina', 'dominance', 'submission'))}
        talents_from_db = self.controller.get_filtered_talents(db_filters)
        cache_items = [
            self._talent_filter_cache[t_db.id] for t_db in talents_from_db
            if t_db.id in self._talent_filter_cache and self._talent_passes_cached_skill_filters(self._talent_filter_cache[t_db.id], filters)
        ]
        self.table_presenter.update_data(cache_items)

    def _execute_role_specific_filter(self, scene_id: int, vp_id: int, filters: dict):
        """Filters talent eligible for a role and calculates demand."""
        base_candidates = self.controller.get_eligible_talent_for_role(scene_id, vp_id)
        attr_filters = {k: v for k, v in filters.items() if not k.startswith(('performance', 'acting', 'stamina', 'dominance', 'submission', 'gender', 'ethnicities'))}
        
        role_details = self.controller.get_role_details_for_ui(scene_id, vp_id)
        role_gender = (role_details.get('gender') or 'any').lower()
        if role_gender == 'female': attr_filters['dick_size_min'] = attr_filters['dick_size_max'] = None
        elif role_gender == 'male' and 'cup_sizes' in attr_filters: del attr_filters['cup_sizes']
            
        attr_filtered = self.controller.filter_talent_list_by_attributes(base_candidates, attr_filters)
        final_dbs = [t_db for t_db in attr_filtered if t_db.id in self._talent_filter_cache and self._talent_passes_cached_skill_filters(self._talent_filter_cache[t_db.id], filters)]

        casting_cache = []
        for t_db in final_dbs:
            base_cache = self._talent_filter_cache[t_db.id]
            _, _, demand = self.controller.calculate_total_demand(t_db.id, scene_id, vp_id)
            casting_cache.append(CastingTalentCache(
                talent_db=t_db, demand=demand,
                perf_range=base_cache.perf_range, act_range=base_cache.act_range,
                stam_range=base_cache.stam_range, dom_range=base_cache.dom_range,
                sub_range=base_cache.sub_range, popularity=base_cache.popularity
            ))
        self.table_presenter.update_data(casting_cache)

    @pyqtSlot(object)
    def _on_open_talent_profile(self, talent: Talent):
        """Handles request from the table presenter to open a talent profile window."""
        self.ui_manager.show_talent_profile(talent)