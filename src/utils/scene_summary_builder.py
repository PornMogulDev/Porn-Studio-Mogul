from typing import Dict, List
from collections import defaultdict

from data.game_state import Scene, VirtualPerformer
from core.interfaces import IGameController

def prepare_summary_data(scene: Scene, controller: IGameController) -> Dict:
    """
    Processes a Scene object and returns a structured dictionary
    suitable for display in a summary widget.

    Args:
        scene: The Scene object to process (can be a working copy or a final one).
        controller: The game controller for accessing services like talent lookups.

    Returns:
        A dictionary containing structured information about the scene.
    """
    summary = {
        "performers": [],
        "thematic_tags": [],
        "physical_tags": [],
        "action_segments": []
    }

    # Helper to get talent alias if cast, otherwise VP name
    vp_map = {vp.id: vp for vp in scene.virtual_performers}
    talent_cache = {}

    def get_performer_display_name(vp_id: int) -> str:
        if talent_id := scene.final_cast.get(str(vp_id)):
            if talent_id in talent_cache:
                return talent_cache[talent_id]
            if talent := controller.get_talent_by_id(talent_id):
                talent_cache[talent_id] = talent.alias
                return talent.alias
        
        return vp_map.get(vp_id, VirtualPerformer(name="Unknown", gender="N/A")).name

    # 1. Process Performers
    for vp in scene.virtual_performers:
        talent_alias = get_performer_display_name(vp.id)
        
        summary["performers"].append({
            "role_name": vp.name,
            "gender": vp.gender,
            "ethnicity": vp.ethnicity,
            "disposition": vp.disposition,
            "cast_talent_alias": talent_alias if scene.final_cast.get(str(vp.id)) else "Uncast"
        })

    # 2. Process Thematic Tags
    summary["thematic_tags"] = sorted(scene.global_tags)

    # 3. Process Physical Tags
    for tag_name, assigned_vp_ids in sorted(scene.assigned_tags.items()):
        if not (tag_def := controller.tag_definitions.get(tag_name)) or tag_def.get('type') != 'Physical':
            continue
            
        assigned_names = [get_performer_display_name(vp_id) for vp_id in assigned_vp_ids]
        summary["physical_tags"].append({
            "tag_name": tag_name,
            "assigned_performers": sorted(assigned_names)
        })

    # 4. Process Action Segments
    for segment in sorted(scene.action_segments, key=lambda s: s.tag_name):
        segment_data = {
            "segment_name": f"{segment.tag_name} ({segment.runtime_percentage}%)",
            "assignments": []
        }
        
        # Build a map of all expected slots for this segment
        all_slots = defaultdict(lambda: {"count": 0, "assigned": []})
        tag_def = controller.tag_definitions.get(segment.tag_name)
        if tag_def:
            for slot_def in tag_def.get('slots', []):
                role = slot_def['role']
                count = segment.parameters.get(role) if slot_def.get("parameterized_by") == "count" else slot_def.get('count', 1)
                all_slots[role]["count"] = count

        # Populate assignments
        for assignment in segment.slot_assignments:
            # e.g., slot_id is "ActionName_RoleName_1"
            try:
                role = assignment.slot_id.rsplit('_', 2)[-2]
                display_name = get_performer_display_name(assignment.virtual_performer_id)
                all_slots[role]["assigned"].append(display_name)
            except (IndexError, ValueError):
                continue # Skip malformed slot IDs

        # Format for display
        for role, data in sorted(all_slots.items()):
            for i in range(data['count']):
                assigned_performer = data['assigned'][i] if i < len(data['assigned']) else "<i>Unassigned</i>"
                segment_data["assignments"].append({
                    "role": f"{role} #{i+1}",
                    "assigned_performer": assigned_performer
                })

        summary["action_segments"].append(segment_data)

    return summary