import random
from typing import Dict, List, Any, Optional
import numpy as np
from collections import defaultdict

from data.game_state import Talent

class TalentGenerator:
    def __init__(self, game_constant: dict, generator_data: dict, affinity_data: dict, tag_definitions: dict, talent_archetypes: list):
        self.game_constant = game_constant
        self.genders_data = generator_data.get('genders', [])
        self.alias_data = generator_data.get('aliases', {})
        self.ethnicity_data = generator_data.get('ethnicities', [])
        self.cup_size_data = generator_data.get('cup_sizes', []) 
        self.affinity_data = affinity_data
        self.tag_definitions = tag_definitions
        self.talent_archetypes = talent_archetypes
        self.gen_config = self.game_constant.get("talent_generation", {})
            
        # New nationality-based data
        self.nationalities_data = generator_data.get('nationalities', [])
        self.locations_by_nationality = generator_data.get('locations_by_nationality', {})
        self.ethnicities_by_nationality = generator_data.get('ethnicities_by_nationality', {})
        self.name_data = generator_data.get('names_by_culture', {})
        self.ethnicity_definitions = generator_data.get('ethnicity_definitions', {})
        # Fallback names
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
        # Younger ages are more likely
        weights = np.linspace(age_config['weight_start'], age_config['weight_end'], len(ages))
        weights /= weights.sum()
        return int(np.random.choice(ages, p=weights))

    def _generate_skill(self) -> int:
        """Generates a random skill value, weighted towards the middle."""
        skill_config = self.gen_config.get("skill", {"min": 10.0, "max": 100.0, "mode": 65.0})
        return random.triangular(skill_config['min'], skill_config['max'], skill_config['mode'])

    def _generate_attribute(self, archetype_mods: Optional[Dict] = None) -> int:
        if archetype_mods:
            return random.randint(archetype_mods['min'], archetype_mods['max'])
        attr_config = self.gen_config.get("attribute", {"min": 1, "max": 10, "mode": 5})
        return int(random.triangular(attr_config['min'], attr_config['max'], attr_config['mode']))

    def _generate_gender(self) -> str:
        """Generates a gender based on weighted choices from data."""
        return self._weighted_choice(self.genders_data)

    def _generate_nationality(self) -> str:
        return self._weighted_choice(self.nationalities_data)

    def _generate_location(self, nationality: str) -> str:
        locations = self.locations_by_nationality.get(nationality, [])
        return self._weighted_choice(locations)

    def _generate_ethnicity(self, nationality: str) -> tuple[str, str]:
        """Returns a tuple of (sub_ethnicity, primary_ethnicity)."""
        ethnicities = self.ethnicities_by_nationality.get(nationality, [])
        sub_ethnicity = self._weighted_choice(ethnicities)
        primary_ethnicity = self.ethnicity_definitions.get(sub_ethnicity, sub_ethnicity) # Fallback to self
        return sub_ethnicity, primary_ethnicity

    def _get_name_list(self, culture_key: str, gender: str, part: str) -> List[str]:
        """
        1. Try specific culture key.
        2. Use hardcoded defaults.
        """
        try:
            names = self.name_data[culture_key][gender][part]
            if names:
                return names
        except KeyError:
            pass # Continue to default

        return self.default_names.get(gender, {}).get(part, ["Default"])

    def _generate_alias(self, gender: str, nationality: str, ethnicity: str) -> str:
        """
        Generates a gender and ethnicity-appropriate alias.
        Can be a single name or a first/last name combo.
        """
        # Construct culture key, e.g., "us_western_european"
        nat_key_map = {'US': 'us', 'Japanese': 'japanese', 'Canadian': 'canadian', 'British': 'british',
                       'French': 'french', 'Colombian': 'colombian', 'Brazilian': 'brazilian',
                       'Russian': 'russian', 'German': 'german', 'Spanish': 'spanish', 'Italian': 'italian',
                       'Czech': 'czech', 'Hungarian': 'hungarian'}
        eth_key = ethnicity.lower().replace(' ', '_')
        nat_key = nat_key_map.get(nationality, 'default')
        culture_key = f"{nat_key}_{eth_key}"
        single_name_chance = self.gen_config.get("alias_single_name_chance", 0.15)
        
        if random.random() < single_name_chance:
            name_list = self._get_name_list(culture_key, gender, 'single')
            return random.choice(name_list)
        
        first_name_list = self._get_name_list(culture_key, gender, 'first')
        last_name_list = self._get_name_list(culture_key, gender, 'last')

        first_name = random.choice(first_name_list)
        last_name = random.choice(last_name_list)

        return f"{first_name} {last_name}"

    def _generate_dick_size(self) -> int:
        """Generates a dick size in inches, weighted towards 7-10."""
        dick_config = self.gen_config.get("dick_size", {"min": 2, "max": 15, "mode": 8})
        return int(round(random.triangular(dick_config['min'], dick_config['max'], dick_config['mode'])))

    def _generate_orientation_score(self) -> int:
        """Generates an orientation score from -100 (straight) to 100 (gay/lesbian)."""
        orient_config = self.gen_config.get("orientation_score", {"min": -100, "max": 100, "mode": 0})
        return int(round(random.triangular(orient_config['min'], orient_config['max'], orient_config['mode'])))

    def _generate_disposition_score(self) -> int:
        """Generates a disposition score from -100 (sub) to 100 (dom)."""
        disp_config = self.gen_config.get("disposition_score", {"min": -100, "max": 100, "mode": 0})
        return int(round(random.triangular(disp_config['min'], disp_config['max'], disp_config['mode'])))

    def _assign_archetype(self) -> dict:
        """Performs a weighted random choice to assign a talent archetype."""
        choices = list(self.talent_archetypes.values())
        weights = [item.get('weight', 1) for item in choices]
        return random.choices(choices, weights=weights, k=1)[0]

    def _generate_preferences_and_limits(self, gender: str, orientation_score: int, disposition_score: int, archetype_data: dict) -> tuple[Dict[str, Dict[str, float]], List[str]]:
        """
        Generates role-based tag preferences and hard limits based on an archetype,
        orientation, and D/S disposition, using a Specific > Base > Concept hierarchy.
        """
        prefs: Dict[str, Dict[str, float]] = defaultdict(dict)
        limits = archetype_data.get("hard_limits", []).copy()
        
        preference_shift_intensity = self.game_constant.get('preference_shift_intensity', 0.5)
        hard_limit_threshold = self.game_constant.get('hard_limit_threshold', 0.1)
        archetype_action_prefs = archetype_data.get("action_preferences", {})

        # Calculate shifters once
        ds_balance = disposition_score / 100.0
        
        for full_name, tag_def in self.tag_definitions.items():
            if tag_def.get('type') != 'Action':
                continue

            slots = tag_def.get('slots', [])
            if not any(slot.get('gender') == gender or slot.get('gender') == "Any" for slot in slots):
                continue

            # Calculate orientation multiplier for the tag
            orientation_targets = {"Straight": -100, "Gay": 100, "Lesbian": 100}
            tag_orientation = tag_def.get('orientation')
            curve_config = self.gen_config.get("orientation_multiplier_curve", {"distance": [0, 150, 200], "multiplier": [1.0, 0.4, 0.05]})
            orientation_multiplier = 1.0
            if tag_orientation and tag_orientation in orientation_targets:
                target_score = orientation_targets[tag_orientation]
                distance = abs(orientation_score - target_score)
                orientation_multiplier = np.interp(distance, curve_config['distance'], curve_config['multiplier'])

            # Iterate through each specific role (slot) in the tag
            for slot_def in slots:
                if not (slot_def.get('gender') == gender or slot_def.get('gender') == "Any"):
                    continue

                role = slot_def['role']
                dynamic_role = slot_def.get('dynamic_role', 'Neutral')
                
                # THREE-TIER HIERARCHICAL PREFERENCE LOOKUP
                base_name = tag_def.get('name')
                concept = tag_def.get('concept')
                
                # Start with a neutral default
                base_pref = 1.0
                
                # 1. Check for Concept preference (most general)
                if concept and concept in archetype_action_prefs and role in archetype_action_prefs[concept]:
                    base_pref = archetype_action_prefs[concept][role]

                # 2. Check for Base Name preference (overwrites concept)
                if base_name and base_name in archetype_action_prefs and role in archetype_action_prefs[base_name]:
                    base_pref = archetype_action_prefs[base_name][role]

                # 3. Check for Full Name preference (most specific, overwrites all others)
                if full_name in archetype_action_prefs and role in archetype_action_prefs[full_name]:
                    base_pref = archetype_action_prefs[full_name][role]
                # --- END NEW LOGIC ---

                # Apply D/S disposition shifter based on the dynamic_role
                adjusted_pref = base_pref
                if dynamic_role == "Dominant":
                    adjusted_pref = base_pref * (1 + ds_balance * preference_shift_intensity)
                elif dynamic_role == "Submissive":
                    adjusted_pref = base_pref * (1 - ds_balance * preference_shift_intensity)
                
                # Combine with orientation and store
                final_score = round(adjusted_pref * orientation_multiplier, 2)
                prefs[full_name][role] = final_score

        # Finalize hard limits: if any role for a tag is below the threshold, the whole tag is a limit.
        tags_to_make_limits = set()
        for tag_name, roles_prefs in prefs.items():
            if any(score < hard_limit_threshold for score in roles_prefs.values()):
                tags_to_make_limits.add(tag_name)

        for tag_name in tags_to_make_limits:
            if tag_name not in limits:
                limits.append(tag_name)
            del prefs[tag_name]

        return dict(prefs), limits


    def _generate_policy_requirements(self, professionalism: int) -> Dict[str, List[str]]:
        """Generates policy requirements based on professionalism."""
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
        else: # If no scores, initialize with 0
            for tag in gender_data:
                affinities[tag] = 0

        return affinities

    def _calculate_boob_affinities(self, cup: str) -> Dict[str, int]:
        boob_affinity_data = self.affinity_data.get("BoobSize", {})
        return boob_affinity_data.get(cup, boob_affinity_data.get("default", {}))

    def _calculate_dick_size_affinities(self, size: int) -> Dict[str, int]:
        """Calculates dick size-based tag affinities."""
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

    def generate_talent(self, talent_id: int) -> Talent:
        """Generates a single, fully-formed Talent object."""
        # Core attributes
        age = self._generate_age()
        gender = self._generate_gender()
        nationality = self._generate_nationality()
        location = self._generate_location(nationality)
        ethnicity, primary_ethnicity = self._generate_ethnicity(nationality) # ethnicity is the sub-group
        
        alias = self._generate_alias(gender, nationality, ethnicity)

        # Archetype and Personality
        archetype_data = self._assign_archetype()
        orientation_score = self._generate_orientation_score()
        disposition_score = self._generate_disposition_score()
        
        # Generate preferences based on archetype and personality
        tag_preferences, hard_limits = self._generate_preferences_and_limits(
            gender, orientation_score, disposition_score, archetype_data
        )

        # Partner Limits from Archetype
        max_scene_partners = archetype_data.get("max_scene_partners", 10)
        variance = self.gen_config.get("max_partners_variance", [-2, 2])
        # Add a small variance for personality
        max_scene_partners = max(1, max_scene_partners + random.randint(variance[0], variance[1]))
        concurrency_limits = archetype_data.get("concurrency_limits", {}).copy()
        for limit_type, base_value in concurrency_limits.items():
            variation = random.randint(-1, 1)
            concurrency_limits[limit_type] = max(1, base_value + variation)

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
        policy_requirements = self._generate_policy_requirements(professionalism)

        # Gender-specific attributes & affinities
        tag_affinities = {}
        cup_size: Optional[str] = None
        dick_size: Optional[int] = None
        
        if gender == "Female":
            cup_size = self._weighted_choice(self.cup_size_data)
            if cup_size and cup_size != "N/A":
                tag_affinities.update(self._calculate_boob_affinities(cup_size))
        else: # Male
            dick_size = self._generate_dick_size()
            tag_affinities.update(self._calculate_dick_size_affinities(dick_size))

        tag_affinities.update(self._calculate_age_affinities(age, gender))

        # Common affinities
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
            location=location,
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
            hard_limits=hard_limits,
            max_scene_partners=max_scene_partners,
            concurrency_limits=concurrency_limits,
            policy_requirements=policy_requirements
        )

    def generate_multiple_talents(self, count: int, start_id: int) -> List[Talent]:
        """Generates a list of new Talent objects."""
        return [self.generate_talent(start_id + i) for i in range(count)]