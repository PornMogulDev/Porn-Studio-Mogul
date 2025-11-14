from dataclasses_json import dataclass_json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass_json
@dataclass
class MarketGroupState:
    name: str
    current_saturation: float = 1.0
    discovered_sentiments: Dict[str, List[str]] = field(default_factory=dict)

@dataclass_json
@dataclass
class EmailMessage:
    id: int; subject: str; body: str; week: int; year: int; is_read: bool = False

@dataclass_json
@dataclass
class Talent: #type: ignore
    id: int; alias: str; age: int; gender: str
    nationality: str; primary_ethnicity: str
    performance: float; acting: float; stamina: float
    dom_skill: float; sub_skill: float
    ambition: int
    professionalism: int = 5
    orientation_score: int = 0
    disposition_score: int = 0
    experience: float = 0.0
    base_location: str = ""
    current_location: str = ""
    chemistry: Dict[int, int] = field(default_factory=dict)
    popularity: Dict[str, float] = field(default_factory=dict)
    ethnicity: Optional[str] = None
    cup_size: Optional[str] = None
    dick_size: Optional[int] = None
    tag_affinities: Dict[str, int] = field(default_factory=dict)
    fatigue: int = 0
    fatigue_end_week: int = 0
    fatigue_end_year: int = 0
    tag_preferences: Dict[str, Dict[str, float]] = field(default_factory=dict)
    hard_limits: List[str] = field(default_factory=list)
    max_scene_partners: int = 10
    concurrency_limits: Dict[str, int] = field(default_factory=dict)
    policy_requirements: Dict[str, List[str]] = field(default_factory=dict)
    is_on_tour: bool = False
    tour_end_week: int = 0
    tour_end_year: int = 0

@dataclass_json
@dataclass
class VirtualPerformer:
    name: str
    gender: str
    ethnicity: str = "Any"
    disposition: str = "Switch"
    id: Optional[int] = None

@dataclass_json
@dataclass
class SlotAssignment:
    slot_id: str
    virtual_performer_id: int
    id: Optional[int] = None

@dataclass_json
@dataclass
class ActionSegment:
    tag_name: str
    id: Optional[int] = None
    runtime_percentage: int = 10
    slot_assignments: List[SlotAssignment] = field(default_factory=list)
    parameters: Dict[str, int] = field(default_factory=dict)

@dataclass_json
@dataclass
class ScenePerformerContribution:
    scene_id: int
    talent_id: int
    contribution_key: str
    quality_score: float
    id: Optional[int] = None

@dataclass_json
@dataclass
class Scene:
    id: int; title: str; status: str; focus_target: str
    scheduled_week: int; scheduled_year: int
    bloc_id: Optional[int] = None
    dom_sub_dynamic_level: int = 0
    protagonist_vp_ids: List[int] = field(default_factory=list)
    scene_type: Optional[str] = None
    is_locked: bool = False
    total_runtime_minutes: int = 10
    virtual_performers: List[VirtualPerformer] = field(default_factory=list)
    global_tags: List[str] = field(default_factory=list)
    assigned_tags: Dict[str, List[int]] = field(default_factory=dict)
    action_segments: List[ActionSegment] = field(default_factory=list)
    auto_tags: List[str] = field(default_factory=list)
    final_cast: Dict[str, int] = field(default_factory=dict)
    pps_salaries: Dict[str, int] = field(default_factory=dict)
    weeks_remaining: int = 0
    tag_qualities: Dict[str, float] = field(default_factory=dict)
    performer_contributions: List[ScenePerformerContribution] = field(default_factory=list)
    revenue: int = 0
    viewer_group_interest: Dict[str, float] = field(default_factory=dict)
    performer_stamina_costs: Dict[str, float] = field(default_factory=dict)
    revenue_modifier_details: Dict[str, float] = field(default_factory=dict)
    post_production_choices: Dict[str, Any] = field(default_factory=dict)

    @property
    def display_status(self) -> str:
        status_text = self.status.replace('_', ' ').title()
        if self.status == 'in_editing':
            return f"{status_text} ({self.weeks_remaining}w left)"
        if self.status == 'casting':
            return f"Casting ({len(self.final_cast)}/{len(self.virtual_performers)})"
        return status_text

    def get_expanded_action_segments(self, tag_definitions: dict) -> List[ActionSegment]:
        expanded_segments = []
        for segment in self.action_segments:
            tag_def = tag_definitions.get(segment.tag_name, {})
            expansion_rules = tag_def.get('expands_to')
            if not expansion_rules:
                expanded_segments.append(segment)
                continue
            
            total_ratio = sum(rule['runtime_ratio'] for rule in expansion_rules)
            if total_ratio == 0: continue
            
            for rule in expansion_rules:
                child_tag_name, child_ratio = rule['tag_name'], rule['runtime_ratio']
                role_map = rule.get('role_map', {})
                remapped_assignments = []
                for parent_assignment in segment.slot_assignments:
                    try: _, parent_role, slot_index = parent_assignment.slot_id.rsplit('_', 2)
                    except ValueError: continue
                    child_role = role_map.get(parent_role, parent_role)
                    child_tag_def = tag_definitions.get(child_tag_name, {})
                    child_base_name = child_tag_def.get('name', child_tag_name)
                    child_slot_id = f"{child_base_name}_{child_role}_{slot_index}"
                    remapped_assignments.append(SlotAssignment(slot_id=child_slot_id, virtual_performer_id=parent_assignment.virtual_performer_id))
                
                child_params = rule.get('parameters', {}).copy()
                for parent_role, parent_value in segment.parameters.items():
                    child_params[role_map.get(parent_role, parent_role)] = parent_value
                
                if child_tag_def := tag_definitions.get(child_tag_name):
                    # Ensure all roles from the child definition are in the params if not already set.
                    for slot in child_tag_def.get("slots", []):
                        role = slot.get("role")
                        if role and role not in child_params:
                            count = slot.get('count', slot.get('min_count', 1))
                            child_params[role] = count
                
                expanded_segments.append(ActionSegment(
                    id=segment.id, tag_name=child_tag_name,
                    runtime_percentage=segment.runtime_percentage * (child_ratio / total_ratio),
                    slot_assignments=remapped_assignments, parameters=child_params
                ))
        return expanded_segments

    def _get_slots_for_segment(self, segment: ActionSegment, tag_definitions: dict) -> List[Dict]:
        tag_def = tag_definitions.get(segment.tag_name)
        if not tag_def: return []
        resolved_slots = []
        for slot_def in tag_def.get('slots', []):
            count = segment.parameters.get(slot_def['role'], slot_def.get('min_count', 1)) \
                if slot_def.get("parameterized_by") == "count" else slot_def.get('count', 1)
            for _ in range(count):
                resolved_slots.append(slot_def)
        return resolved_slots

@dataclass_json
@dataclass
class ShootingBloc:
    id: int
    name: str
    scheduled_week: int
    scheduled_year: int
    production_settings: Dict[str, str] = field(default_factory=dict) # Key: category, Value: tier_name
    production_cost: int = 0
    scenes: List[Scene] = field(default_factory=list)
    on_set_policies: List[str] = field(default_factory=list) # Key: policy_id, e.g., ["policy_condoms_mandatory"]

@dataclass_json
@dataclass
class GameState:
    week: int = 1
    year: int = 0
    money: int = 0
    studio_location: str = ""