
import copy
import logging
from typing import Optional, List, Dict, Tuple

from data.game_state import Scene, VirtualPerformer, ActionSegment, SlotAssignment
from data.data_manager import DataManager
from services.calculation.tag_validation_checker import TagValidationChecker

logger = logging.getLogger(__name__)

class SceneStateEditor:
    """
    Service class responsible for managing the state of a Scene during the editing process.
    
    It maintains a working copy of the scene to allow for transactional edits (save/cancel),
    handles complex logic like updating performer counts (adding/removing virtual performers),
    managing tags (thematic, physical), and validating scene status transitions (e.g., to Casting).
    """
    def __init__(self, scene_to_edit: Scene, data_manager: DataManager, tag_validator: TagValidationChecker):
        self.working_scene = copy.deepcopy(scene_to_edit)
        self.original_scene = scene_to_edit
        self.data_manager = data_manager
        self.tag_validator = tag_validator
        
    def reset_with_scene(self, new_scene: Scene):
        """
        Resets the editor's state with a fresh Scene object from the database.
        This is used to synchronize state after an external change, like casting.
        """
        # We use deepcopy to ensure our working copy is fully independent.
        self.working_scene = copy.deepcopy(new_scene)
        self.original_scene = new_scene

    def set_title(self, title: str):
        """Updates the title of the working scene."""
        self.working_scene.title = title

    def set_focus_target(self, target: str):
        """Updates the focus target (viewer group) of the working scene."""
        self.working_scene.focus_target = target

    def set_total_runtime(self, minutes: int):
        """Updates the total runtime of the scene in minutes."""
        self.working_scene.total_runtime_minutes = minutes

    def set_ds_level(self, level: int):
        """Updates the Dom/Sub dynamic level of the scene."""
        self.working_scene.dom_sub_dynamic_level = level

    def update_performer_count(self, new_count: int):
        """
        Updates the number of virtual performers in the scene.
        
        If increasing, adds new VirtualPerformer objects with temporary negative IDs.
        If decreasing, removes performers from the end of the list and cleans up 
        any associated tag assignments or slot assignments for the removed IDs.
        """
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
        """
        Updates the attributes (name, gender, ethnicity, disposition) of the virtual performers
        based on data from the UI editors.
        """
        for i, data in enumerate(performers_data):
            if i < len(self.working_scene.virtual_performers):
                vp = self.working_scene.virtual_performers[i]
                vp.name = data['name']
                vp.gender = data['gender']
                vp.ethnicity = data['ethnicity']
                vp.disposition = data['disposition']

    def add_style_tag(self, tag_name: str):
        """
        Adds a style tag (Thematic or Physical) to the scene.
        
        - Thematic tags are added to `global_tags`.
        - Physical tags are added to `assigned_tags` with an empty list of assignments initially.
        """
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
        """Removes a style tag from the scene."""
        tag_data = self.data_manager.tag_definitions.get(tag_name)
        if not tag_data: return
        if tag_data.get('type') == 'Thematic' and tag_name in self.working_scene.global_tags: self.working_scene.global_tags.remove(tag_name)
        elif tag_data.get('type') == 'Physical' and tag_name in self.working_scene.assigned_tags: del self.working_scene.assigned_tags[tag_name]

    def update_style_tag_assignment(self, tag_name: str, vp_id: int, is_assigned: bool):
        """Updates the assignment of a specific performer to a physical tag."""
        current_list = self.working_scene.assigned_tags.setdefault(tag_name, [])
        if is_assigned and vp_id not in current_list: current_list.append(vp_id)
        elif not is_assigned and vp_id in current_list: current_list.remove(vp_id)

    def add_action_segment(self, tag_name: str) -> Optional[int]:
        """
        Adds a new action segment to the scene based on the given tag name.
        Initializes parameters based on the tag definition.
        Returns the ID of the new segment.
        """
        tag_def = self.data_manager.tag_definitions.get(tag_name)
        if not tag_def: return None
        params = {}
        for slot in tag_def.get("slots", []):
            if role := slot.get("role"): params[role] = slot.get('count', slot.get('min_count', 1))
        new_id = - (max([abs(s.id) for s in self.working_scene.action_segments if s.id < 0] + [0]) + 1)
        new_segment = ActionSegment(id=new_id, tag_name=tag_name, parameters=params)
        self.working_scene.action_segments.append(new_segment)
        return new_id
    
    def add_style_tags(self, tag_names: List[str]):
        for tag_name in tag_names: self.add_style_tag(tag_name)
    def remove_style_tags(self, tag_names: List[str]):
        for tag_name in tag_names: self.remove_style_tag(tag_name)
    def add_action_segments(self, tag_names: List[str]) -> List[int]:
        return [self.add_action_segment(tag_name) for tag_name in tag_names]
    def remove_action_segments(self, segment_ids: List[int]):
        for segment_id in segment_ids: self.remove_action_segment(segment_id)

    def remove_action_segment(self, segment_id: int):
        """Removes an action segment by its ID."""
        self.working_scene.action_segments = [s for s in self.working_scene.action_segments if s.id != segment_id]

    def update_action_segment_runtime(self, segment_id: int, percentage: int):
        """Updates the runtime percentage of a specific action segment."""
        for s in self.working_scene.action_segments:
            if s.id == segment_id: s.runtime_percentage = percentage; break

    def update_action_segment_parameter(self, segment_id: int, role: str, value: int):
        """Updates a parameter (e.g., count of a role) for a specific action segment."""
        for s in self.working_scene.action_segments:
            if s.id == segment_id: s.parameters[role] = value; break

    def update_slot_assignment(self, segment_id: int, slot_id: str, vp_id: Optional[int]):
        """
        Updates the assignment of a performer to a specific slot in an action segment.
        Removes any existing assignment for that slot before adding the new one.
        """
        for s in self.working_scene.action_segments:
            if s.id == segment_id:
                s.slot_assignments = [sa for sa in s.slot_assignments if sa.slot_id != slot_id]
                if vp_id is not None:
                    s.slot_assignments.append(SlotAssignment(slot_id=slot_id, virtual_performer_id=vp_id))
                break
    
    def set_protagonist_status(self, vp_id: int, is_protagonist: bool):
        """Updates the protagonist status for a given virtual performer."""
        current_protagonists = set(self.working_scene.protagonist_vp_ids)
        if is_protagonist:
            current_protagonists.add(vp_id)
        else:
            current_protagonists.discard(vp_id)
        self.working_scene.protagonist_vp_ids = sorted(list(current_protagonists))

    def validate_and_set_status(self, new_status: str) -> Tuple[bool, str]:
        """
        Attempts to transition the scene to a new status (e.g., 'Casting', 'Scheduled').
        Performs validation checks appropriate for the target status.
        
        Returns:
            (success, error_message)
        """
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
        
        unassigned_physical_tags = self._get_unassigned_physical_tags()
        if unassigned_physical_tags:
            return "Cannot proceed to Casting. The following physical tags have insufficient performers:\n\n- " + "\n- ".join(unassigned_physical_tags)

        # Validate orientation constraints (e.g. preventing M/M in a Straight tag)
        vp_map = {vp.id: vp for vp in self.working_scene.virtual_performers}
        for segment in self.working_scene.action_segments:
            tag_def = self.data_manager.tag_definitions.get(segment.tag_name)
            is_valid, error = self.tag_validator.validate_action_segment_orientation(segment, tag_def, vp_map)
            if not is_valid:
                return f"Cannot proceed to Casting.\n\nIssue in '{segment.tag_name}':\n{error}"

        return None

    def _get_validation_errors_for_scheduling(self) -> Optional[str]:
        total_runtime = sum(seg.runtime_percentage for seg in self.working_scene.action_segments)
        if total_runtime != 100:
            return f"Total action segment runtime must be 100% to schedule a scene (currently {total_runtime}%)."

        is_fully_cast = len(self.working_scene.final_cast) == len(self.working_scene.virtual_performers)
        if not is_fully_cast:
            return f"All {len(self.working_scene.virtual_performers)} roles must be cast to schedule the scene."
            
        return None
    
    def _get_unassigned_physical_tags(self) -> List[str]:
        unassigned_tags = []
        for tag_name, assigned_vp_ids in self.working_scene.assigned_tags.items():
            tag_def = self.data_manager.tag_definitions.get(tag_name)
            if not tag_def or tag_def.get('type') != 'Physical':
                continue

            required_count = 1
            validation_rule = tag_def.get('validation_rule')
            if validation_rule and validation_rule.get('mode') == 'match_all':
                required_count = len(validation_rule.get('profiles', []))
                if required_count == 0: required_count = 2 # Fallback

            if len(assigned_vp_ids) < required_count:
                unassigned_tags.append(f"'{tag_name}' (requires at least {required_count} performer(s), has {len(assigned_vp_ids)})")
        return unassigned_tags

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
