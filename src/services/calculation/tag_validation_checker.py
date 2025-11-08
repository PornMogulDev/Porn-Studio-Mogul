    
import logging
from itertools import permutations
from typing import List, Dict, Set, Optional

from data.game_state import Talent
from data.data_manager import DataManager

logger = logging.getLogger(__name__)

class TagValidationChecker:
    """
    A pure logic class responsible for discovering Physical tags based on
    the composition of a scene's cast.
    """
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

        
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
                if is_match and (req_ethnicity := profile.get("ethnicity")) and getattr(performer, 'ethnicity', None) != req_ethnicity:
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
            if (req_ethnicity := tag_def.get('ethnicity')) and getattr(performer, 'ethnicity', None) != req_ethnicity:
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
        """
        Validates if a permutation of the cast satisfies a compositional rule.
        Returns the matched performers if a valid permutation is found, otherwise None.
        """
        profiles = rule.get("profiles", [])
        if not profiles or len(cast) < len(profiles): 
            return None
            
        # Using permutations is computationally expensive, but necessary for correctness with small cast sizes.
        for cast_permutation in permutations(cast, len(profiles)):
            matched_performers, is_valid_permutation = [], True
            for i, profile in enumerate(profiles):
                performer = cast_permutation[i]
                if (profile.get("gender") and performer.gender != profile.get("gender")) or \
                   (profile.get("ethnicity") and performer.ethnicity != profile.get("ethnicity")) or \
                   (profile.get("min_age") is not None and performer.age < profile.get("min_age")) or \
                   (profile.get("max_age") is not None and performer.age > profile.get("max_age")):
                    is_valid_permutation = False
                    break
                matched_performers.append(performer)
            
            if not is_valid_permutation: 
                continue
            
            if "min_gap_years" in rule:
                older = next((p for i, p in enumerate(matched_performers) if profiles[i].get("role") == "older"), None)
                younger = next((p for i, p in enumerate(matched_performers) if profiles[i].get("role") == "younger"), None)
                if not (older and younger and (older.age - younger.age) >= rule["min_gap_years"]):
                    continue # This permutation doesn't meet the age gap, try the next one

            return matched_performers # Found a valid permutation
        
        return None