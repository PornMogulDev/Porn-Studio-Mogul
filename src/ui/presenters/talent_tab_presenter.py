from typing import Union, List, Dict, TYPE_CHECKING, Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSlot, QPoint, QRunnable, QThreadPool, pyqtSignal

from core.interfaces import IGameController
from ui.tabs.talent_tab import TalentTab
from ui.widgets.talent_filter_widget import TalentFilterWidget
from data.game_state import Talent, Scene
from database.db_models import TalentDB
from utils.formatters import get_fuzzed_skill_range
from ui.presenters.talent_filter_cache import TalentFilterCache, CastingTalentCache
from ui.presenters.role_details_presenter import RoleDetailsPresenter
from ui.builders.scene_summary_builder import prepare_summary_data

if TYPE_CHECKING:
    from ui.managers.ui_manager import UIManager
    from ui.managers.icon_manager import IconManager

# --- Asynchronous Worker for Demand Calculation ---
class WorkerSignals(QObject):
    """Defines signals available from a running worker thread."""
    finished = pyqtSignal(dict) # dict will be {talent_id: demand_cost}

class DemandCalculationWorker(QRunnable):
    """Worker thread for calculating talent demands without freezing the UI."""
    def __init__(self, controller: IGameController, talents_data: List[Talent], scene_data: Scene, vp_id: int, talent_locations: Dict[int, str]):
        super().__init__()
        self.controller = controller
        self.talents = talents_data
        self.scene = scene_data
        self.vp_id = vp_id
        self.talent_locations = talent_locations
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        # This worker is now "dumb". It receives all data and just calls the calculator.
        demands = {}
        game_state = self.controller.game_state
        for talent in self.talents:
            effective_location = self.talent_locations.get(talent.id, talent.base_location)
            cost_breakdown = self.controller.talent_demand_calculator.calculate_total_demand(
                talent, self.scene, self.vp_id, effective_location, game_state.absolute_week
            )
            demands[talent.id] = cost_breakdown['total_cost']
        self.signals.finished.emit(demands)

class TalentTabPresenter(QObject):
    def __init__(self, controller: IGameController, view: TalentTab, ui_manager: 'UIManager', icon_manager: 'IconManager', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager
        self.icon_manager = icon_manager
        
        self.view.presenter = self

        # --- Thread Pool for Background Tasks ---
        self.thread_pool = QThreadPool()

        # --- Sub-presenter for Role Details ---
        self.role_details_presenter = RoleDetailsPresenter(self.controller, self.view.role_details_widget, parent=self)
        
        # --- Caching Mechanism ---
        self._all_talents_for_filtering: List[TalentDB] = []
        self._talent_filter_cache: Dict[int, TalentFilterCache] = {}
        self._demand_cache: Dict[int, int] = {}
        self._current_casting_context: Optional[Tuple[int, int]] = None # (scene_id, vp_id)
        self._cache_is_dirty = True
        self._is_casting_mode = False
        
        self._filter_sequence_id = 0

        # --- Initialize Filter Widget ---
        self.filter_widget = TalentFilterWidget(
            controller=self.controller,
            ethnicities_hierarchy=self.controller.get_ethnicity_hierarchy(),
            cup_sizes=self.controller.get_available_cup_sizes(),
            nationalities=self.controller.get_available_nationalities(),
            locations_by_region=self.controller.get_locations_by_region(),
            go_to_categories=self.controller.get_go_to_list_categories(),
            current_filters={},
            settings_manager=self.controller.settings_manager,
            icon_manager=self.icon_manager,
            parent=self.view
        )
        # Inject the widget into the view's layout
        self.view.set_filter_widget(self.filter_widget)

        self._connect_signals()
        
        self.view.create_model_and_load(
            self.controller.settings_manager,
            self.icon_manager,
            self.ui_manager,
            self.controller.get_available_cup_sizes()
        )

    def _connect_signals(self):
        self.controller.signals.talent_pool_changed.connect(self._invalidate_filter_cache)
        self.controller.signals.go_to_categories_changed.connect(self.view.refresh_from_state)
        self.controller.signals.go_to_list_changed.connect(self.view.refresh_from_state)
        self.controller.settings_manager.signals.setting_changed.connect(self.on_setting_changed)
        
        # View Signals
        self.view.initial_load_requested.connect(self.view.refresh_from_state)
        self.view.standard_filters_changed.connect(self.on_filters_changed)
        self.view.context_menu_requested.connect(self.on_context_menu_requested)
        self.view.add_talent_to_category_requested.connect(self.controller.add_talents_to_go_to_category)
        self.view.remove_talent_from_category_requested.connect(self.controller.remove_talents_from_go_to_category)
        self.view.open_talent_profile_requested.connect(self.on_open_talent_profile)
        self.view.help_requested.connect(self.on_help_requested)
        
        # Internal Handler for table hover
        self.view.smart_hover_entered.connect(self._on_table_hover)
        self.view.smart_hover_left.connect(self.ui_manager.hide_talent_summary)

    @pyqtSlot(object, QPoint)
    def _on_table_hover(self, data_obj, pos: QPoint):
        """Extracts the ID from the table model's data object and shows summary."""
        talent_id = None
        if hasattr(data_obj, 'talent_db'):
            talent_id = data_obj.talent_db.id
        elif hasattr(data_obj, 'id'):
            talent_id = data_obj.id
            
        if talent_id:
            self.ui_manager.show_talent_summary(talent_id, pos)

    def _update_casting_ui_state(self, scene_id: int, vp_id: int):
        """
        Manages the visibility and content of the Left Info Panel and Demand Column
        based on the current casting context and user settings.
        """
        if self._is_casting_mode and scene_id and vp_id:
            # 1. Update Layout Visibility
            show_role = self.controller.settings_manager.get_setting("casting_mode_show_role_details", True)
            show_summary = self.controller.settings_manager.get_setting("casting_mode_show_scene_summary", True)
            
            self.view.configure_info_panel(show_role, show_summary)
            self.view.set_info_panel_visible(show_role or show_summary)
            
            # 2. Update Content
            # Role Details
            self.role_details_presenter.display_role(scene_id, vp_id)
            
            # Scene Summary
            if scene := self.controller.get_scene_by_id(scene_id):
                summary_data = prepare_summary_data(scene, self.controller)
                self.view.update_scene_summary(summary_data)
                
        else:
            # Reset to browsing mode
            self.view.set_info_panel_visible(False)
            self.view.clear_role_details()
            self.role_details_presenter.clear()

        # 4. Update Demand Column (Always runs)
        self._update_demand_column()

    def _update_demand_column(self):
        """
        Enforces the rule: Demand column is visible ONLY if 
        User wants it (pref) AND we are in Casting Mode.
        """
        user_wants_it = self.controller.settings_manager.get_setting("demand_column_user_preference", True)
        should_show = user_wants_it and self._is_casting_mode
        self.view.set_demand_column_visible(should_show)

    @pyqtSlot()
    def _invalidate_filter_cache(self):
        self._cache_is_dirty = True
        self.view.refresh_from_state()

    def _build_filter_cache(self):
        self._all_talents_for_filtering = self.controller.get_filtered_talents({})
        self._talent_filter_cache.clear()

        for t_db in self._all_talents_for_filtering:
            perf_fuzzed = get_fuzzed_skill_range(t_db.performance, t_db.experience, t_db.id)
            act_fuzzed = get_fuzzed_skill_range(t_db.acting, t_db.experience, t_db.id)
            stam_fuzzed = get_fuzzed_skill_range(t_db.stamina, t_db.experience, t_db.id)
            dom_fuzzed = get_fuzzed_skill_range(t_db.dom_skill, t_db.experience, t_db.id)
            sub_fuzzed = get_fuzzed_skill_range(t_db.sub_skill, t_db.experience, t_db.id)
            popularity = round(sum(p.score for p in t_db.popularity_scores) if t_db.popularity_scores else 0)

            self._talent_filter_cache[t_db.id] = TalentFilterCache(
                talent_db=t_db,
                perf_range=(perf_fuzzed, perf_fuzzed) if isinstance(perf_fuzzed, int) else perf_fuzzed,
                act_range=(act_fuzzed, act_fuzzed) if isinstance(act_fuzzed, int) else act_fuzzed,
                stam_range=(stam_fuzzed, stam_fuzzed) if isinstance(stam_fuzzed, int) else stam_fuzzed,
                dom_range=(dom_fuzzed, dom_fuzzed) if isinstance(dom_fuzzed, int) else dom_fuzzed,
                sub_range=(sub_fuzzed, sub_fuzzed) if isinstance(sub_fuzzed, int) else sub_fuzzed,
                popularity=popularity,
                effective_location=t_db.current_location
            )
        self._cache_is_dirty = False

    def _talent_passes_cached_skill_filters(self, cache_item: TalentFilterCache, filters: dict) -> bool:
        user_min_perf, user_max_perf = filters.get('performance_min', 0), filters.get('performance_max', 100)
        talent_min_perf, talent_max_perf = cache_item.perf_range
        if not (talent_min_perf <= user_max_perf and talent_max_perf >= user_min_perf): return False
        
        user_min_act, user_max_act = filters.get('acting_min', 0), filters.get('acting_max', 100)
        talent_min_act, talent_max_act = cache_item.act_range
        if not (talent_min_act <= user_max_act and talent_max_act >= user_min_act): return False
        
        user_min_stam, user_max_stam = filters.get('stamina_min', 0), filters.get('stamina_max', 100)
        talent_min_stam, talent_max_stam = cache_item.stam_range
        if not (talent_min_stam <= user_max_stam and talent_max_stam >= user_min_stam): return False
        
        user_min_dom, user_max_dom = filters.get('dominance_min', 0), filters.get('dominance_max', 100)
        talent_min_dom, talent_max_dom = cache_item.dom_range
        if not (talent_min_dom <= user_max_dom and talent_max_dom >= user_min_dom): return False
        
        user_min_sub, user_max_sub = filters.get('submission_min', 0), filters.get('submission_max', 100)
        talent_min_sub, talent_max_sub = cache_item.sub_range
        if not (talent_min_sub <= user_max_sub and talent_max_sub >= user_min_sub): return False
        return True
    
    @pyqtSlot(str)
    def on_setting_changed(self, key: str):
        if key in ('unit_system', 'font_size'): 
            self.view.talent_model.refresh()
        
        # Handle Casting Mode UI Preference Changes
        elif key in ('casting_mode_show_role_details', 'casting_mode_show_scene_summary', 'demand_column_user_preference'):
            # Re-run the UI state update to reflect new settings immediately
            if self._current_casting_context:
                self._update_casting_ui_state(*self._current_casting_context)
            else:
                self._update_demand_column()

    @pyqtSlot(dict)
    def on_filters_changed(self, all_filters: dict):
        self._filter_sequence_id += 1
        current_seq_id = self._filter_sequence_id

        if self._cache_is_dirty: self._build_filter_cache()

        scene_id = all_filters.get('scene_id')
        vp_id = all_filters.get('vp_id')
        
        # Determine Mode
        new_is_casting = (scene_id is not None and vp_id is not None and vp_id > -1)
        
        # Check if we are transitioning INTO casting mode (or changing roles within it)
        mode_changed = (self._is_casting_mode != new_is_casting)
        self._is_casting_mode = new_is_casting
        
        # Update Context
        new_context = (scene_id, vp_id) if new_is_casting else None
        
        # Clear cache if context changed
        if self._current_casting_context != new_context:
            self._demand_cache.clear()
            self._current_casting_context = new_context
            
        # Update Sidebar/Layout state
        self._update_casting_ui_state(scene_id, vp_id)

        if new_is_casting:
            # --- PATH A: Role-Specific Filtering ---
            
            # Separate attributes that can be filtered in SQL from skills that are fuzzy/in-memory
            attribute_filters = {k: v for k, v in all_filters.items() if not k.startswith(('performance', 'acting', 'stamina', 'dominance', 'submission', 'gender', 'ethnicities'))}
            
            # Role Logic: Handle Gender/Cup size filters based on role requirements
            role_details = self.controller.get_role_details_for_ui(scene_id, vp_id)
            if (role_gender := (role_details.get('gender') or 'any').lower()) == 'female':
                attribute_filters['dick_size_min'] = None; attribute_filters['dick_size_max'] = None
            elif role_gender == 'male' and 'cup_sizes' in attribute_filters: 
                del attribute_filters['cup_sizes']
            
            # Perform optimized DB fetch with attribute filters applied
            base_candidates_db = self.controller.get_eligible_talent_for_role(scene_id, vp_id, attribute_filters)

            # Pre-fetch scene data.
            scene_dc = self.controller.get_scene_by_id(scene_id)
            if not scene_dc:
                self.view.update_talent_list([])
                return
            
            # --- Step 1: Pre-filter talents and pre-fetch all necessary location data ---
            talents_passing_skills_db = [
                t_db for t_db in base_candidates_db 
                if (filter_cache_item := self._talent_filter_cache.get(t_db.id)) and self._talent_passes_cached_skill_filters(filter_cache_item, all_filters)
            ]
            all_relevant_ids = [t_db.id for t_db in talents_passing_skills_db]
            
            talent_locations = self.controller.get_effective_locations_for_multiple_talents(
                all_relevant_ids, scene_dc.scheduled_absolute_week
            )
            
            # --- Step 2: Apply effective location filter ---
            if effective_location_filters := all_filters.get('effective_locations'):
                talents_passing_skills_db = [
                    t_db for t_db in talents_passing_skills_db
                    if talent_locations.get(t_db.id) in effective_location_filters
                ]

            # --- Step 3: Build list using cached demands ---
            final_cache_items = []
            talent_ids_to_calculate = []
            for t_db in talents_passing_skills_db:
                filter_cache_item = self._talent_filter_cache.get(t_db.id)
                if filter_cache_item:
                    cached_demand = self._demand_cache.get(t_db.id)
                    filter_cache_item.effective_location = talent_locations.get(t_db.id, t_db.base_location)
                    final_cache_items.append(CastingTalentCache(**filter_cache_item.__dict__, demand=cached_demand))
                    if cached_demand is None:
                        talent_ids_to_calculate.append(t_db.id)
            
            self.view.update_talent_list(final_cache_items)

            # --- Step 4: Background Calc ---
            if talent_ids_to_calculate:
                talents_to_calc = self.controller.get_multiple_talents_by_ids(talent_ids_to_calculate)
                worker = DemandCalculationWorker(self.controller, talents_to_calc, scene_dc, vp_id, talent_locations)
                worker.signals.finished.connect(lambda res: self._on_demand_calculation_finished(res, current_seq_id))
                self.thread_pool.start(worker)
        else:
            # --- PATH B: Standard Filtering ---
            db_filters = {k: v for k, v in all_filters.items() if not k.startswith(('performance', 'acting', 'stamina', 'dominance', 'submission'))}
            effective_location_filters = db_filters.pop('effective_locations', [])
            talents_from_db = self.controller.get_filtered_talents(db_filters)

            cache_items_passing_skills = []
            for t_db in talents_from_db:
                filter_cache_item = self._talent_filter_cache.get(t_db.id)
                if filter_cache_item and self._talent_passes_cached_skill_filters(filter_cache_item, all_filters):
                    filter_cache_item.effective_location = t_db.current_location
                    if effective_location_filters and filter_cache_item.effective_location not in effective_location_filters:
                        continue
                    cache_items_passing_skills.append(filter_cache_item)
            self.view.update_talent_list(cache_items_passing_skills)

    @pyqtSlot(dict)
    def _on_demand_calculation_finished(self, demands: dict, seq_id: int):
        """Slot to receive results from the background worker and update the model."""
        if seq_id != self._filter_sequence_id:
            return

        self._demand_cache.update(demands)

        model_data = self.view.talent_model.raw_data
        for item in model_data:
            if isinstance(item, CastingTalentCache):
                if item.demand is None:
                    item.demand = demands.get(item.talent_db.id)
        
        self.view.talent_model.refresh()

    @pyqtSlot(list, QPoint)
    def on_context_menu_requested(self, talents: List[Talent], pos: QPoint):
        self.view.display_talent_context_menu(talents, self.controller.get_go_to_list_categories(), pos)

    @pyqtSlot(object)
    def on_open_talent_profile(self, talent_data: Union[Talent, TalentDB, TalentFilterCache, CastingTalentCache]):
        if hasattr(talent_data, 'talent_db'):
            talent_data = talent_data.talent_db
        if isinstance(talent_data, TalentDB): 
            talent_data = talent_data.to_dataclass(Talent)
        self.ui_manager.show_talent_profile(talent_data)

    @pyqtSlot(str)
    def on_help_requested(self, topic_key: str):
        self.ui_manager.show_help(topic_key)