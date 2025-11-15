from typing import Union, Tuple, TYPE_CHECKING, List, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSlot, QPoint

from core.interfaces import IGameController
from ui.tabs.talent_tab import TalentTab
from ui.dialogs.talent_filter_dialog import TalentFilterDialog
from data.game_state import Talent
from database.db_models import TalentDB
from utils.formatters import get_fuzzed_skill_range
from ui.presenters.talent_filter_cache import TalentFilterCache

if TYPE_CHECKING:
    from ui.ui_manager import UIManager

class TalentTabPresenter(QObject):
    def __init__(self, controller: IGameController, view: TalentTab, ui_manager: 'UIManager'):
        super().__init__()
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager
        self.filter_dialog = None

        # --- Caching Mechanism ---
        self._all_talents_for_filtering: List[TalentDB] = []
        self._talent_filter_cache: Dict[int, TalentFilterCache] = {}
        self._cache_is_dirty = True

        self._connect_signals()
        self.view.create_model_and_load(
            self.controller.settings_manager,
            self.controller.get_available_cup_sizes()
        )

    def _connect_signals(self):
        # When talent pool changes, mark our cache as dirty. It will be rebuilt on the next filter action.
        self.controller.signals.talent_pool_changed.connect(self._invalidate_filter_cache)
        self.controller.signals.go_to_categories_changed.connect(self.view.refresh_from_state)
        self.controller.signals.go_to_list_changed.connect(self.view.refresh_from_state)
        self.controller.settings_manager.signals.setting_changed.connect(self.on_setting_changed)

        self.view.initial_load_requested.connect(self.on_initial_load)
        self.view.standard_filters_changed.connect(self.on_standard_filters_changed)
        self.view.context_menu_requested.connect(self.on_context_menu_requested)
        self.view.add_talent_to_category_requested.connect(self.controller.add_talents_to_go_to_category)
        self.view.remove_talent_from_category_requested.connect(self.controller.remove_talents_from_go_to_category)
        self.view.open_advanced_filters_requested.connect(self.on_open_advanced_filters)
        self.view.open_talent_profile_requested.connect(self.on_open_talent_profile)
        self.view.help_requested.connect(self.on_help_requested)

    @pyqtSlot()
    def _invalidate_filter_cache(self):
        self._cache_is_dirty = True
        self.view.refresh_from_state()

    def _build_filter_cache(self):
        """
        Calculates fuzzed ranges for ALL talents ONCE and stores them.
        This is the core of the performance optimization.
        Now calculates ALL 5 skills + popularity to eliminate duplicate work in table model.
        """
        # Fetch all talents from DB. Using a throwaway filter to get the full list.
        self._all_talents_for_filtering = self.controller.get_filtered_talents({})
        self._talent_filter_cache.clear()

        for t_db in self._all_talents_for_filtering:
            # Calculate all 5 fuzzed skill ranges
            perf_fuzzed = get_fuzzed_skill_range(t_db.performance, t_db.experience, t_db.id)
            act_fuzzed = get_fuzzed_skill_range(t_db.acting, t_db.experience, t_db.id)
            stam_fuzzed = get_fuzzed_skill_range(t_db.stamina, t_db.experience, t_db.id)
            dom_fuzzed = get_fuzzed_skill_range(t_db.dom_skill, t_db.experience, t_db.id)
            sub_fuzzed = get_fuzzed_skill_range(t_db.sub_skill, t_db.experience, t_db.id)
            
            # Pre-calculate popularity
            popularity = round(sum(p.score for p in t_db.popularity_scores) if t_db.popularity_scores else 0)

            self._talent_filter_cache[t_db.id] = TalentFilterCache(
                talent_db=t_db,
                perf_range=(perf_fuzzed, perf_fuzzed) if isinstance(perf_fuzzed, int) else perf_fuzzed,
                act_range=(act_fuzzed, act_fuzzed) if isinstance(act_fuzzed, int) else act_fuzzed,
                stam_range=(stam_fuzzed, stam_fuzzed) if isinstance(stam_fuzzed, int) else stam_fuzzed,
                dom_range=(dom_fuzzed, dom_fuzzed) if isinstance(dom_fuzzed, int) else dom_fuzzed,
                sub_range=(sub_fuzzed, sub_fuzzed) if isinstance(sub_fuzzed, int) else sub_fuzzed,
                popularity=popularity
            )
        self._cache_is_dirty = False

    def _talent_passes_cached_skill_filters(self, cache_item: TalentFilterCache, filters: dict) -> bool:
        """Performs fast integer comparisons against the pre-calculated cache."""
        # Performance
        user_min_perf, user_max_perf = filters.get('performance_min', 0), filters.get('performance_max', 100)
        talent_min_perf, talent_max_perf = cache_item.perf_range
        if not (talent_min_perf <= user_max_perf and talent_max_perf >= user_min_perf):
            return False

        # Acting
        user_min_act, user_max_act = filters.get('acting_min', 0), filters.get('acting_max', 100)
        talent_min_act, talent_max_act = cache_item.act_range
        if not (talent_min_act <= user_max_act and talent_max_act >= user_min_act):
            return False

        # Stamina
        user_min_stam, user_max_stam = filters.get('stamina_min', 0), filters.get('stamina_max', 100)
        talent_min_stam, talent_max_stam = cache_item.stam_range
        if not (talent_min_stam <= user_max_stam and talent_max_stam >= user_min_stam):
            return False

        # Dominance
        user_min_dom, user_max_dom = filters.get('dominance_min', 0), filters.get('dominance_max', 100)
        talent_min_dom, talent_max_dom = cache_item.dom_range
        if not (talent_min_dom <= user_max_dom and talent_max_dom >= user_min_dom):
            return False

        # Submission
        user_min_sub, user_max_sub = filters.get('submission_min', 0), filters.get('submission_max', 100)
        talent_min_sub, talent_max_sub = cache_item.sub_range
        if not (talent_min_sub <= user_max_sub and talent_max_sub >= user_min_sub):
            return False

        return True
    
    @pyqtSlot(str)
    def on_setting_changed(self, key: str):
        """
        Handles global settings changes that affect this tab's display.
        """
        if key == 'unit_system':
            self.view.talent_model.refresh()

    @pyqtSlot()
    def on_initial_load(self):
        self.view.refresh_from_state()

    @pyqtSlot(dict)
    def on_standard_filters_changed(self, all_filters: dict):
        # Step 1: Ensure the cache is up-to-date.
        if self._cache_is_dirty:
            self._build_filter_cache()

        # Step 2: Decide which filtering path to take based on whether a specific role is selected.
        scene_id = all_filters.get('scene_id')
        vp_id = all_filters.get('vp_id')

        if scene_id is not None and vp_id is not None and vp_id > -1:
            # --- PATH A: Role-Specific Filtering ---
            # 1. Get the base list of candidates who are eligible for the role.
            base_candidates_db = self.controller.get_eligible_talent_for_role(scene_id, vp_id)

            # 2. Prepare attribute filters. This is where we implement the "Smarter Caller" logic.
            attribute_filters = {
                k: v for k, v in all_filters.items()
                if not k.startswith(('performance', 'acting', 'stamina', 'dominance', 'submission', 'gender', 'ethnicities'))
            }
            
            # Get role details to determine which physical filter is irrelevant.
            role_details = self.controller.get_role_details_for_ui(scene_id, vp_id)
            role_gender = (role_details.get('gender') or 'any').lower()

            if role_gender == 'female':
                # For a female role, the dick size filter is irrelevant.
                # Setting its keys to None ensures the service's `is not None` check will fail, correctly skipping it.
                attribute_filters['dick_size_min'] = None
                attribute_filters['dick_size_max'] = None
            elif role_gender == 'male':
                # For a male role, the cup size filter is irrelevant.
                if 'cup_sizes' in attribute_filters:
                    del attribute_filters['cup_sizes']
            
            # 3. Call the service to perform in-memory attribute filtering.
            attribute_filtered_db = self.controller.filter_talent_list_by_attributes(
                base_candidates_db,
                attribute_filters
            )

            # 4. Perform final, UI-cached skill filtering on the refined list.
            final_cache_items = [
                self._talent_filter_cache[t_db.id]
                for t_db in attribute_filtered_db
                if t_db.id in self._talent_filter_cache and
                   self._talent_passes_cached_skill_filters(self._talent_filter_cache[t_db.id], all_filters)
            ]
            self.view.update_talent_list(final_cache_items)

        else:
            # --- PATH B: Standard, General Filtering (Existing Logic) ---
            # 1. Apply fast database-side filters.
            db_filters = {k: v for k, v in all_filters.items() if not k.startswith(('performance', 'acting', 'stamina', 'dominance', 'submission'))}
            talents_from_db = self.controller.get_filtered_talents(db_filters)

            # 2. Apply slow Python-side filters using the pre-calculated cache.
            cache_items_passing_skills = [
                self._talent_filter_cache[t_db.id]
                for t_db in talents_from_db
                if t_db.id in self._talent_filter_cache and
                   self._talent_passes_cached_skill_filters(self._talent_filter_cache[t_db.id], all_filters)
            ]
            self.view.update_talent_list(cache_items_passing_skills)

    @pyqtSlot(list, QPoint)
    def on_context_menu_requested(self, talents: List[Talent], pos: QPoint):
        all_categories = self.controller.get_go_to_list_categories()
        # For multi-select, we don't need to get specific talent categories, just all possible ones.
        self.view.display_talent_context_menu(talents, all_categories, pos)

    @pyqtSlot(dict)
    def on_open_advanced_filters(self, current_filters: dict):
        if self.filter_dialog is None:
            self.filter_dialog = TalentFilterDialog(
                self.controller,
                ethnicities_hierarchy=self.controller.get_ethnicity_hierarchy(),
                cup_sizes=self.controller.get_available_cup_sizes(),
                nationalities=self.controller.get_available_nationalities(),
                locations_by_region=self.controller.get_locations_by_region(),
                go_to_categories=self.controller.get_go_to_list_categories(),
                current_filters=current_filters,
                settings_manager=self.controller.settings_manager,
                parent=self.view
            )
            # The dialog now only emits when 'Apply' is clicked.
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
        # The UserRole might now return a TalentDB object, handle both cases.
        if isinstance(talent, TalentDB):
            talent = talent.to_dataclass(Talent)
        self.ui_manager.show_talent_profile(talent)

    @pyqtSlot(str)
    def on_help_requested(self, topic_key: str):
        self.ui_manager.show_help(topic_key)