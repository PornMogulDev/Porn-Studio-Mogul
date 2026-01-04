import logging
import dataclasses
import copy
from typing import Optional, List, Dict, Set
from PyQt6.QtCore import Qt, pyqtSlot, QObject
from PyQt6.QtWidgets import QDialog, QMessageBox
from PyQt6 import sip

from core.interfaces import IGameController
from data.game_state import (
    Scene, Talent, ShootingBloc,
    VirtualPerformer, ActionSegment, SlotAssignment
)
from ui.view_models import PerformerEditorViewModel, TotalRuntimeViewModel
from ui.dialogs.scene_planner_dialog import ScenePlannerDialog
from ui.dialogs.scene_filter_dialog import SceneFilterDialog
from ui.builders.scene_summary_builder import prepare_summary_data
from utils.preset_handler import PresetHandler
from utils import time_utils

logger = logging.getLogger(__name__)

class ScenePlannerPresenter(QObject):
    def __init__(self, controller: IGameController, scene_id: int, view: ScenePlannerDialog, parent=None):
        super().__init__(parent) # Parent the presenter to the view for lifecycle management
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.view = view
        
        # Use Controller Factory for DI
        self.state_editor = self.controller.get_scene_state_editor(scene_id)
        if not self.state_editor:
             raise ValueError(f"Scene with ID {scene_id} not found.")
        
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

        # --- Initialize Preset Handler ---
        self.preset_handler = PresetHandler(
            widget=self.view.preset_widget,
            settings_manager=self.settings_manager,
            settings_key="scene_planner_presets",
            parent_view=self.view,
            save_callback=self._get_scene_data_for_preset,
            load_callback=self._apply_preset_to_scene
        )

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
        self.view.composition_changed.connect(self.handle_composition_change)
        self.view.protagonist_toggled.connect(self.on_protagonist_toggled)
        self.view.total_runtime_changed.connect(self.on_total_runtime_changed)
        self.view.toggle_favorite_requested.connect(self.on_toggle_favorite_requested)

        # Thematic
        self.view.thematic_search_changed.connect(self.on_thematic_search_changed)
        self.view.thematic_filter_requested.connect(self.on_thematic_filter_requested)
        self.view.add_thematic_tags_requested.connect(self.handle_add_thematic_tags)
        self.view.remove_thematic_tags_requested.connect(self.handle_remove_thematic_tags)
        
        # Physical
        self.view.physical_search_changed.connect(self.on_physical_search_changed)
        self.view.physical_filter_requested.connect(self.on_physical_filter_requested)
        self.view.add_physical_tags_requested.connect(self.handle_add_physical_tags)
        self.view.remove_physical_tags_requested.connect(self.handle_remove_physical_tags)
        self.view.selected_physical_tag_changed.connect(self.on_selected_physical_tag_changed)
        self.view.physical_tag_assignment_changed.connect(self.on_physical_tag_assignment_changed)
        
        # Action
        self.view.action_search_changed.connect(self.on_action_search_changed)
        self.view.action_filter_requested.connect(self.on_action_filter_requested)
        self.view.add_action_segments_requested.connect(self.handle_add_action_segments)
        self.view.remove_action_segments_requested.connect(self.handle_remove_action_segments)
        self.view.selected_action_segment_changed.connect(self.on_selected_action_segment_changed)
        self.view.segment_runtime_changed.connect(self.on_segment_runtime_changed)
        self.view.segment_parameter_changed.connect(self.on_segment_parameter_changed)
        self.view.slot_assignment_changed.connect(self.on_slot_assignment_changed)
  
        self.controller.signals.favorites_changed.connect(self.on_favorites_changed)

        self.controller.signals.scenes_changed.connect(self.on_external_scene_change)

    def on_view_loaded(self):
        self._load_and_set_initial_data()
        self._refresh_full_view()

    def _load_and_set_initial_data(self):
        """Fetches static data, formats it, and passes it to the view."""
        viewer_groups = [group['name'] for group in self.controller.market_data.get('viewer_groups', [])]

        # This logic is moved from the old view's _build_indented_ethnicity_list
        hierarchy = self.controller.get_ethnicity_hierarchy()
        ethnicities = []
        for primary, subs in hierarchy.items():
            ethnicities.append(primary)
            for sub in subs:
                ethnicities.append(f"  {sub}")

        self.view.set_initial_data(viewer_groups, ethnicities, self.controller.signals.show_help_requested)

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
        performer_models = []
        is_design_editable = self.is_design_editable()
        is_casting_enabled = self.is_casting_enabled()
        ds_level = self.working_scene.dom_sub_dynamic_level
        protagonist_ids = self.working_scene.protagonist_vp_ids
        for vp in self.working_scene.virtual_performers:
            talent = self.get_talent_by_id(self.working_scene.final_cast.get(str(vp.id))); is_cast = talent is not None
            is_role_uncast = not is_cast; is_role_editable = is_role_uncast and is_design_editable

            model = PerformerEditorViewModel(
                vp_id=vp.id,
                display_name=talent.alias if is_cast else vp.name,
                tooltip=f"Playing the role of '{vp.name}'" if is_cast else "",
                gender=vp.gender, ethnicity=vp.ethnicity, disposition=vp.disposition,
                is_protagonist=vp.id in protagonist_ids,
                is_name_editable=is_role_editable, is_gender_editable=is_role_editable,
                is_ethnicity_editable=is_role_editable,
                is_disposition_editable=ds_level > 0 and is_role_editable,
                is_protagonist_editable=is_role_editable
            )
            performer_models.append(model)
        self.view.update_performer_editors(performer_models)

    def _refresh_thematic_panel(self):
        available = self.get_filtered_available_thematic_tags()
        self.view.update_available_thematic_tags(available)
        
        all_tags, _, _ = self.controller.get_thematic_tags_for_planner()
        all_tags_map = {t['full_name']: t for t in all_tags}
        selected_data = [all_tags_map[tag_name] for tag_name in self.working_scene.global_tags if tag_name in all_tags_map]
        self.view.update_selected_thematic_tags(selected_data)

    def _refresh_physical_panel(self):
        available = self.get_filtered_available_physical_tags()
        self.view.update_available_physical_tags(available)
        
        all_tags, _, _ = self.controller.get_physical_tags_for_planner()
        all_tags_map = {t['full_name']: t for t in all_tags}
        selected_data = [all_tags_map[tag_name] for tag_name in self.working_scene.assigned_tags.keys() if tag_name in all_tags_map]
        self.view.update_selected_physical_tags(selected_data, self.selected_physical_tag_name)
        
        current_item = self.view.selected_physical_list.currentItem()
        current_tag_name = current_item.text() if current_item else ""
        self.on_selected_physical_tag_changed(current_tag_name)

    def _refresh_action_segment_panel(self):
        available = self.get_filtered_available_action_tags()
        self.view.update_available_action_tags(available)
        
        segments = self.working_scene.action_segments
        total_percent = sum(s.runtime_percentage for s in segments)
        if total_percent == 100:
            status = 'good'
        elif total_percent > 100:
            status = 'bad'
        else: # < 100
            status = 'neutral' if total_percent == 0 else 'warning'
        runtime_model = TotalRuntimeViewModel(
            text=f"<b>Total Assigned: {total_percent}%</b>",
            status=status
        )
        self.view.update_selected_action_segments(segments, self.controller.tag_definitions, self.selected_segment_id, runtime_model)
        # Refresh details pane. If nothing selected (e.g. last item deleted), pass 0/None to clear the pane.
        # We use 0 (or -0) as the sentinel for "None" in this context.
        segment_id_to_refresh = self.selected_segment_id if self.selected_segment_id else 0
        self.on_selected_action_segment_changed(segment_id_to_refresh)

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

    def handle_composition_change(self):
        performers_data = self.view.get_composition_data()
        self.state_editor.update_composition(performers_data)
        current_item = self.view.selected_physical_list.currentItem()
        current_tag_name = current_item.text() if current_item else ""
        self.on_selected_physical_tag_changed(current_tag_name); self._refresh_action_segment_panel()
        self._refresh_physical_panel()
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

    def handle_add_thematic_tags(self):
        tag_names = self.view.get_selected_available_thematic_tags()
        self.state_editor.add_style_tags(tag_names)
        self._refresh_thematic_panel()
        self._update_summary()
    def handle_remove_thematic_tags(self):
        tag_names = self.view.get_selected_assigned_thematic_tags()
        self.state_editor.remove_style_tags(tag_names)
        self._refresh_thematic_panel()
        self._update_summary()

    def handle_add_physical_tags(self):
        tag_names = self.view.get_selected_available_physical_tags()
        if not tag_names: return
        self.state_editor.add_style_tags(tag_names)
        self.selected_physical_tag_name = sorted(tag_names)[0]
        self._refresh_physical_panel()
        self._update_summary()
    def handle_remove_physical_tags(self):
        tag_names = self.view.get_selected_assigned_physical_tags()
        if not tag_names: return
        if self.selected_physical_tag_name in tag_names:
            self.selected_physical_tag_name = None
        self.state_editor.remove_style_tags(tag_names)
        self._refresh_physical_panel()
        self._update_summary()

    def on_selected_physical_tag_changed(self, tag_name: str):
        if not tag_name:
            self.view.update_physical_assignment_panel(None, [], [], False)
            return
        raw_name = tag_name.lstrip("⭐ ")
        all_tags, _, _ = self.controller.get_physical_tags_for_planner()
        tag_data = next((t for t in all_tags if t['full_name'] == raw_name), None)
        if not tag_data: return
        self.selected_physical_tag_name = raw_name
        eligible_performers_data = []
        for vp in self.working_scene.virtual_performers:
            # Check eligibility against the tag definition using the controller
            if self.controller.is_performer_eligible_for_tag(vp, raw_name):
                talent = self.get_talent_by_id(self.working_scene.final_cast.get(str(vp.id)))
                eligible_performers_data.append({
                    'display_name': talent.alias if talent else vp.name, 'is_cast': talent is not None,
                    'gender': vp.gender, 'ethnicity': vp.ethnicity, 'vp_id': vp.id
                })
        assigned_ids = self.working_scene.assigned_tags.get(raw_name, [])
        self.view.update_physical_assignment_panel(tag_data, eligible_performers_data, assigned_ids, self.is_design_editable())

    def on_physical_tag_assignment_changed(self, tag_name: str, vp_id: int, is_assigned: bool):
        self.state_editor.update_style_tag_assignment(tag_name, vp_id, is_assigned)
        self._update_summary()

    def handle_add_action_segments(self):
        tag_names = self.view.get_selected_available_action_tags()
        if not tag_names: return
        new_ids = self.state_editor.add_action_segments(tag_names)
        if new_ids: self.selected_segment_id = new_ids[0]
        self._refresh_action_segment_panel()
        self._update_summary()
    def handle_remove_action_segments(self):
        segment_ids = self.view.get_selected_assigned_action_segment_ids()
        if not segment_ids: return
        if self.selected_segment_id in segment_ids:
            self.selected_segment_id = None
        self.state_editor.remove_action_segments(segment_ids)
        # After removing, if there are segments left and nothing is selected, select the first one.
        if not self.selected_segment_id and self.working_scene.action_segments:
            self.selected_segment_id = sorted(self.working_scene.action_segments, key=lambda s: s.tag_name)[0].id
        self._refresh_action_segment_panel()
        self._update_summary()

    def on_selected_action_segment_changed(self, segment_id: int):
        if segment_id == 0:
            self.selected_segment_id = None; self.view.update_segment_details(None, {}, {}, {}, False)
            return
        
        segment = next((s for s in self.working_scene.action_segments if s.id == segment_id), None)
        self.selected_segment_id = segment_id
        if not segment: self.view.update_segment_details(None, {}, {}, {}, False); return

        vp_options_by_slot = {}; tag_def = self.controller.tag_definitions.get(segment.tag_name)
        effective_genders_by_slot = {} # Store calculated gender requirements
        if tag_def:
            assignments_map = {sa.slot_id: sa for sa in segment.slot_assignments}
            current_assignments_ids = {sa.slot_id: sa.virtual_performer_id for sa in segment.slot_assignments}
            for slot_def in tag_def.get('slots', []):
                count = segment.parameters.get(slot_def['role'], slot_def.get('count', 1))
                for i in range(count):
                    slot_id = f"{tag_def.get('name', segment.tag_name)}_{slot_def['role']}_{i+1}"
                    # Calculate Effective Gender Label
                    effective_genders_by_slot[slot_id] = self._calculate_effective_gender_req(
                        tag_def, slot_def, slot_id, assignments_map
                    )
                    
                    vps_assigned_elsewhere = {vp_id for sid, vp_id in current_assignments_ids.items() if sid != slot_id and vp_id is not None}
                    eligible_vps = []

                    # Create a map for the validator
                    vp_map = {vp.id: vp for vp in self.working_scene.virtual_performers}

                    for vp in self.working_scene.virtual_performers:
                        talent = self.get_talent_by_id(self.working_scene.final_cast.get(str(vp.id)))
                        gender_req = slot_def.get('gender')
                        gender_ok = not gender_req or gender_req == "Any" or vp.gender == gender_req
                        # Check orientation validity dynamically
                        orientation_ok = True
                        if gender_ok:
                             orientation_ok = self.controller.tag_validation_checker.is_assignment_valid_for_segment(
                                segment, tag_def, vp_map, slot_id, slot_def['role'], vp.id
                             )

                        if gender_ok and orientation_ok and vp.id not in vps_assigned_elsewhere:
                            eligible_vps.append((talent.alias if talent else vp.name, vp.id))
                    vp_options_by_slot[slot_id] = eligible_vps
        self.view.update_segment_details(segment, self.controller.tag_definitions, vp_options_by_slot, effective_genders_by_slot, self.is_design_editable())

    def on_segment_runtime_changed(self, segment_id: int, percentage: int):
        self.state_editor.update_action_segment_runtime(segment_id, percentage)
        self._refresh_action_segment_panel()
        self._update_summary()
    def on_segment_parameter_changed(self, segment_id: int, role: str, value: int):
        self.state_editor.update_action_segment_parameter(segment_id, role, value)
        self._refresh_action_segment_panel()
        self._update_summary()
    def on_slot_assignment_changed(self, segment_id: int, slot_id: str, role: str, vp_id: int):
        # The view emits 0 for "Unassigned"
        self.state_editor.update_slot_assignment(segment_id, slot_id, role, vp_id if vp_id != 0 else None)
        current_item = self.view.selected_actions_list.currentItem()
        current_segment_id = current_item.data(Qt.ItemDataRole.UserRole) if current_item else -1
        self.on_selected_action_segment_changed(current_segment_id)
        self._update_summary()

    def on_save_requested(self):
        self.controller.update_scene_full(self.state_editor.finalize_for_saving())
        self.view.accept()

    def on_cancel_requested(self):
        self.view.reject()

    def on_delete_requested(self, penalty_percentage: float): self.controller.delete_scene(self.working_scene.id, penalty_percentage=penalty_percentage); self.view.accept()
    
    # --- Preset Management ---

    def _get_scene_data_for_preset(self) -> Dict:
        """Callback for PresetHandler to get data to save."""

        scene_data = dataclasses.asdict(self.working_scene)
        
        # DEBUG: Log what is about to be saved to verify if 'id' is leaking
        logger.debug(f"[PRESET SAVE] Raw scene data keys before filter: {list(scene_data.keys())}")
        if 'id' in scene_data:
            logger.debug(f"[PRESET SAVE] Scene ID present in raw data: {scene_data['id']}")

        fields_to_keep = [
            'title', 'focus_target', 'total_runtime_minutes', 'dom_sub_dynamic_level',
            'virtual_performers', 'global_tags', 'assigned_tags', 'action_segments',
            'protagonist_vp_ids'
        ]
        
        result = {key: scene_data.get(key) for key in fields_to_keep}
        
        # DEBUG: Verify final payload
        if 'id' in result:
            logger.error(f"[PRESET SAVE] CRITICAL: 'id' field leaked into saved preset data! Value: {result['id']}")
        else:
            logger.debug("[PRESET SAVE] 'id' field successfully excluded from preset.")

        return result

    def _apply_preset_to_scene(self, preset_data: Dict):
        # BUG: Sometimes it will fail to move to the Casting phase, removing the action segments.
        # Doesn't seem to be a timing issue.
        """Callback for PresetHandler to apply loaded data."""
        
        # DEBUG: Trace ID restoration
        original_id = self.working_scene.id
        logger.debug(f"[PRESET LOAD] Original Scene ID before apply: {original_id}")

        if 'id' in preset_data:
             logger.warning(f"[PRESET LOAD] Warning: Preset data contains 'id': {preset_data['id']}. This should have been filtered out.")

        # Reconstruct a new Scene object from the preset data
        scene_from_preset = self._scene_from_preset_data(preset_data)
        
        # DEBUG: Check ID of constructed scene object
        logger.debug(f"[PRESET LOAD] Constructed Scene ID from preset: {scene_from_preset.id}")

        # Preserve essential current scene data that should not be overwritten by a preset
        original_status = self.working_scene.status
        original_bloc_id = self.working_scene.bloc_id
        original_scheduled_absolute_week = self.working_scene.scheduled_absolute_week
        original_final_cast = self.working_scene.final_cast
        original_is_locked = self.working_scene.is_locked

        # Overwrite the state editor's working scene
        self.state_editor.working_scene = scene_from_preset

        # Restore the preserved data
        self.state_editor.working_scene.id = original_id
        self.state_editor.working_scene.status = original_status
        self.state_editor.working_scene.bloc_id = original_bloc_id
        self.state_editor.working_scene.scheduled_absolute_week = original_scheduled_absolute_week
        self.state_editor.working_scene.final_cast = original_final_cast
        self.state_editor.working_scene.is_locked = original_is_locked
        
        # DEBUG: Final verification
        if self.state_editor.working_scene.id != original_id:
             logger.error(f"[PRESET LOAD] CRITICAL: Scene ID mismatch after restoration! Expected {original_id}, got {self.state_editor.working_scene.id}")
        else:
             logger.debug(f"[PRESET LOAD] Scene ID successfully restored to {self.state_editor.working_scene.id}")
        
        # The presenter's own selection state needs to be reset
        self.selected_physical_tag_name = None
        self.selected_segment_id = None

        # Refresh entire UI from the new working_scene state
        self._refresh_full_view()

    def _scene_from_preset_data(self, data: dict) -> Scene:
        """Helper to reconstruct a Scene object from preset data, creating new temporary IDs and remapping references."""
        scene_data = copy.deepcopy(data) # Create a deep copy to avoid modifying the cached preset in SettingsManager
        
        # Inject placeholders for required Scene fields not present in presets.
        # These will be overwritten by the actual scene context in _apply_preset_to_scene.
        required_fields = {
            'id': 0, 
            'status': 'design', 
            'scheduled_absolute_week': 0, 
            'location': 'Studio'
        }
        for k, v in required_fields.items():
            scene_data.setdefault(k, v)
        
        new_vps, old_vp_id_map = [], {}
        logger.debug("[PRESET MAP] Starting VP Mapping...")
        for i, vp_data in enumerate(scene_data.get('virtual_performers', [])):
            old_id = vp_data.get('id')
            # Use a base offset (e.g. -100) to avoid the ID '-1', which can cause conflicts 
            # with Qt sentinel values (Invalid Index) in QComboBox logic.
            new_id = -(i + 101) 
            
            # Explicitly cast to int to handle potential string IDs from JSON
            if old_id is not None:
                try:
                    old_id_int = int(old_id)
                    old_vp_id_map[old_id_int] = new_id
                    # Also map string version just in case key lookup uses string later
                    old_vp_id_map[str(old_id)] = new_id 
                except ValueError:
                    logger.warning(f"[PRESET MAP] Could not convert VP ID '{old_id}' to int.")

            logger.debug(f"[PRESET MAP] VP Index {i}: Old ID {old_id} -> New ID {new_id}")
            
            vp_data['id'] = new_id
            new_vps.append(VirtualPerformer(**vp_data))
            
        scene_data['virtual_performers'] = new_vps
        
        # Remap Protagonists
        new_protagonists = []
        for old_id in scene_data.get('protagonist_vp_ids', []):
             # Try int first, then as-is
             mapped = old_vp_id_map.get(int(old_id) if isinstance(old_id, (int, str)) and str(old_id).lstrip('-').isdigit() else old_id)
             if mapped is not None:
                 new_protagonists.append(mapped)
        scene_data['protagonist_vp_ids'] = sorted(new_protagonists)

        # Remap Assigned Tags
        if 'assigned_tags' in scene_data:
            new_assigned_tags = {}
            for tag, oids in scene_data['assigned_tags'].items():
                new_oids = []
                for oid in oids:
                     mapped = old_vp_id_map.get(int(oid) if isinstance(oid, (int, str)) and str(oid).lstrip('-').isdigit() else oid)
                     if mapped is not None: new_oids.append(mapped)
                new_assigned_tags[tag] = new_oids
            scene_data['assigned_tags'] = new_assigned_tags

        # Remap Action Segments
        new_segments = []
        for i, seg_data in enumerate(scene_data.get('action_segments', [])):
            seg_data['id'] = -(i + 101)
            assignments_data = seg_data.pop('slot_assignments', [])
            
            new_assignments = []
            for sa_dict in assignments_data:
                sa = SlotAssignment(**sa_dict)
                
                # Handle type conversion for lookup
                raw_vp_id = sa.virtual_performer_id
                lookup_key = raw_vp_id
                if raw_vp_id is not None and isinstance(raw_vp_id, (int, str)) and str(raw_vp_id).lstrip('-').isdigit():
                     lookup_key = int(raw_vp_id)
                
                mapped_id = old_vp_id_map.get(lookup_key)
                
                # Log the mapping attempt for the first few segments/slots
                if i == 0:
                     logger.debug(f"[PRESET MAP] Seg 0 Slot {sa.slot_id}: Raw VP {raw_vp_id} (Key {lookup_key}) -> Mapped {mapped_id}")

                sa.virtual_performer_id = mapped_id
                new_assignments.append(sa)

            segment = ActionSegment(**seg_data); segment.slot_assignments = new_assignments; new_segments.append(segment)
        scene_data['action_segments'] = new_segments
        return Scene(**{k: v for k, v in scene_data.items() if k in Scene.__annotations__})
    
    def on_favorites_changed(self): self.update_favorites(); self._refresh_thematic_panel(); self._refresh_physical_panel(); self._refresh_action_segment_panel()
    def on_toggle_favorite_requested(self, tag_name: str, tag_type: str): self.toggle_favorite_tag(tag_name, tag_type)

    def _calculate_effective_gender_req(self, tag_def: Dict, slot_def: Dict, current_slot_id: str, assignments_map: Dict[str, SlotAssignment]) -> str:
        """
        Determines the 'runtime' gender requirement for a slot.
        e.g. If a Straight tag has a Male in slot A, slot B becomes 'Female' (instead of Any).
        """
        base_gender = slot_def.get('gender', 'Any')

        # If the slot has a fixed gender (not Any or Dependent), that's the requirement.
        if base_gender not in ['Any', 'Dependent']:
            return base_gender

        orientation = tag_def.get('orientation')

        # If the tag is explicitly strictly gendered by definition, return that.
        if orientation in ['Gay', 'Male']: return 'Male'
        if orientation in ['Lesbian', 'Female']: return 'Female'

        # If it's Straight (Fluid), determine context
        if orientation == 'Straight':
            # 1. Look at peers to find constraints
            for sa in assignments_map.values():
                if sa.slot_id == current_slot_id or not sa.virtual_performer_id:
                    continue
                
                vp = next((v for v in self.working_scene.virtual_performers if v.id == sa.virtual_performer_id), None)
                if not vp: continue

                # Check peer role vs my role
                # Same Role -> Same Gender. Different Role -> Opposite Gender.
                if sa.role == slot_def['role']:
                    if vp.gender == 'Male': return 'Male'
                    if vp.gender == 'Female': return 'Female'
                else:
                    if vp.gender == 'Male': return 'Female'
                    if vp.gender == 'Female': return 'Male'

            # 2. Look at self (If I am already assigned, I take that gender)
            if my_assignment := assignments_map.get(current_slot_id):
                my_vp = next((v for v in self.working_scene.virtual_performers if v.id == my_assignment.virtual_performer_id), None)
                if my_vp:
                    return my_vp.gender
        return base_gender

    # --- Data Access & Helpers ---
    def _update_summary(self):
        """Prepares and sends summary data to the view."""
        summary_data = prepare_summary_data(self.working_scene, self.controller)
        self.view.update_summary_view(summary_data)

    def _get_bloc_info_text(self) -> str:
        if not self.working_scene: return ""
        if self.parent_bloc:
            bloc_year, bloc_week = time_utils.from_absolute(self.parent_bloc.scheduled_absolute_week)
            return f"Part of '{self.parent_bloc.name}' shooting on Week {bloc_week}, {bloc_year}"
        
        scene_year, scene_week = time_utils.from_absolute(self.working_scene.scheduled_absolute_week)
        return f"Scheduled for Week {scene_week}, {scene_year}"

    def get_talent_by_id(self, talent_id: int) -> Optional[Talent]:
        if talent_id is None:
            return None
        
        if talent_id in self._talent_cache: return self._talent_cache[talent_id]
        talent = self.controller.get_talent_by_id(talent_id)
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
                fresh_scene = self.controller.get_scene_by_id(self.working_scene.id)
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
        # Guard against accessing a deleted view (zombie presenter issue)
        if not self.view or sip.isdeleted(self.view):
            return
            
        # Re-fetch the scene data from the authoritative source
        fresh_scene = self.controller.get_scene_by_id(self.working_scene.id)

        if fresh_scene == self.state_editor.original_scene:
            return

        if not fresh_scene:
            # The scene was likely deleted by another process. Close the dialog.
            logger.info(f"Scene {self.working_scene.id} no longer exists. Closing planner.")
            try:
                self.view.close()
            except RuntimeError:
                # View was deleted, nothing to close
                pass
            return
            
        # The scene still exists. Reset our local state and refresh the entire view.
        self.state_editor.reset_with_scene(fresh_scene)
        try:
            self._refresh_full_view()
        except RuntimeError:
            # View was deleted during refresh
            pass