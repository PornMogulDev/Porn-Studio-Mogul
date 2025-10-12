
import copy
import logging
from typing import Optional, List, Dict, Tuple

from game_state import Scene, VirtualPerformer, ActionSegment, Talent, ShootingBloc, SlotAssignment
from data_manager import DataManager

logger = logging.getLogger(__name__)

class SceneEditorService:
    def __init__(self, scene_to_edit: Scene, data_manager: DataManager):
        self.working_scene = copy.deepcopy(scene_to_edit)
        self.data_manager = data_manager

    def set_title(self, title: str):
        self.working_scene.title = title

    def set_focus_target(self, target: str):
        self.working_scene.focus_target = target

    def set_total_runtime(self, minutes: int):
        self.working_scene.total_runtime_minutes = minutes

    def set_ds_level(self, level: int):
        self.working_scene.dom_sub_dynamic_level = level

    def update_performer_count(self, new_count: int):
        current_count = len(self.working_scene.virtual_performers)
        if new_count == current_count:
            return

        if new_count > current_count:
            for i in range(current_count, new_count):
                existing_temp_ids = {abs(vp.id) for vp in self.working_scene.virtual_performers if vp.id < 0}
                temp_id = i + 1
                while temp_id in existing_temp_ids:
                    temp_id += 1
                
                self.working_scene.virtual_performers.append(
                    VirtualPerformer(id=-(temp_id), name=f"Performer {i+1}", gender="Female", ethnicity="Any")
                )
        else:
            removed_vps = self.working_scene.virtual_performers[new_count:]
            removed_ids = {vp.id for vp in removed_vps}
            self.working_scene.virtual_performers = self.working_scene.virtual_performers[:new_count]
            
            if removed_ids:
                for tag_name in list(self.working_scene.assigned_tags.keys()):
                    self.working_scene.assigned_tags[tag_name] = [vp_id for vp_id in self.working_scene.assigned_tags[tag_name] if vp_id not in removed_ids]
                for segment in self.working_scene.action_segments:
                    segment.slot_assignments = [sa for sa in segment.slot_assignments if sa.virtual_performer_id not in removed_ids]

    def update_composition(self, performers_data: List[Dict]):
        for i, data in enumerate(performers_data):
            if i < len(self.working_scene.virtual_performers):
                vp = self.working_scene.virtual_performers[i]
                vp.name = data['name']
                vp.gender = data['gender']
                vp.ethnicity = data['ethnicity']
                vp.disposition = data['disposition']

    def add_style_tag(self, tag_name: str):
        tag_data = self.data_manager.tag_definitions.get(tag_name)
        if not tag_data: return

        tag_type = tag_data.get('type')

        if tag_type == 'Thematic':
            if tag_name not in self.working_scene.global_tags: 
                self.working_scene.global_tags.append(tag_name)
        elif tag_type == 'Physical':
             self.working_scene.assigned_tags.setdefault(tag_name, [])
        else:
            # Fallback for old style tags if any exist, or for action tags being added incorrectly
            # This part can be adjusted based on how you handle other tag types
            logger.warning(f"[Warning] add_style_tag called with unhandled tag type: {tag_type} for '{tag_name}'")
            # For now, let's assume non-thematic/physical tags might be assigned.
            self.working_scene.assigned_tags.setdefault(tag_name, [])

    def remove_style_tag(self, tag_name: str):
        tag_data = self.data_manager.tag_definitions.get(tag_name)
        if not tag_data: return
        if tag_data.get('type') == 'Global' and tag_name in self.working_scene.global_tags: self.working_scene.global_tags.remove(tag_name)
        elif tag_data.get('type') == 'Assigned' and tag_name in self.working_scene.assigned_tags: del self.working_scene.assigned_tags[tag_name]

    def update_style_tag_assignment(self, tag_name: str, vp_id: int, is_assigned: bool):
        current_list = self.working_scene.assigned_tags.setdefault(tag_name, [])
        if is_assigned and vp_id not in current_list: current_list.append(vp_id)
        elif not is_assigned and vp_id in current_list: current_list.remove(vp_id)

    def add_action_segment(self, tag_name: str) -> Optional[int]:
        tag_def = self.data_manager.tag_definitions.get(tag_name)
        if not tag_def: return None
        params = {}
        for slot in tag_def.get("slots", []):
            if role := slot.get("role"): params[role] = slot.get('count', slot.get('min_count', 1))
        new_id = - (max([abs(s.id) for s in self.working_scene.action_segments if s.id < 0] + [0]) + 1)
        new_segment = ActionSegment(id=new_id, tag_name=tag_name, parameters=params)
        self.working_scene.action_segments.append(new_segment)
        return new_id

    def remove_action_segment(self, segment_id: int):
        self.working_scene.action_segments = [s for s in self.working_scene.action_segments if s.id != segment_id]

    def update_action_segment_runtime(self, segment_id: int, percentage: int):
        for s in self.working_scene.action_segments:
            if s.id == segment_id: s.runtime_percentage = percentage; break

    def update_action_segment_parameter(self, segment_id: int, role: str, value: int):
        for s in self.working_scene.action_segments:
            if s.id == segment_id: s.parameters[role] = value; break

    def update_slot_assignment(self, segment_id: int, slot_id: str, vp_id: Optional[int]):
        for s in self.working_scene.action_segments:
            if s.id == segment_id:
                s.slot_assignments = [sa for sa in s.slot_assignments if sa.slot_id != slot_id]
                if vp_id is not None:
                    s.slot_assignments.append(SlotAssignment(slot_id=slot_id, virtual_performer_id=vp_id))
                break

    def validate_and_set_status(self, new_status: str) -> Tuple[bool, str]:
        new_status_lower = new_status.lower()
        
        if new_status_lower == 'casting':
            message = self._get_validation_errors_for_casting()
            if message:
                return False, message
        
        if new_status_lower == 'scheduled':
            message = self._get_validation_errors_for_scheduling()
            if message:
                return False, message

        self.working_scene.status = new_status.lower()
        return True, ""

    def _get_validation_errors_for_casting(self) -> Optional[str]:
        total_runtime = sum(seg.runtime_percentage for seg in self.working_scene.action_segments)
        if total_runtime != 100:
            return f"Total action segment runtime must be 100% to enter Casting (currently {total_runtime}%)."
        
        unassigned_slots = self._get_unassigned_slots()
        if unassigned_slots:
            return "Cannot proceed to Casting. The following roles are unassigned:\n\n- " + "\n- ".join(unassigned_slots)
            
        return None

    def _get_validation_errors_for_scheduling(self) -> Optional[str]:
        total_runtime = sum(seg.runtime_percentage for seg in self.working_scene.action_segments)
        if total_runtime != 100:
            return f"Total action segment runtime must be 100% to schedule a scene (currently {total_runtime}%)."

        is_fully_cast = len(self.working_scene.final_cast) == len(self.working_scene.virtual_performers)
        if not is_fully_cast:
            return f"All {len(self.working_scene.virtual_performers)} roles must be cast to schedule the scene."
            
        return None

    def _get_unassigned_slots(self) -> List[str]:
        unassigned_slots = []
        for segment in self.working_scene.action_segments:
            tag_def = self.data_manager.tag_definitions.get(segment.tag_name)
            if not tag_def: continue
            
            assigned_slot_ids = {sa.slot_id for sa in segment.slot_assignments}
            
            for slot_def in tag_def.get('slots', []):
                count = segment.parameters.get(slot_def['role'], slot_def.get('min_count', 1)) \
                    if slot_def.get("parameterized_by") == "count" else slot_def.get('count', 1)
                for i in range(count):
                    base_name = tag_def.get('name', segment.tag_name)
                    slot_id = f"{base_name}_{slot_def['role']}_{i+1}"
                    if slot_id not in assigned_slot_ids:
                        unassigned_slots.append(f"'{segment.tag_name}' ({slot_def['role']} #{i+1})")
        return unassigned_slots

    def finalize_for_saving(self) -> Scene:
        """Prepares the scene object for being saved, setting lock status."""
        status = self.working_scene.status.lower()
        if status == 'casting' or len(self.working_scene.final_cast) > 0:
            self.working_scene.is_locked = True
        else:
            self.working_scene.is_locked = False
        return self.working_scene
