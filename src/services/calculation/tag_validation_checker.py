    
import logging
from itertools import permutations
from typing import List, Dict, Set, Optional, Tuple

from data.game_state import Talent, ActionSegment, VirtualPerformer
from data.data_manager import DataManager

logger = logging.getLogger(__name__)

class TagValidationChecker:
    """
    A pure logic class responsible for discovering Physical tags based on
    the composition of a scene's cast.
    """
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def validate_action_segment_orientation(self, segment: ActionSegment, tag_def: Dict, performers: Dict[int, VirtualPerformer]) -> Tuple[bool, Optional[str]]:
        """
        Validates that the performers assigned to an action segment respect the 
        tag's orientation constraints. This is crucial for 'Fluid' tags (e.g., 
        Straight tags where slots are 'Any') to prevent invalid pairings.

        Args:
            segment: The ActionSegment to validate.
            tag_def: The dictionary definition of the tag (from DataManager).
            performers: A map of {vp_id: VirtualPerformer} for looking up genders.

        Returns:
            (is_valid, error_message)
        """
        if not tag_def:
            return True, None

        orientation = tag_def.get('orientation')
        if not orientation:
            return True, None

        # Gather genders of currently assigned performers
        assigned_genders = []
        for assignment in segment.slot_assignments:
            if assignment.virtual_performer_id and assignment.virtual_performer_id in performers:
                vp = performers[assignment.virtual_performer_id]
                assigned_genders.append(vp.gender)
        
        # If nobody is assigned yet, we can't invalidate it based on pairing
        if not assigned_genders:
            return True, None

        # 1. Straight Validation
        # A Straight action implies opposite-sex interaction. 
        # If slots are 'Any'/'Any', we must ensure we don't have M/M or F/F.
        if orientation == "Straight":
            # If we have at least 2 people, we enforce the mix.
            if len(assigned_genders) > 1:
                has_male = "Male" in assigned_genders
                has_female = "Female" in assigned_genders
                if not (has_male and has_female):
                    return False, "Straight actions require both Male and Female participants."

        # 2. Gay / Male Validation (No Females)
        elif orientation in ["Gay", "Male"]:
            if "Female" in assigned_genders:
                return False, f"{orientation} actions cannot include Female participants."

        # 3. Lesbian / Female Validation (No Males)
        elif orientation in ["Lesbian", "Female"]:
            if "Male" in assigned_genders:
                return False, f"{orientation} actions cannot include Male participants."

        # Bi / Pan / Template orientations generally allow any combination 
        # (constraints are handled by specific slot requirements, e.g. 'Vaginal' requires Female receiver)

        return True, None
    
    def is_assignment_valid_for_segment(self, segment: ActionSegment, tag_def: Dict, 
                                      performers: Dict[int, VirtualPerformer], 
                                      slot_id: str, candidate_vp_id: int) -> bool:
        """
        Checks if assigning a specific candidate to a specific slot would violate
        orientation rules, considering who is ALREADY assigned to other slots.
        """
        if not tag_def: return True
        
        candidate = performers.get(candidate_vp_id)
        if not candidate: return False

        orientation = tag_def.get('orientation')
        if not orientation: return True

        # 1. Immediate Gender Lock (e.g. Gay tag = No Females allowed ever)
        if orientation in ["Gay", "Male"] and candidate.gender == "Female":
            return False
        if orientation in ["Lesbian", "Female"] and candidate.gender == "Male":
            return False

        # 2. Contextual Lock (Straight tag = Must not match existing genders of same type)
        # e.g. If slot A has a Male, slot B cannot accept a Male.
        if orientation == "Straight":
            # Check genders of peers ALREADY assigned to OTHER slots
            existing_genders = set()
            for assignment in segment.slot_assignments:
                if assignment.slot_id != slot_id and assignment.virtual_performer_id:
                    if peer := performers.get(assignment.virtual_performer_id):
                        existing_genders.add(peer.gender)
            
            # If we are adding a Male, and there is already a Male, it's invalid.
            # (Assuming Straight requires M/F pairing. M/M is invalid).
            # Note: This logic assumes strict M/F. 
            # It prevents M/M/F (Threesome) if strict pairing is enforced, 
            # but for "Fluid Straight" (Any/Any), preventing M+M is the goal.
            if candidate.gender == "Male" and "Male" in existing_genders:
                return False
            if candidate.gender == "Female" and "Female" in existing_genders:
                return False
                
        return True

    def is_performer_eligible_for_tag(self, performer, tag_def: Dict) -> bool:
        """
        Checks if a single performer (Talent or VirtualPerformer) is eligible to be assigned
        to a Physical tag, either by matching a profile in a compositional tag or by
        meeting the top-level requirements of a single-performer tag.
        """
        # Case 1: Compositional Tag with a validation rule
        if validation_rule := tag_def.get('validation_rule'):
            profiles = validation_rule.get("profiles", [])
            if not profiles:
                return True # No specific profiles, so anyone is technically eligible

            for profile in profiles:
                is_match = True
                # Check gender
                if (req_gender := profile.get("gender")) and getattr(performer, 'gender', None) != req_gender:
                    is_match = False
                
                # Check ethnicity
                if is_match and (req_ethnicity := profile.get("ethnicity")):
                    performer_ethnicity = getattr(performer, 'ethnicity', None)
                    if not self.data_manager.is_ethnicity_match(performer_ethnicity, req_ethnicity):
                        is_match = False

                # Check age (safely, as VirtualPerformer won't have it)
                performer_age = getattr(performer, 'age', None)
                if is_match and performer_age is not None:
                    if (min_age := profile.get("min_age")) is not None and performer_age < min_age:
                        is_match = False
                    if is_match and (max_age := profile.get("max_age")) is not None and performer_age > max_age:
                        is_match = False

                # If all checks for this profile passed, the performer is eligible.
                if is_match:
                    return True

            # Performer didn't match any profile in the compositional tag
            return False

        # Case 2: Single-performer Tag (no validation rule, check top-level attributes)
        else:
            # Check top-level gender requirement
            if (req_gender := tag_def.get('gender')) and getattr(performer, 'gender', None) != req_gender:
                return False

            # Check top-level ethnicity requirement
            if req_ethnicity := tag_def.get('ethnicity'):
                performer_ethnicity = getattr(performer, 'ethnicity', None)
                if not self.data_manager.is_ethnicity_match(performer_ethnicity, req_ethnicity):
                    return False

            # All single-performer requirements met (or there were none)
            return True

    def analyze_cast(self, cast_talents: List[Talent], existing_tags: Set[str]) -> List[str]:
        """
        Analyzes a list of talents to discover applicable Physical auto-tags.

        Args:
            cast_talents: A list of Talent dataclasses representing the cast.
            existing_tags: A set of tags already applied to the scene (global or assigned).

        Returns:
            A list of discovered auto-tag names.
        """
        if not cast_talents:
            return []

        discovered_tags = set()

        candidate_tags = [
            (full_name, tag_def) for full_name, tag_def in self.data_manager.tag_definitions.items()
            if tag_def.get('type') == 'Physical' and tag_def.get('is_auto_taggable')
        ]

        for full_name, tag_def in candidate_tags:
            if full_name in existing_tags or full_name in discovered_tags:
                continue
            
            # Case 1: Multi-performer compositional tag (e.g., Interracial, Age Gap)
            if validation_rule := tag_def.get('validation_rule'):
                if self._validate_compositional_tag(cast_talents, validation_rule):
                    discovered_tags.add(full_name)
            
            # Case 2: Single-performer attribute tag (e.g., MILF, Big Dick)
            elif detection_rule := tag_def.get('auto_detection_rule'):
                # Pre-filter cast based on top-level gender/ethnicity
                potential_performers = [
                    t for t in cast_talents
                    if (not tag_def.get('gender') or t.gender == tag_def.get('gender')) and
                       (not tag_def.get('ethnicity') or t.ethnicity == tag_def.get('ethnicity'))
                ]
                if not potential_performers:
                    continue

                # Check if ANY performer meets all conditions
                for performer in potential_performers:
                    if self._check_performer_conditions(performer, detection_rule):
                        discovered_tags.add(full_name)
                        break # Found one, tag is added, move to next tag
                        
        return sorted(list(discovered_tags))

    def _check_performer_conditions(self, performer: Talent, rule: Dict) -> bool:
        """Helper function to check if a single performer meets all conditions in a rule."""
        conditions = rule.get("conditions", []) 
        if not conditions:
            return False

        for cond in conditions:
            cond_type = (cond.get('type') or '').lower()
            key = cond.get('key')
            comparison = cond.get('comparison')
            value = cond.get('value')
            
            actual_value = None
            if cond_type == 'stat':
                actual_value = getattr(performer, key, None)
            elif cond_type == 'affinity':
                actual_value = performer.tag_affinities.get(key)
            elif cond_type == 'physical':
                actual_value = getattr(performer, key, None)
            
            if actual_value is None:
                return False

            is_met = False
            if comparison == 'gte' and actual_value >= value: is_met = True
            elif comparison == 'lte' and actual_value <= value: is_met = True
            elif comparison == 'eq' and actual_value == value: is_met = True
            elif comparison == 'in' and actual_value in value: is_met = True
            
            if not is_met:
                return False
        return True

        
    def _validate_compositional_tag(self, cast: List[Talent], rule: Dict) -> Optional[List[Talent]]:
        profiles = rule.get("profiles", [])
        if len(cast) < len(profiles):
            return None

        # Optimization: Filter candidates by static requirements (Gender/Ethnicity) first
        # This dramatically reduces the N in the N! permutation calculation
        candidates_by_profile = []
        for profile in profiles:
            eligible = []
            for talent in cast:
                # Check basic static stats here
                if profile.get("gender") and talent.gender != profile.get("gender"): continue
                # ... (ethnicity checks) ...
                eligible.append(talent)
            
            if not eligible: return None # Impossible to fill this slot
            candidates_by_profile.append(eligible)

        # Now use a recursive backtracking search (Constraint Satisfaction)
        # instead of raw permutations on the whole cast
        return self._find_valid_assignment(candidates_by_profile, [], set())

    def _find_valid_assignment(self, candidate_lists, current_assignment, used_ids):
        # Base case: All profiles filled
        if len(current_assignment) == len(candidate_lists):
            return current_assignment

        next_profile_idx = len(current_assignment)
        possible_candidates = candidate_lists[next_profile_idx]

        for cand in possible_candidates:
            if cand.id in used_ids: continue
            
            # Check relative constraints (Age Gap) here if needed against current_assignment
            
            result = self._find_valid_assignment(candidate_lists, current_assignment + [cand], used_ids | {cand.id})
            if result: return result
        
        return None