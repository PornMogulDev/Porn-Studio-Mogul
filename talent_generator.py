import random
from typing import Dict, List, Any, Optional
import numpy as np
from collections import defaultdict

from game_state import Talent

class TalentGenerator:
    def __init__(self, game_constant: dict, generator_data: dict, affinity_data: dict, tag_definitions: dict, talent_archetypes: list):
        self.game_constant = game_constant
        self.genders_data = generator_data.get('genders', [])
        self.alias_data = generator_data.get('aliases', {})
        self.ethnicity_data = generator_data.get('ethnicities', [])
        self.boob_cup_data = generator_data.get('boob_cups', []) 
        self.affinity_data = affinity_data
        self.tag_definitions = tag_definitions
        self.talent_archetypes = talent_archetypes
            
        # A common ethnicity to fall back on if a specific one has no names
        self.fallback_ethnicity = "White"
        # Absolute fallback names if the data is missing
        self.default_names = {
            "Male": {"first": ["John"], "last": ["Doe"], "single": ["Rocco"]},
            "Female": {"first": ["Jane"], "last": ["Doe"], "single": ["Angel"]}
        }

    def _weighted_choice(self, options: List[Dict[str, Any]]) -> str:
        if not options:
            return "N/A"
        
        choices = [item['name'] for item in options]
        weights = [item['weight'] for item in options]
        
        return random.choices(choices, weights=weights, k=1)[0]

    def _generate_age(self) -> int:
        ages = list(range(18, 61))
        # Younger ages are more likely
        weights = np.linspace(1.0, 0.1, len(ages))
        weights /= weights.sum()
        return int(np.random.choice(ages, p=weights))

    def _generate_skill(self) -> int:
        """Generates a random skill value, weighted towards the middle."""
        return random.triangular(10, 100, 65)

    def _generate_attribute(self, archetype_mods: Optional[Dict] = None) -> int:
        if archetype_mods:
            return random.randint(archetype_mods['min'], archetype_mods['max'])
        return int(random.triangular(1, 10, 5))

    def _generate_gender(self) -> str:
        """Generates a gender based on weighted choices from data."""
        return self._weighted_choice(self.genders_data)

    def _get_name_list(self, ethnicity: str, gender: str, part: str) -> List[str]:
        """
        Safely retrieves a list of names, with fallbacks for missing data.
        1. Try specific ethnicity.
        2. Try fallback ethnicity (e.g., 'White').
        3. Use hardcoded defaults.
        """
        try:
            # 1. Try specific ethnicity
            names = self.alias_data[ethnicity][gender][part]
            if names:
                return names
        except KeyError:
            pass # Continue to fallback

        try:
            # 2. Try fallback ethnicity
            names = self.alias_data[self.fallback_ethnicity][gender][part]
            if names:
                return names
        except KeyError:
            pass # Continue to default

        # 3. Use hardcoded defaults
        return self.default_names[gender][part]


    def _generate_alias(self, gender: str, ethnicity: str) -> str:
        """
        Generates a gender and ethnicity-appropriate alias.
        Can be a single name or a first/last name combo.
        """
        # 15% chance to generate a single-name alias
        if random.random() < 0.15:
            name_list = self._get_name_list(ethnicity, gender, 'single')
            return random.choice(name_list)
        
        # Otherwise, generate a two-part name
        first_name_list = self._get_name_list(ethnicity, gender, 'first')
        
        # Last names are often more universal. We can pool them for more variety.
        # For simplicity here, we'll just use the fallback ethnicity's last names.
        last_name_list = self._get_name_list(self.fallback_ethnicity, gender, 'last')
        if not last_name_list: # Edge case if even fallback has no last names
            last_name_list = self.default_names[gender]['last']

        first_name = random.choice(first_name_list)
        last_name = random.choice(last_name_list)

        return f"{first_name} {last_name}"

    def _generate_dick_size(self) -> int:
        # ... (This method is unchanged)
        """Generates a dick size in inches, weighted towards 7-10."""
        # Triangular distribution: min, max, mode
        return int(round(random.triangular(2, 15, 8)))

    def _generate_orientation_score(self) -> int:
        """Generates an orientation score from -100 (straight) to 100 (gay/lesbian)."""
        # A triangular distribution makes the extremes less common than values in the middle.
        return int(round(random.triangular(-100, 100, 0)))

    def _generate_disposition_score(self) -> int:
        """Generates a disposition score from -100 (sub) to 100 (dom)."""
        return int(round(random.triangular(-100, 100, 0)))

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
            orientation_multiplier = 1.0
            if tag_orientation and tag_orientation in orientation_targets:
                target_score = orientation_targets[tag_orientation]
                distance = abs(orientation_score - target_score)
                orientation_multiplier = np.interp(distance, [0, 150, 200], [1.0, 0.4, 0.05])

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
        reqs = {"requires": [], "refuses": []}

        # High professionalism may require stricter policies
        if professionalism >= 8 and random.random() < 0.25:
            reqs["requires"].append("policy_std_test_required")
        if professionalism >= 6 and random.random() < 0.15:
            reqs["requires"].append("policy_no_drugs_allowed")
        
        # Low professionalism may refuse certain safety/professional policies
        if professionalism <= 3 and random.random() < 0.20:
            reqs["refuses"].append("policy_condoms_mandatory")
        if professionalism <= 4 and random.random() < 0.10:
            reqs["refuses"].append("policy_std_test_required")

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
        ethnicity = self._weighted_choice(self.ethnicity_data)
        gender = self._generate_gender()
        alias = self._generate_alias(gender, ethnicity)
        
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
        # Add a small variance for personality
        max_scene_partners = max(1, max_scene_partners + random.randint(-2, 2))
        concurrency_limits = archetype_data.get("concurrency_limits", {}).copy()

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
        boob_cup: Optional[str] = None
        dick_size: Optional[int] = None
        
        if gender == "Female":
            boob_cup = self._weighted_choice(self.boob_cup_data)
            if boob_cup and boob_cup != "N/A":
                tag_affinities.update(self._calculate_boob_affinities(boob_cup))
        else: # Male
            dick_size = self._generate_dick_size()
            tag_affinities.update(self._calculate_dick_size_affinities(dick_size))

        tag_affinities.update(self._calculate_age_affinities(age, gender))

        # Common affinities
        if ethnicity and ethnicity != "N/A":
            tag_affinities[ethnicity] = 100
            
        return Talent(
            id=talent_id,
            alias=alias,
            age=age,
            ethnicity=ethnicity,
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
            boob_cup=boob_cup,
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