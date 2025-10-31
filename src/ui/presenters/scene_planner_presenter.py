import logging
from typing import Optional, List, Dict, Tuple, Set, TYPE_CHECKING
from PyQt6.QtCore import Qt, pyqtSlot, QObject
from PyQt6.QtWidgets import QDialog, QMessageBox, QListWidgetItem

from core.interfaces import IGameController
from data.game_state import Scene, Talent, ShootingBloc
from ui.dialogs.scene_dialog import SceneDialog
from ui.dialogs.scene_filter_dialog import SceneFilterDialog
from utils.scene_summary_builder import prepare_summary_data
from services.scene_state_editor import SceneStateEditor

if TYPE_CHECKING:
    from ui.ui_manager import UIManager

logger = logging.getLogger(__name__)

class ScenePlannerPresenter(QObject):
    def __init__(self, controller: IGameController, scene_id: int, view: SceneDialog, ui_manager: 'UIManager'):
        super().__init__(view) # Parent the presenter to the view for lifecycle management
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager
        
        original_scene = self.controller.get_scene_for_planner(scene_id)
        if not original_scene: raise ValueError(f"Scene with ID {scene_id} not found.")
            
        self.state_editor = SceneStateEditor(original_scene, self.controller.data_manager)
        
        self._talent_cache = {}
        self.parent_bloc: Optional[ShootingBloc] = None
        if self.working_scene.bloc_id: self.parent_bloc = self.controller.get_bloc_by_id(self.working_scene.bloc_id)

        # UI State
        self.thematic_tag_filters: Dict = {}
        self.physical_tag_filters: Dict = {}
        self.action_tag_filters: Dict = {}
        self.thematic_search_text: str = ""
        self.physical_search_text: str = ""
        self.action_search_text: str = ""
        self.selected_thematic_tag_name: Optional[str] = None
        self.selected_physical_tag_name: Optional[str] = None
        self.selected_segment_id: Optional[int] = None
        
        self.update_favorites()
        self._connect_signals()

    @property
    def working_scene(self) -> Scene: return self.state_editor.working_scene

    def _connect_signals(self):
        # View signals
        self.view.view_loaded.connect(self.on_view_loaded)
        self.view.button_box.accepted.connect(self.on_save_requested)
        self.view.button_box.rejected.connect(self.on_cancel_requested)
        self.view.delete_requested.connect(self.on_delete_requested)
        self.view.title_changed.connect(self.on_title_changed)
        self.view.focus_target_changed.connect(self.on_focus_target_changed)
        self.view.status_changed.connect(self._on_status_changed)
        self.view.ds_level_changed.connect(self.on_ds_level_changed)
        self.view.performer_count_changed.connect(self.on_performer_count_changed)
        self.view.composition_changed.connect(self.on_composition_changed)
        self.view.protagonist_toggled.connect(self.on_protagonist_toggled)
        self.view.total_runtime_changed.connect(self.on_total_runtime_changed)
        self.view.toggle_favorite_requested.connect(self.on_toggle_favorite_requested)
        
        # Thematic
        self.view.thematic_search_changed.connect(self.on_thematic_search_changed)
        self.view.thematic_filter_requested.connect(self.on_thematic_filter_requested)
        self.view.add_thematic_tags_requested.connect(self.on_add_thematic_tags)
        self.view.remove_thematic_tags_requested.connect(self.on_remove_thematic_tags)
        
        # Physical
        self.view.physical_search_changed.connect(self.on_physical_search_changed)
        self.view.physical_filter_requested.connect(self.on_physical_filter_requested)
        self.view.add_physical_tags_requested.connect(self.on_add_physical_tags)
        self.view.remove_physical_tags_requested.connect(self.on_remove_physical_tags)
        self.view.selected_physical_tag_changed.connect(self.on_selected_physical_tag_changed)
        self.view.physical_tag_assignment_changed.connect(self.on_physical_tag_assignment_changed)
        
        # Action
        self.view.action_search_changed.connect(self.on_action_search_changed)
        self.view.action_filter_requested.connect(self.on_action_filter_requested)
        self.view.add_action_segments_requested.connect(self.on_add_action_segments)
        self.view.remove_action_segments_requested.connect(self.on_remove_action_segments)
        self.view.selected_action_segment_changed.connect(self.on_selected_action_segment_changed)
        self.view.segment_runtime_changed.connect(self.on_segment_runtime_changed)
        self.view.segment_parameter_changed.connect(self.on_segment_parameter_changed)
        self.view.slot_assignment_changed.connect(self.on_slot_assignment_changed)

        self.view.hire_for_role_requested.connect(self.on_hire_for_role)     
        self.controller.signals.favorites_changed.connect(self.on_favorites_changed)

        self.controller.signals.scenes_changed.connect(self.on_external_scene_change)

    def on_view_loaded(self): self._refresh_full_view()

    def _refresh_full_view(self):
        self._refresh_general_info()
        self._refresh_composition()
        self._refresh_thematic_panel()
        self._refresh_physical_panel()
        self._refresh_action_segment_panel()
        self._refresh_lock_state()
        self._update_summary()

    # --- Refresh Helpers ---
    def _refresh_general_info(self):
        self.view.update_general_info(
            title=self.working_scene.title, status=self.working_scene.status,
            focus_target=self.working_scene.focus_target, runtime=self.working_scene.total_runtime_minutes,
            ds_level=self.working_scene.dom_sub_dynamic_level, bloc_text=self._get_bloc_info_text()
        )

    def _refresh_composition(self):
        performers_with_talent_data = []
        for vp in self.working_scene.virtual_performers:
            talent = self.get_talent_by_id(self.working_scene.final_cast.get(str(vp.id)))
            performers_with_talent_data.append({
                'display_name': talent.alias if talent else vp.name, 'vp_name': vp.name, 'is_cast': talent is not None,
                'gender': vp.gender, 'ethnicity': vp.ethnicity, 'disposition': vp.disposition, 'vp_id': vp.id
            })
        self.view.update_performer_editors(
            performers_with_talent_data,
            self.working_scene.dom_sub_dynamic_level,
            self.working_scene.protagonist_vp_ids,
            self.is_casting_enabled(),
            self.is_design_editable()
        )

    def _refresh_thematic_panel(self):
        available = self.get_filtered_available_thematic_tags()
        self.view.update_available_thematic_tags(available)
        
        all_tags, _, _ = self.controller.get_thematic_tags_for_planner()
        selected_data = [t for t in all_tags if t['full_name'] in self.working_scene.global_tags]
        self.view.update_selected_thematic_tags(sorted(selected_data, key=lambda t: t['full_name']))

    def _refresh_physical_panel(self):
        available = self.get_filtered_available_physical_tags()
        self.view.update_available_physical_tags(available)
        
        all_tags, _, _ = self.controller.get_physical_tags_for_planner()
        selected_data = [t for t in all_tags if t['full_name'] in self.working_scene.assigned_tags.keys()]
        self.view.update_selected_physical_tags(sorted(selected_data, key=lambda t: t['full_name']), self.selected_physical_tag_name)
        
        self.on_selected_physical_tag_changed(self.view.selected_physical_list.currentItem())

    def _refresh_action_segment_panel(self):
        available = self.get_filtered_available_action_tags()
        self.view.update_available_action_tags(available)
        
        segments = sorted(self.working_scene.action_segments, key=lambda s: s.tag_name)
        self.view.update_selected_action_segments(segments, self.controller.tag_definitions, self.selected_segment_id)
        
        self.on_selected_action_segment_changed(self.view.selected_actions_list.currentItem())

    def _refresh_lock_state(self):
        is_cast_locked = len(self.working_scene.final_cast) > 0
        is_editable = not is_cast_locked and self.working_scene.status.lower() == 'design'
        self.view.set_ui_lock_state(is_editable, is_cast_locked)
        
    # --- Slots for View Signals ---
    def on_title_changed(self, title: str):
        self.state_editor.set_title(title)
    def on_focus_target_changed(self, target: str): self.state_editor.set_focus_target(target)
    def on_total_runtime_changed(self, minutes: int): self.state_editor.set_total_runtime(minutes)
    def on_ds_level_changed(self, level: int):
        self.state_editor.set_ds_level(level)
        self._refresh_composition()
        self._update_summary()

    def on_performer_count_changed(self, new_count: int):
        self.view.flush_pending_composition_changes()
        self.state_editor.update_performer_count(new_count)
        self._refresh_composition(); self._refresh_physical_panel(); self._refresh_action_segment_panel()
        self._update_summary()

    def on_composition_changed(self, performers_data: List[Dict]):
        self.state_editor.update_composition(performers_data)
        self.on_selected_physical_tag_changed(self.view.selected_physical_list.currentItem()); self._refresh_action_segment_panel()
        self._update_summary()

    def on_protagonist_toggled(self, vp_id: int, is_protagonist: bool):
        self.state_editor.set_protagonist_status(vp_id, is_protagonist)

    def on_thematic_search_changed(self, text: str):
        self.thematic_search_text = text.lower()
        self._refresh_thematic_panel()
    def on_physical_search_changed(self, text: str):
        self.physical_search_text = text.lower()
        self._refresh_physical_panel()
    def on_action_search_changed(self, text: str):
        self.action_search_text = text.lower()
        self._refresh_action_segment_panel()

    def on_thematic_filter_requested(self):
        _, cats, orients = self.controller.get_thematic_tags_for_planner()
        self._show_filter_dialog('thematic', cats, orients, self.thematic_tag_filters, self._refresh_thematic_panel)

    def on_physical_filter_requested(self):
        all_tags, cats, orients = self.controller.get_physical_tags_for_planner()
        self._show_filter_dialog('physical', cats, orients, self.physical_tag_filters, self._refresh_physical_panel, all_tags)

    def on_action_filter_requested(self):
        _, cats, orients = self.controller.get_action_tags_for_planner()
        self._show_filter_dialog('action', cats, orients, self.action_tag_filters, self._refresh_action_segment_panel)

    def _show_filter_dialog(self, mode, cats, orients, current_filters, refresh_callback, all_tags_for_dialog: Optional[List[Dict]] = None):
        dialog = SceneFilterDialog(
            categories=sorted(list(cats)),
            orientations=sorted(list(orients)),
            mode=mode,
            current_filters=current_filters,
            all_tags=all_tags_for_dialog, # Pass tags for body part filtering
            controller=self.controller, parent=self.view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if mode == 'thematic': self.thematic_tag_filters = dialog.get_filters()
            elif mode == 'physical': self.physical_tag_filters = dialog.get_filters()
            elif mode == 'action': self.action_tag_filters = dialog.get_filters()
            refresh_callback()

    def on_add_thematic_tags(self, tag_names: List[str]):
        self.state_editor.add_style_tags(tag_names)
        self._refresh_thematic_panel()
        self._update_summary()
    def on_remove_thematic_tags(self, tag_names: List[str]):
        self.state_editor.remove_style_tags(tag_names)
        self._refresh_thematic_panel()
        self._update_summary()
    def on_add_physical_tags(self, tag_names: List[str]):
        if not tag_names: return
        self.state_editor.add_style_tags(tag_names)
        self.selected_physical_tag_name = sorted(tag_names)[0]
        self._refresh_physical_panel()
        self._update_summary()
    def on_remove_physical_tags(self, tag_names: List[str]):
        if not tag_names: return
        if self.selected_physical_tag_name in tag_names:
            self.selected_physical_tag_name = None
        self.state_editor.remove_style_tags(tag_names)
        self._refresh_physical_panel()
        self._update_summary()

    def on_selected_physical_tag_changed(self, item: Optional[QListWidgetItem]):
        if not item:
            self.view.update_physical_assignment_panel(None, [], [], False)
            return
        tag_data = item.data(Qt.ItemDataRole.UserRole)
        raw_name = tag_data['full_name'].lstrip("⭐ ")
        self.selected_physical_tag_name = raw_name
        performers_with_talent_data = []
        for vp in self.working_scene.virtual_performers:
            talent = self.get_talent_by_id(self.working_scene.final_cast.get(str(vp.id)))
            performers_with_talent_data.append({
                'display_name': talent.alias if talent else vp.name, 'is_cast': talent is not None, 
                'gender': vp.gender, 'ethnicity': vp.ethnicity, 'vp_id': vp.id
            })
        assigned_ids = self.working_scene.assigned_tags.get(raw_name, [])
        self.view.update_physical_assignment_panel(tag_data, performers_with_talent_data, assigned_ids, self.is_design_editable())

    def on_physical_tag_assignment_changed(self, tag_name: str, vp_id: int, is_assigned: bool):
        self.state_editor.update_style_tag_assignment(tag_name, vp_id, is_assigned)
        self._update_summary()

    def on_add_action_segments(self, tag_names: List[str]):
        if not tag_names: return
        new_ids = self.state_editor.add_action_segments(tag_names)
        if new_ids: self.selected_segment_id = new_ids[0]
        self._refresh_action_segment_panel()
        self._update_summary()

    def on_remove_action_segments(self, segment_ids: List[int]):
        if not segment_ids: return
        if self.selected_segment_id in segment_ids:
            self.selected_segment_id = None
        self.state_editor.remove_action_segments(segment_ids)
        # After removing, if there are segments left and nothing is selected, select the first one.
        if not self.selected_segment_id and self.working_scene.action_segments:
            self.selected_segment_id = sorted(self.working_scene.action_segments, key=lambda s: s.tag_name)[0].id
        self._refresh_action_segment_panel()
        self._update_summary()

    def on_selected_action_segment_changed(self, item: Optional[QListWidgetItem]):
        if not item:
            self.selected_segment_id = None; self.view.update_segment_details(None, {}, {}, False)
            return
        segment_id = item.data(Qt.ItemDataRole.UserRole)
        segment = next((s for s in self.working_scene.action_segments if s.id == segment_id), None)
        self.selected_segment_id = segment_id
        if not segment: self.view.update_segment_details(None, {}, {}, False); return

        vp_options_by_slot = {}; tag_def = self.controller.tag_definitions.get(segment.tag_name)
        if tag_def:
            current_assignments = {sa.slot_id: sa.virtual_performer_id for sa in segment.slot_assignments}
            for slot_def in tag_def.get('slots', []):
                count = segment.parameters.get(slot_def['role'], slot_def.get('count', 1))
                for i in range(count):
                    slot_id = f"{tag_def.get('name', segment.tag_name)}_{slot_def['role']}_{i+1}"
                    vps_assigned_elsewhere = {vp_id for sid, vp_id in current_assignments.items() if sid != slot_id and vp_id is not None}
                    eligible_vps = []
                    for vp in self.working_scene.virtual_performers:
                        talent = self.get_talent_by_id(self.working_scene.final_cast.get(str(vp.id)))
                        gender_req = slot_def.get('gender')
                        gender_ok = not gender_req or gender_req == "Any" or vp.gender == gender_req
                        if gender_ok and vp.id not in vps_assigned_elsewhere:
                            eligible_vps.append((talent.alias if talent else vp.name, vp.id))
                    vp_options_by_slot[slot_id] = eligible_vps
        self.view.update_segment_details(segment, self.controller.tag_definitions, vp_options_by_slot, self.is_design_editable())

    def on_segment_runtime_changed(self, segment_id: int, percentage: int):
        self.state_editor.update_action_segment_runtime(segment_id, percentage)
        self._refresh_action_segment_panel()
        self._update_summary()
    def on_segment_parameter_changed(self, segment_id: int, role: str, value: int):
        self.state_editor.update_action_segment_parameter(segment_id, role, value)
        self._refresh_action_segment_panel()
        self._update_summary()
    def on_slot_assignment_changed(self, segment_id: int, slot_id: str, vp_id: Optional[int]):
        self.state_editor.update_slot_assignment(segment_id, slot_id, vp_id)
        self.on_selected_action_segment_changed(self.view.selected_actions_list.currentItem())
        self._update_summary()

    def on_save_requested(self):
        self.controller.update_scene_full(self.state_editor.finalize_for_saving())
        self.view.accept()

    def on_cancel_requested(self):
        self.view.reject()
    def on_delete_requested(self, penalty_percentage: float): self.controller.delete_scene(self.working_scene.id, penalty_percentage=penalty_percentage); self.view.accept()
    def on_favorites_changed(self): self.update_favorites(); self._refresh_thematic_panel(); self._refresh_physical_panel(); self._refresh_action_segment_panel()
    def on_toggle_favorite_requested(self, tag_name: str, tag_type: str): self.toggle_favorite_tag(tag_name, tag_type)

    @pyqtSlot(int)
    def on_hire_for_role(self, vp_id: int):
        # Sanity check to ensure the scene is in the right state.
        fresh_scene = self.controller.get_scene_for_planner(self.working_scene.id)
        if not fresh_scene or fresh_scene.status.lower() != 'casting':
            QMessageBox.warning(self.view, "Casting Error",
                                "Scene is not ready for casting. Please ensure it is saved in 'Casting' status.")
            return

        # 1. Show the casting dialog. The vp_id is already permanent.
        result = self.ui_manager.show_role_casting_dialog(self.working_scene.id, vp_id)

        if result == QDialog.DialogCode.Accepted:
            # 2. A hire was made. The database is updated, but our local 'working_scene'
            # in the editor service is now stale. We need to refresh it.
            updated_scene = self.controller.get_scene_for_planner(self.working_scene.id)
            if updated_scene:
                self.state_editor.reset_with_scene(updated_scene)
                self._refresh_full_view()
            else:
                logger.error(f"Could not re-fetch scene {self.working_scene.id} after hiring. Closing dialog.")
                self.view.close()

    # --- Data Access & Helpers ---
    def _update_summary(self):
        """Prepares and sends summary data to the view."""
        summary_data = prepare_summary_data(self.working_scene, self.controller)
        self.view.update_summary_view(summary_data)

    def _get_bloc_info_text(self) -> str:
        if not self.working_scene: return ""
        if self.parent_bloc: return f"Part of '{self.parent_bloc.name}' shooting on Week {self.parent_bloc.scheduled_week}, {self.parent_bloc.scheduled_year}"
        return f"Scheduled for Week {self.working_scene.scheduled_week}, {self.working_scene.scheduled_year} (Legacy)"

    def get_talent_by_id(self, talent_id: int) -> Optional[Talent]:
        if talent_id is None:
            return None
        
        if talent_id in self._talent_cache: return self._talent_cache[talent_id]
        talent = self.controller.talent_service.get_talent_by_id(talent_id)
        if talent: self._talent_cache[talent_id] = talent
        return talent

    def is_design_editable(self) -> bool: return not self.is_cast_locked() and self.working_scene.status.lower() == 'design'
    def is_cast_locked(self) -> bool: return len(self.working_scene.final_cast) > 0
    def is_casting_enabled(self) -> bool: return self.working_scene.status.lower() == 'casting'

    def update_favorites(self):
        self.favorite_thematic_tags = set(self.controller.get_favorite_tags('thematic'))
        self.favorite_physical_tags = set(self.controller.get_favorite_tags('physical'))
        self.favorite_action_tags = set(self.controller.get_favorite_tags('action'))

    def toggle_favorite_tag(self, tag_name: str, tag_type: str): self.controller.toggle_favorite_tag(tag_name, tag_type)

    def get_filtered_available_thematic_tags(self) -> List[Dict]:
        all_tags, _, _ = self.controller.get_thematic_tags_for_planner()
        return self._filter_tags(all_tags, self.thematic_tag_filters, self.thematic_search_text, 
                                 set(self.working_scene.global_tags), self.favorite_thematic_tags)

    def get_filtered_available_physical_tags(self) -> List[Dict]:
        all_tags, _, _ = self.controller.get_physical_tags_for_planner()
        return self._filter_tags(all_tags, self.physical_tag_filters, self.physical_search_text, 
                                 set(self.working_scene.assigned_tags.keys()), self.favorite_physical_tags)

    def get_filtered_available_action_tags(self) -> List[Dict]:
        all_tags, _, _ = self.controller.get_action_tags_for_planner()
        return self._filter_tags(all_tags, self.action_tag_filters, self.action_search_text, 
                                 set(), self.favorite_action_tags)

    def _filter_tags(self, all_tags: List[Dict], filters: Dict, search_text: str, current_selected_names: Set, favorite_tags: Set) -> List[Dict]:
        selected_cats = set(filters.get('categories', [])); match_mode = filters.get('match_mode', 'any')
        selected_orients = set(filters.get('orientations', []))
        show_favs_only = filters.get('show_favorites_only', False)
        min_p, max_p = filters.get('min_participants', 1), filters.get('max_participants', 99)
        tags_to_display = []
        for tag_data_orig in all_tags:
            tag_data = tag_data_orig.copy(); full_name = tag_data['full_name']
            if full_name in current_selected_names: continue
            if search_text and search_text not in full_name.lower(): continue
            if show_favs_only and full_name not in favorite_tags: continue
            if selected_orients and tag_data.get('orientation') not in selected_orients: continue
            if 'participant_count' in tag_data and not (min_p <= tag_data['participant_count'] <= max_p): continue
            tag_cats = {tag_data.get('categories', [])} if isinstance(tag_data.get('categories', []), str) else set(tag_data.get('categories', []))
            if not selected_cats or (match_mode == 'any' and selected_cats.intersection(tag_cats)) or (match_mode == 'all' and selected_cats.issubset(tag_cats)):
                # Create a sort key that ignores the star for alphabetical sorting
                tag_data['_sort_name'] = full_name.lstrip("⭐ ")
                tags_to_display.append(tag_data) 
        sort_key = lambda t: (0 if t['full_name'] in favorite_tags else 1, t['_sort_name'])
        for t in tags_to_display:
            if t['full_name'] in favorite_tags: t['full_name'] = f"⭐ {t['full_name']}"
        return sorted(tags_to_display, key=sort_key)
        
    def _on_status_changed(self, new_status_str: str):
        new_status_lower = new_status_str.lower()
        if new_status_lower == self.working_scene.status.lower():
            return

        is_valid, message = self.state_editor.validate_and_set_status(new_status_str)
        if is_valid:
            # Refresh the UI to reflect the new status and potential lock changes.
            self._refresh_full_view()

            # If moving to casting, save immediately to make roles available.
            if new_status_lower == 'casting':

                self.controller.update_scene_full(self.state_editor.finalize_for_saving())
                # After saving, temp IDs become permanent. We must refresh our local state.
                fresh_scene = self.controller.get_scene_for_planner(self.working_scene.id)
                if fresh_scene:
                    self.state_editor.reset_with_scene(fresh_scene)
                    self._refresh_full_view()
                else:
                    logger.error(f"Could not re-fetch scene {self.working_scene.id} after status change. Closing dialog.")
                    self.view.close()

        else:
            QMessageBox.warning(self.view, "Cannot Change Status", message)
            self._refresh_general_info()



    @pyqtSlot()
    def on_external_scene_change(self):
        """
        Slot to handle the global scenes_changed signal.
        Refreshes the presenter's state and view if the underlying scene
        has been modified by an external action (e.g., casting from a
        different dialog).
        """
        # Re-fetch the scene data from the authoritative source
        fresh_scene = self.controller.get_scene_for_planner(self.working_scene.id)

        if fresh_scene == self.state_editor.original_scene:
            return

        if not fresh_scene:
            # The scene was likely deleted by another process. Close the dialog.
            logger.info(f"Scene {self.working_scene.id} no longer exists. Closing planner.")
            self.view.close()
            return
            
        # The scene still exists. Reset our local state and refresh the entire view.
        self.state_editor.reset_with_scene(fresh_scene)
        self._refresh_full_view()