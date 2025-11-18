from typing import Union, List, Dict, TYPE_CHECKING, Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSlot, QPoint, QRunnable, QThreadPool, pyqtSignal

from core.interfaces import IGameController
from ui.tabs.talent_tab import TalentTab
from ui.dialogs.talent_filter_dialog import TalentFilterDialog
from data.game_state import Talent, Scene
from database.db_models import TalentDB
from utils.formatters import get_fuzzed_skill_range
from ui.presenters.talent_filter_cache import TalentFilterCache, CastingTalentCache
from ui.presenters.role_details_presenter import RoleDetailsPresenter

if TYPE_CHECKING:
    from ui.ui_manager import UIManager

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
                talent, self.scene, self.vp_id, effective_location, game_state.week, game_state.year
            )
            demands[talent.id] = cost_breakdown['total_cost']
        self.signals.finished.emit(demands)

class TalentTabPresenter(QObject):
    def __init__(self, controller: IGameController, view: TalentTab, ui_manager: 'UIManager'):
        super().__init__()
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager
        self.filter_dialog = None

        self.view.presenter = self

        # --- Thread Pool for Background Tasks ---
        self.thread_pool = QThreadPool()

        # --- Sub-presenter for Role Details ---
        self.role_details_presenter = RoleDetailsPresenter(self.controller, self.view.role_details_widget, parent=self)
        
        # --- Caching Mechanism ---
        self._all_talents_for_filtering: List[TalentDB] = []
        self._talent_filter_cache: Dict[int, TalentFilterCache] = {}
        # Role-specific cache for calculated demands to prevent re-calculation on sub-filters
        self._demand_cache: Dict[int, int] = {}
        self._current_casting_context: Optional[Tuple[int, int]] = None # (scene_id, vp_id)
        self._cache_is_dirty = True

        self._connect_signals()
        self.view.create_model_and_load(
            self.controller.settings_manager,
            self.controller.get_available_cup_sizes()
        )

    def _connect_signals(self):
        self.controller.signals.talent_pool_changed.connect(self._invalidate_filter_cache)
        self.controller.signals.go_to_categories_changed.connect(self.view.refresh_from_state)
        self.controller.signals.go_to_list_changed.connect(self.view.refresh_from_state)
        self.controller.settings_manager.signals.setting_changed.connect(self.on_setting_changed)
        self.view.initial_load_requested.connect(self.view.refresh_from_state)
        self.view.standard_filters_changed.connect(self.on_filters_changed)
        self.view.context_menu_requested.connect(self.on_context_menu_requested)
        self.view.add_talent_to_category_requested.connect(self.controller.add_talents_to_go_to_category)
        self.view.remove_talent_from_category_requested.connect(self.controller.remove_talents_from_go_to_category)
        self.view.open_advanced_filters_requested.connect(self.on_open_advanced_filters)
        self.view.open_talent_profile_requested.connect(self.on_open_talent_profile)
        self.view.help_requested.connect(self.on_help_requested)

    def _stop_casting_mode(self):
        """Resets the tab from casting mode back to its general browsing state."""

        self.role_details_presenter.clear()
        self.view.set_role_details_panel_visible(False)

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
                effective_location=t_db.current_location # Default "smart" location is current location
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
        if key == 'unit_system': self.view.talent_model.refresh()

    @pyqtSlot(dict)
    def on_filters_changed(self, all_filters: dict):
        if self._cache_is_dirty: self._build_filter_cache()

        scene_id = all_filters.get('scene_id')
        vp_id = all_filters.get('vp_id')

        if scene_id is not None and vp_id is not None and vp_id > -1:
            # --- PATH A: Role-Specific Filtering ---
            self.role_details_presenter.display_role(scene_id, vp_id) # Update the details panel
            self.view.set_role_details_panel_visible(True) # Show the panel

            base_candidates_db = self.controller.get_eligible_talent_for_role(scene_id, vp_id)
            attribute_filters = {k: v for k, v in all_filters.items() if not k.startswith(('performance', 'acting', 'stamina', 'dominance', 'submission', 'gender', 'ethnicities'))}
            role_details = self.controller.get_role_details_for_ui(scene_id, vp_id)
            if (role_gender := (role_details.get('gender') or 'any').lower()) == 'female':
                attribute_filters['dick_size_min'] = None; attribute_filters['dick_size_max'] = None
            elif role_gender == 'male' and 'cup_sizes' in attribute_filters: del attribute_filters['cup_sizes']
            
            attribute_filtered_db = self.controller.filter_talent_list_by_attributes(base_candidates_db, attribute_filters)

            # --- Orchestration Step 1: Prepare data for the worker ---
            new_context = (scene_id, vp_id)
            if self._current_casting_context != new_context:
                self._demand_cache.clear()
                self._current_casting_context = new_context

            # Pre-fetch scene data.
            scene_dc = self.controller.get_scene_by_id(scene_id)
            if not scene_dc:
                self.view.update_talent_list([])
                return
            
            # --- Step 1.5: Pre-filter talents and pre-fetch all necessary location data ---
            talents_passing_skills_db = [
                t_db for t_db in attribute_filtered_db 
                if (filter_cache_item := self._talent_filter_cache.get(t_db.id)) and self._talent_passes_cached_skill_filters(filter_cache_item, all_filters)
            ]
            all_relevant_ids = [t_db.id for t_db in talents_passing_skills_db]
            
            talent_locations = self.controller.get_effective_locations_for_multiple_talents(
                all_relevant_ids, scene_dc.scheduled_week, scene_dc.scheduled_year
            )
            # --- Step 1.6: Apply effective location filter after fetching locations ---
            if effective_location_filters := all_filters.get('effective_locations'):
                talents_passing_skills_db = [
                    t_db for t_db in talents_passing_skills_db
                    if talent_locations.get(t_db.id) in effective_location_filters
                ]

            # --- Orchestration Step 2: Build the list for the UI, using cached demands where available ---
            final_cache_items = []
            talent_ids_to_calculate = []
            for t_db in talents_passing_skills_db:
                filter_cache_item = self._talent_filter_cache.get(t_db.id)
                if filter_cache_item: # We know this is true from the pre-filter above
                    # Use cached demand if it exists, otherwise mark for calculation
                    cached_demand = self._demand_cache.get(t_db.id)
                    # Update the effective location for the context of this scene
                    filter_cache_item.effective_location = talent_locations.get(t_db.id, t_db.base_location)
                    final_cache_items.append(CastingTalentCache(**filter_cache_item.__dict__, demand=cached_demand))
                    if cached_demand is None:
                        talent_ids_to_calculate.append(t_db.id)
            
            # --- Orchestration Step 3: Update UI immediately. Rows without demand will show "Calculating..." ---
            self.view.update_talent_list(final_cache_items)

            # --- Orchestration Step 4: Start background calculation ONLY for missing demands ---
            if talent_ids_to_calculate:
                # Pass all pre-fetched data to the worker.
                # The talent_locations dictionary is already calculated for all relevant talents.
                talents_to_calc = self.controller.get_multiple_talents_by_ids(talent_ids_to_calculate)
                worker = DemandCalculationWorker(self.controller, talents_to_calc, scene_dc, vp_id, talent_locations)
                worker.signals.finished.connect(self._on_demand_calculation_finished)
                self.thread_pool.start(worker)
        else:
            # --- PATH B: Standard, General Filtering ---
            self._current_casting_context = None # Clear context when not in casting mode
            self._stop_casting_mode()
            # Separate filters for the DB query vs. the in-memory cache filter
            db_filters = {k: v for k, v in all_filters.items() if not k.startswith(('performance', 'acting', 'stamina', 'dominance', 'submission'))}
            # Exclude effective_locations from the initial DB query as it's a dynamic value
            effective_location_filters = db_filters.pop('effective_locations', [])
            talents_from_db = self.controller.get_filtered_talents(db_filters)

            cache_items_passing_skills = []
            for t_db in talents_from_db:
                filter_cache_item = self._talent_filter_cache.get(t_db.id)
                if filter_cache_item and self._talent_passes_cached_skill_filters(filter_cache_item, all_filters):
                    # In general mode, ensure effective location is the current location
                    filter_cache_item.effective_location = t_db.current_location
                    # Apply the effective location filter in-memory
                    if effective_location_filters and filter_cache_item.effective_location not in effective_location_filters:
                        continue
                    cache_items_passing_skills.append(filter_cache_item)
            self.view.update_talent_list(cache_items_passing_skills)

    @pyqtSlot(dict)
    def _on_demand_calculation_finished(self, demands: dict):
        """Slot to receive results from the background worker and update the model."""
        # Update the presenter's demand cache first
        self._demand_cache.update(demands)

        # Then, update the underlying data in the model with the newly calculated values
        model_data = self.view.talent_model.raw_data
        for item in model_data:
            if isinstance(item, CastingTalentCache):
                if item.demand is None: # Only update if it was previously None
                    item.demand = demands.get(item.talent_db.id)
        
        # Tell the view to redraw itself with the new data
        self.view.talent_model.refresh()

    @pyqtSlot(list, QPoint)
    def on_context_menu_requested(self, talents: List[Talent], pos: QPoint):
        self.view.display_talent_context_menu(talents, self.controller.get_go_to_list_categories(), pos)

    @pyqtSlot(dict)
    def on_open_advanced_filters(self, current_filters: dict):
        if self.filter_dialog is None:
            self.filter_dialog = TalentFilterDialog(
                controller=self.controller,
                ethnicities_hierarchy=self.controller.get_ethnicity_hierarchy(),
                cup_sizes=self.controller.get_available_cup_sizes(),
                nationalities=self.controller.get_available_nationalities(),
                locations_by_region=self.controller.get_locations_by_region(),
                go_to_categories=self.controller.get_go_to_list_categories(),
                current_filters=current_filters,
                settings_manager=self.controller.settings_manager,
                parent=self.view,
            )
            self.filter_dialog.filters_applied.connect(self.view.on_filters_applied)
            self.filter_dialog.finished.connect(self.on_filter_dialog_closed)
            self.filter_dialog.show()
        else:
            self.filter_dialog.raise_()
            self.filter_dialog.activateWindow()
     
    def on_filter_dialog_closed(self, result):
        self.filter_dialog = None
    
    @pyqtSlot(object)
    def on_open_talent_profile(self, talent: Union[Talent, TalentDB]):
        if isinstance(talent, TalentDB): talent = talent.to_dataclass(Talent)
        self.ui_manager.show_talent_profile(talent)

    @pyqtSlot(str)
    def on_help_requested(self, topic_key: str):
        self.ui_manager.show_help(topic_key)