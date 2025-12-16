import random
import logging
from typing import Dict, List, Any, Optional, Set
import numpy as np
from collections import defaultdict

from data.game_state import Talent

logger = logging.getLogger(__name__)

class TalentGenerator:
    def __init__(self, game_constant: dict, generator_data: dict, affinity_data: dict, 
                 tag_definitions: dict, talent_archetypes: dict, traits_data: dict):
        self.game_constant = game_constant
        self.genders_data = generator_data.get('genders', [])
        self.alias_data = generator_data.get('aliases', {})
        self.ethnicity_data = generator_data.get('ethnicities', [])
        self.cup_size_data = generator_data.get('cup_sizes', []) 
        self.affinity_data = affinity_data
        self.tag_definitions = tag_definitions
        self.talent_archetypes = talent_archetypes
        self.traits_data = traits_data # New: Full traits definitions
        self.gen_config = self.game_constant.get("talent_generation", {})
            
        # Nationality-based data
        self.nationalities_data = generator_data.get('nationalities', [])
        self.locations_by_nationality = generator_data.get('locations_by_nationality', {})
        self.ethnicities_by_nationality = generator_data.get('ethnicities_by_nationality', {})
        self.name_data = generator_data.get('names_by_culture', {})
        self.ethnicity_definitions = generator_data.get('ethnicity_definitions', {})
        self.default_names = self.name_data.get("default", {})

    def _weighted_choice(self, options: List[Dict[str, Any]]) -> str:
        if not options:
            return "N/A"
        
        choices = [item['name'] for item in options]
        weights = [item['weight'] for item in options]
        
        return random.choices(choices, weights=weights, k=1)[0]

    def _generate_age(self) -> int:
        age_config = self.gen_config.get("age", {"min": 18, "max": 61, "weight_start": 1.0, "weight_end": 0.1})
        ages = list(range(age_config['min'], age_config['max']))
        weights = np.linspace(age_config['weight_start'], age_config['weight_end'], len(ages))
        weights /= weights.sum()
        return int(np.random.choice(ages, p=weights))

    def _generate_skill(self) -> int:
        skill_config = self.gen_config.get("skill", {"min": 10.0, "max": 100.0, "mode": 65.0})
        return random.triangular(skill_config['min'], skill_config['max'], skill_config['mode'])

    def _generate_attribute(self, archetype_mods: Optional[Dict] = None) -> int:
        if archetype_mods:
            # Attributes now defined as {min, max} in archetype
            return random.randint(archetype_mods['min'], archetype_mods['max'])
        attr_config = self.gen_config.get("attribute", {"min": 1, "max": 10, "mode": 5})
        return int(random.triangular(attr_config['min'], attr_config['max'], attr_config['mode']))

    def _generate_gender(self) -> str:
        return self._weighted_choice(self.genders_data)

    def _generate_nationality(self) -> str:
        return self._weighted_choice(self.nationalities_data)

    def _generate_location(self, nationality: str) -> str:
        locations = self.locations_by_nationality.get(nationality, [])
        return self._weighted_choice(locations)

    def _generate_ethnicity(self, nationality: str) -> tuple[str, str]:
        ethnicities = self.ethnicities_by_nationality.get(nationality, [])
        sub_ethnicity = self._weighted_choice(ethnicities)
        primary_ethnicity = self.ethnicity_definitions.get(sub_ethnicity, sub_ethnicity)
        return sub_ethnicity, primary_ethnicity

    def _get_name_list(self, culture_key: str, gender: str, part: str) -> List[str]:
        """
        Retrieves a specific list of names. Returns empty list if not found.
        Does NOT fallback to default immediately, allowing logic to check availability.
        """
        try:
            return self.name_data[culture_key][gender][part]
        except KeyError:
            return []

    def _generate_alias(self, gender: str, nationality: str, ethnicity: str) -> str:
        exception_map = {
            # Placeholder
        }

        # 1. Resolve the prefix (e.g., "US" -> "us", "German" -> "german")
        if nationality in exception_map:
            nat_key = exception_map[nationality]
        else:
            # Fallback: lowercase and replace spaces with underscores
            nat_key = nationality.lower().replace(" ", "_")

        eth_key = ethnicity.lower().replace(' ', '_')
        
        # 2. Determine Culture Keys to try (Specific -> Default)
        # e.g. "us_western_european", then "default"
        culture_keys = [f"{nat_key}_{eth_key}", "default"]
        
        for culture_key in culture_keys:
            # Check availability of name types for this specific culture
            first_names = self._get_name_list(culture_key, gender, 'first')
            last_names = self._get_name_list(culture_key, gender, 'last')
            single_names = self._get_name_list(culture_key, gender, 'single')
            
            has_full_name = len(first_names) > 0 and len(last_names) > 0
            has_single_name = len(single_names) > 0
            
            # If neither exist for this culture, try the next fallback (e.g., 'default')
            if not has_full_name and not has_single_name:
                continue

            # 2. Decide Format
            single_name_chance = self.gen_config.get("alias_single_name_chance", 0.15)
            use_single = False

            if has_single_name and has_full_name:
                # Both available, roll dice
                use_single = random.random() < single_name_chance
            elif has_single_name:
                # Only single available
                use_single = True
            else:
                # Only full available
                use_single = False
            
            # 3. Generate
            if use_single:
                return random.choice(single_names)
            else:
                return f"{random.choice(first_names)} {random.choice(last_names)}"
        
        # Fallback if even 'default' is broken
        return "Unknown Talent"

    def _generate_dick_size(self) -> int:
        dick_config = self.gen_config.get("dick_size", {"min": 2, "max": 15, "mode": 8})
        return int(round(random.triangular(dick_config['min'], dick_config['max'], dick_config['mode'])))

    def _generate_orientation_score(self) -> int:
        orient_config = self.gen_config.get("orientation_score", {"min": -100, "max": 100, "mode": 0})
        return int(round(random.triangular(orient_config['min'], orient_config['max'], orient_config['mode'])))

    def _generate_disposition_score(self) -> int:
        disp_config = self.gen_config.get("disposition_score", {"min": -100, "max": 100, "mode": 0})
        return int(round(random.triangular(disp_config['min'], disp_config['max'], disp_config['mode'])))

    def _assign_archetype(self) -> dict:
        choices = list(self.talent_archetypes.values())
        weights = [item.get('weight', 1) for item in choices]
        return random.choices(choices, weights=weights, k=1)[0]

    def _select_traits(self, archetype_data: dict) -> List[str]:
        """
        Selects traits for the talent based on archetype weights.
        """
        selected_traits: Set[str] = set()
        
        # 1. Load Configuration
        trait_weights = archetype_data.get("trait_weights", {}) 
        
        max_traits = self.gen_config.get("max_traits", 3)
        base_chance = self.gen_config.get("base_trait_chance", 0.3)

        # 2. Helper to check conflicts
        def has_conflict(trait_id: str, current_set: Set[str]) -> bool:
            trait_def = self.traits_data.get(trait_id)
            if not trait_def: return False
            conflicts = trait_def.get("conflicts_with", [])
            return any(c in current_set for c in conflicts)

        # 3. Select traits based on weights defined in Archetype
        if trait_weights:
            potential_traits = [t for t in trait_weights.keys() if t in self.traits_data]
            # Extract weights in the same order
            weights = [trait_weights[t] for t in potential_traits]
            
            # Attempt to add traits until max is reached or random chance fails
            attempts = 0
            while len(selected_traits) < max_traits and attempts < 10:
                attempts += 1
                # Standard random check to see if we add another trait
                if len(selected_traits) > 0 and random.random() > base_chance: 
                    break 

                if not potential_traits: break

                # Weighted random choice
                choice = random.choices(potential_traits, weights=weights, k=1)[0]
                
                if choice not in selected_traits and not has_conflict(choice, selected_traits):
                    selected_traits.add(choice)
        
        return list(selected_traits)

    def _generate_ds_dynamic_preferences(self, archetype_data: dict) -> Dict[int, float]:
        """
        Generates the 0-3 intensity preference curve.
        Reads from archetype['dynamic_preference_weights'].
        """
        base_weights = archetype_data.get("dynamic_preference_weights", {})
        preferences = {}
        
        for level in range(4): # 0, 1, 2, 3
            level_str = str(level)
            if level_str in base_weights:
                # Pick random value between min/max defined in archetype
                min_v = base_weights[level_str].get("min", 1.0)
                max_v = base_weights[level_str].get("max", 1.0)
                preferences[level] = round(random.uniform(min_v, max_v), 2)
            else:
                preferences[level] = 1.0
                
        return preferences

    def _apply_trait_preferences(self, prefs: Dict[str, Dict[str, float]], traits: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Applies trait modifiers to the base preferences.
        Traits can modify specific actions (Tag -> Role) or thematic categories (Thematic -> All Matching Tags).
        """
        for trait_id in traits:
            trait_def = self.traits_data.get(trait_id)
            if not trait_def: continue

            # 1. Specific Action Modifiers
            if action_mods := trait_def.get("action_preference_modifiers"):
                for tag_name, roles_mods in action_mods.items():
                    if tag_name in prefs:
                        for role, mod in roles_mods.items():
                            if role in prefs[tag_name]:
                                prefs[tag_name][role] = round(prefs[tag_name][role] * mod, 2)

            # 2. Thematic Modifiers (e.g., "Kink" boosts all kink tags)
            if thematic_mods := trait_def.get("thematic_preference_modifiers"):
                for theme, mod in thematic_mods.items():
                    # Find all tags in prefs that match this theme (via concept or categories)
                    for tag_name, roles_prefs in prefs.items():
                        tag_def = self.tag_definitions.get(tag_name)
                        if not tag_def: continue
                        
                        is_match = (tag_def.get('concept') == theme) or \
                                   (theme in tag_def.get('categories', []))
                        
                        if is_match:
                            for role in roles_prefs:
                                prefs[tag_name][role] = round(prefs[tag_name][role] * mod, 2)
                                
        return prefs

    def _generate_preferences_and_limits(
        self, gender: str, orientation_score: int, disposition_score: int, 
        archetype_data: dict, traits: List[str]
    ) -> tuple[Dict[str, Dict[str, float]], List[str]]:
        """
        Generates role-based tag preferences and hard limits.
        Hierarchy: Base Calculation (Archetype/Personality) -> Trait Modifiers -> Hard Limit Check.
        """
        prefs: Dict[str, Dict[str, float]] = defaultdict(dict)
        limits = archetype_data.get("hard_limits", []).copy()
        
        preference_shift_intensity = self.game_constant.get('preference_shift_intensity', 0.5)
        hard_limit_threshold = self.game_constant.get('hard_limit_threshold', 0.1)
        # Legacy support: if archetypes still have explicit lists, use them as base, otherwise generic defaults
        archetype_action_prefs = archetype_data.get("action_preferences", {}) 

        # Calculate shifters once
        ds_balance = disposition_score / 100.0
        
        # --- 1. Base Calculation ---
        for full_name, tag_def in self.tag_definitions.items():
            if tag_def.get('type') != 'Action': continue

            slots = tag_def.get('slots', [])
            if not any(slot.get('gender') == gender or slot.get('gender') == "Any" for slot in slots):
                continue

            # Orientation Multiplier
            orientation_targets = {"Straight": -100, "Gay": 100, "Lesbian": 100}
            tag_orientation = tag_def.get('orientation')
            curve_config = self.gen_config.get("orientation_multiplier_curve", {"distance": [0, 150, 200], "multiplier": [1.0, 0.4, 0.05]})
            orientation_multiplier = 1.0
            if tag_orientation and tag_orientation in orientation_targets:
                target_score = orientation_targets[tag_orientation]
                distance = abs(orientation_score - target_score)
                orientation_multiplier = np.interp(distance, curve_config['distance'], curve_config['multiplier'])

            # Role iteration
            for slot_def in slots:
                if not (slot_def.get('gender') == gender or slot_def.get('gender') == "Any"):
                    continue

                role = slot_def['role']
                dynamic_role = slot_def.get('dynamic_role', 'Neutral')
                
                # Preference Lookup (Specific > Concept > Default 1.0)
                base_name = tag_def.get('name')
                concept = tag_def.get('concept')
                base_pref = 1.0
                
                if concept and concept in archetype_action_prefs and role in archetype_action_prefs[concept]:
                    base_pref = archetype_action_prefs[concept][role]
                if base_name and base_name in archetype_action_prefs and role in archetype_action_prefs[base_name]:
                    base_pref = archetype_action_prefs[base_name][role]
                if full_name in archetype_action_prefs and role in archetype_action_prefs[full_name]:
                    base_pref = archetype_action_prefs[full_name][role]

                # Apply D/S disposition shifter
                adjusted_pref = base_pref
                if dynamic_role == "Dominant":
                    adjusted_pref = base_pref * (1 + ds_balance * preference_shift_intensity)
                elif dynamic_role == "Submissive":
                    adjusted_pref = base_pref * (1 - ds_balance * preference_shift_intensity)
                
                final_score = round(adjusted_pref * orientation_multiplier, 2)
                prefs[full_name][role] = final_score

        # --- 2. Apply Trait Modifiers ---
        prefs = self._apply_trait_preferences(prefs, traits)

        # --- 3. Determine Hard Limits ---
        tags_to_make_limits = set()
        for tag_name, roles_prefs in prefs.items():
            # If any role for a tag is below threshold, the whole tag becomes a limit
            if any(score < hard_limit_threshold for score in roles_prefs.values()):
                tags_to_make_limits.add(tag_name)

        for tag_name in tags_to_make_limits:
            if tag_name not in limits:
                limits.append(tag_name)
            del prefs[tag_name]

        return dict(prefs), limits


    def _generate_policy_requirements(self, professionalism: int) -> Dict[str, List[str]]:
        policy_rules = self.gen_config.get("policy_rules", [])
        reqs = {"requires": [], "refuses": []}

        for rule in policy_rules:
            is_met = False
            comparison = rule.get("comparison", "gte")
            if comparison == "gte" and professionalism >= rule.get("pro_level", 99):
                is_met = True
            elif comparison == "lte" and professionalism <= rule.get("pro_level", -1):
                is_met = True
            
            if is_met and random.random() < rule.get("chance", 0.0):
                req_type = rule.get("type") # 'requires' or 'refuses'
                if req_type and req_type in reqs:
                    reqs[req_type].append(rule.get("policy_id"))

        return reqs

    def _calculate_age_affinities(self, age: int, gender: str) -> Dict[str, int]:
        affinities = {}
        gender_data = self.affinity_data.get(gender)
        if not gender_data:
            return affinities

        raw_scores = {}
        for tag, data in gender_data.items():
            age_points = data.get("age_points", [])
            values = data.get("values", [])
            if age_points and values:
                raw_scores[tag] = np.interp(age, age_points, values)
        
        total_raw_score = sum(raw_scores.values())
        if total_raw_score > 0:
            for tag, raw_score in raw_scores.items():
                affinities[tag] = int(round((raw_score / total_raw_score) * 100))
        else: 
            for tag in gender_data:
                affinities[tag] = 0

        return affinities

    def _calculate_boob_affinities(self, cup: str) -> Dict[str, int]:
        boob_affinity_data = self.affinity_data.get("BoobSize", {})
        return boob_affinity_data.get(cup, boob_affinity_data.get("default", {}))

    def _calculate_dick_size_affinities(self, size: int) -> Dict[str, int]:
        dick_size_data = self.affinity_data.get("DickSize", {})
        size_points = dick_size_data.get("size_points", [])
        tags_data = dick_size_data.get("tags", {})

        if not size_points or not tags_data:
            return {}

        raw_scores = {}
        for tag, values in tags_data.items():
            raw_scores[tag] = np.interp(size, size_points, values)

        total = sum(raw_scores.values())
        if total == 0:
            return {tag: 0 for tag in tags_data}

        return {tag: int(round((raw_score / total) * 100)) for tag, raw_score in raw_scores.items()}

    def _get_concurrency_limits(self, archetype_data: dict, traits: List[str]) -> Dict[str, int]:
        """
        Generates concurrency limits based on archetype ranges and trait modifiers.
        """
        limits = {}
        
        # 1. Base Archetype Limits (Range)
        arch_limits = archetype_data.get("concurrency_limits", {})
        for limit_type, data in arch_limits.items():
            if isinstance(data, dict) and 'min' in data and 'max' in data:
                limits[limit_type] = random.randint(data['min'], data['max'])
            elif isinstance(data, int):
                # Legacy support if using integers
                limits[limit_type] = data

        # 2. Trait Modifiers (Range or Flat)
        for trait_id in traits:
            trait_def = self.traits_data.get(trait_id)
            if not trait_def: continue
            
            trait_concurrency = trait_def.get("concurrency_modifiers", {})
            for limit_type, data in trait_concurrency.items():
                # Traits override base if they exist
                if isinstance(data, dict) and 'min' in data and 'max' in data:
                    limits[limit_type] = random.randint(data['min'], data['max'])
                elif isinstance(data, int):
                    limits[limit_type] = data
                    
        return limits

    def generate_talent(self, talent_id: int) -> Talent:
        """Generates a single, fully-formed Talent object."""
        # Core attributes
        age = self._generate_age()
        gender = self._generate_gender()
        nationality = self._generate_nationality()
        location = self._generate_location(nationality)
        ethnicity, primary_ethnicity = self._generate_ethnicity(nationality) 
        
        alias = self._generate_alias(gender, nationality, ethnicity)

        # Archetype, Personality, Traits
        archetype_data = self._assign_archetype()
        archetype_id = archetype_data['id']
        orientation_score = self._generate_orientation_score()
        disposition_score = self._generate_disposition_score()
        
        traits = self._select_traits(archetype_data)

        if archetype_id:
            traits.insert(0, archetype_id)
            
        ds_dynamic_preferences = self._generate_ds_dynamic_preferences(archetype_data)

        # Generate preferences (incorporating traits)
        tag_preferences, hard_limits = self._generate_preferences_and_limits(
            gender, orientation_score, disposition_score, archetype_data, traits
        )

        # Partner Limits (Archetype range)
        max_scene_partners_range = archetype_data.get("max_scene_partners", {"min": 5, "max": 15})
        if isinstance(max_scene_partners_range, int): 
             max_scene_partners = max_scene_partners_range # Legacy support
        else:
             max_scene_partners = random.randint(max_scene_partners_range.get('min', 5), max_scene_partners_range.get('max', 15))
        
        concurrency_limits = self._get_concurrency_limits(archetype_data, traits)

        # Skills
        performance = self._generate_skill()
        acting = self._generate_skill()
        stamina = self._generate_skill()
        dom_skill = self._generate_skill()
        sub_skill = self._generate_skill()

        # Attributes (potentially modified by archetype)
        stat_mods = archetype_data.get('stat_modifiers', {})
        ambition = self._generate_attribute(stat_mods.get('ambition'))
        professionalism = self._generate_attribute(stat_mods.get('professionalism'))
        
        # Policy reqs also need to check traits for specific overrides
        policy_requirements = self._generate_policy_requirements(professionalism)
        for t_id in traits:
            if t_reqs := self.traits_data.get(t_id, {}).get('policy_requirements'):
                for p in t_reqs.get('requires', []):
                    if p not in policy_requirements['requires']: policy_requirements['requires'].append(p)
                for p in t_reqs.get('refuses', []):
                    if p not in policy_requirements['refuses']: policy_requirements['refuses'].append(p)

        # Gender-specific attributes & affinities
        tag_affinities = {}
        cup_size: Optional[str] = None
        dick_size: Optional[int] = None
        
        if gender == "Female":
            cup_size = self._weighted_choice(self.cup_size_data)
            if cup_size and cup_size != "N/A":
                tag_affinities.update(self._calculate_boob_affinities(cup_size))
        else: 
            dick_size = self._generate_dick_size()
            tag_affinities.update(self._calculate_dick_size_affinities(dick_size))

        tag_affinities.update(self._calculate_age_affinities(age, gender))

        if ethnicity and ethnicity != "N/A":
            affinity_score = self.gen_config.get("ethnicity_self_affinity_score", 100)
            tag_affinities[ethnicity] = affinity_score
            
        return Talent(
            id=talent_id,
            alias=alias,
            age=age,
            ethnicity=ethnicity,
            primary_ethnicity=primary_ethnicity,
            nationality=nationality,
            base_location=location,
            current_location=location,
            gender=gender,
            performance=performance,
            acting=acting,
            stamina=stamina,
            dom_skill=dom_skill,
            sub_skill=sub_skill,
            ambition=ambition,
            professionalism=professionalism,
            orientation_score=orientation_score,
            disposition_score=disposition_score,
            cup_size=cup_size,
            dick_size=dick_size,
            tag_affinities=tag_affinities,
            tag_preferences=tag_preferences,
            ds_dynamic_preferences=ds_dynamic_preferences,
            traits=traits,
            hard_limits=hard_limits,
            max_scene_partners=max_scene_partners,
            concurrency_limits=concurrency_limits,
            policy_requirements=policy_requirements
        )

    def generate_multiple_talents(self, count: int, start_id: int) -> List[Talent]:
        return [self.generate_talent(start_id + i) for i in range(count)]