from typing import Union, Tuple, TYPE_CHECKING, List, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSlot, QPoint

from core.interfaces import IGameController
from ui.tabs.talent_tab import HireWindow
from ui.dialogs.talent_filter_dialog import TalentFilterDialog
from data.game_state import Talent
from database.db_models import TalentDB
from utils.formatters import get_fuzzed_skill_range
from ui.presenters.talent_filter_cache import TalentFilterCache

if TYPE_CHECKING:
    from ui.ui_manager import UIManager

class TalentTabPresenter(QObject):
    def __init__(self, controller: IGameController, view: HireWindow, ui_manager: 'UIManager'):
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
            self.controller.get_available_boob_cups()
        )

    def _connect_signals(self):
        # When talent pool changes, mark our cache as dirty. It will be rebuilt on the next filter action.
        self.controller.signals.talent_pool_changed.connect(self._invalidate_filter_cache)
        self.controller.signals.go_to_categories_changed.connect(self.view.refresh_from_state)
        self.controller.signals.go_to_list_changed.connect(self.view.refresh_from_state)

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
        """
        # Fetch all talents from DB. Using a throwaway filter to get the full list.
        self._all_talents_for_filtering = self.controller.get_filtered_talents({})
        self._talent_filter_cache.clear()

        for t_db in self._all_talents_for_filtering:
            perf_fuzzed = get_fuzzed_skill_range(t_db.performance, t_db.experience, t_db.id)
            act_fuzzed = get_fuzzed_skill_range(t_db.acting, t_db.experience, t_db.id)
            stam_fuzzed = get_fuzzed_skill_range(t_db.stamina, t_db.experience, t_db.id)

            self._talent_filter_cache[t_db.id] = TalentFilterCache(
                talent_db=t_db,
                perf_range=(perf_fuzzed, perf_fuzzed) if isinstance(perf_fuzzed, int) else perf_fuzzed,
                act_range=(act_fuzzed, act_fuzzed) if isinstance(act_fuzzed, int) else act_fuzzed,
                stam_range=(stam_fuzzed, stam_fuzzed) if isinstance(stam_fuzzed, int) else stam_fuzzed
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

        return True

    @pyqtSlot()
    def on_initial_load(self):
        self.view.refresh_from_state()

    @pyqtSlot(dict)
    def on_standard_filters_changed(self, all_filters: dict):
        # Step 1: Ensure the cache is up-to-date.
        if self._cache_is_dirty:
            self._build_filter_cache()

        # Step 2: Apply fast database-side filters.
        db_filters = {k: v for k, v in all_filters.items() if not k.startswith(('performance', 'acting', 'stamina'))}
        talents_from_db = self.controller.get_filtered_talents(db_filters)

        # Step 3: Apply slow Python-side filters using the pre-calculated cache.
        final_talent_ids = {t_db.id for t_db in talents_from_db}
        
        # This list comprehension is now extremely fast.
        talents_passing_skills = [
            cache_item.talent_db
            for talent_id, cache_item in self._talent_filter_cache.items()
            if talent_id in final_talent_ids and self._talent_passes_cached_skill_filters(cache_item, all_filters)
        ]
        
        self.view.update_talent_list(talents_passing_skills)

    @pyqtSlot(list, QPoint)
    def on_context_menu_requested(self, talents: List[Talent], pos: QPoint):
        all_categories = self.controller.get_go_to_list_categories()
        # For multi-select, we don't need to get specific talent categories, just all possible ones.
        self.view.display_talent_context_menu(talents, all_categories, pos)

    @pyqtSlot(dict)
    def on_open_advanced_filters(self, current_filters: dict):
        if self.filter_dialog is None:
            self.filter_dialog = TalentFilterDialog(
                ethnicities=self.controller.get_available_ethnicities(),
                boob_cups=self.controller.get_available_boob_cups(),
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