import random
from typing import Dict, List, Any, Optional
import numpy as np
from collections import defaultdict

from game_state import Talent

class TalentGenerator:
    def __init__(self, generator_data: dict, affinity_data: dict, tag_definitions: dict, talent_archetypes: dict):
        self.genders_data = generator_data.get('genders', [])
        self.alias_data = generator_data.get('aliases', {})
        self.ethnicity_data = generator_data.get('ethnicities', [])
        self.boob_cup_data = generator_data.get('boob_cups', []) 
        self.affinity_data = affinity_data
        self.tag_definitions = tag_definitions
        self.talent_archetypes = talent_archetypes # Added
            
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

    def _assign_archetype(self) -> dict:
        """Performs a weighted random choice to assign a talent archetype."""
        choices = list(self.talent_archetypes.values())
        weights = [item.get('weight', 1) for item in choices]
        return random.choices(choices, weights=weights, k=1)[0]

    def _generate_preferences_and_limits(self, gender: str, orientation_score: int, archetype_data: dict) -> tuple[Dict[str, Dict[str, float]], List[str]]:
        """
        Generates role-based tag preferences and hard limits based on an archetype and orientation.
        """
        prefs: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Get baseline hard limits from the archetype. We will add to this list later.
        limits = archetype_data.get("hard_limits", []).copy()
        base_prefs = archetype_data.get("preferences", {})
        
        # Iterate through all tags to build preferences
        for full_name, tag_def in self.tag_definitions.items():
            if tag_def.get('type') != 'Action': continue

            # Step 1: GENDER COMPATIBILITY CHECK
            # If the talent's gender cannot perform any role in this tag, skip it completely.
            slots = tag_def.get('slots', [])
            if not any(slot.get('gender') == gender or slot.get('gender') == "Any" for slot in slots):
                continue

            # Step 2: ORIENTATION COMPATIBILITY
            orientation_targets = {"Straight": -100, "Gay": 100, "Lesbian": 100}
            tag_orientation = tag_def.get('orientation')
            
            orientation_multiplier = 1.0
            if tag_orientation and tag_orientation in orientation_targets:
                target_score = orientation_targets[tag_orientation]
                distance = abs(orientation_score - target_score)
                # An orientation mismatch results in a severe penalty.
                orientation_multiplier = np.interp(distance, [0, 150, 200], [1.0, 0.4, 0.05])

            # Step 3: ARCHETYPE PREFERENCE
            # Find the base preference score from the archetype data.
            concept = tag_def.get('concept')
            base_name = tag_def.get('name')
            archetype_score = 1.0
            if full_name in base_prefs:
                archetype_score = base_prefs[full_name]
            elif concept and concept in base_prefs:
                archetype_score = base_prefs[concept]
            elif base_name and base_name in base_prefs:
                archetype_score = base_prefs[base_name]

            # Step 4: CALCULATE FINAL SCORE
            # Combine the archetype preference with the orientation penalty.
            final_score = round(archetype_score * orientation_multiplier, 2)

            # Only store preferences that are not the default (1.0) or are not effectively a hard limit.
            # This reduces clutter. We handle hard limits in the finalization step.
            if final_score != 1.0:
                roles = {slot['role'] for slot in tag_def.get('slots', [])}
                for role in roles:
                    prefs[full_name][role] = final_score
        
        # Step 5: FINALIZE HARD LIMITS AND CLEAN UP PREFERENCES
        # This is a critical step to prevent contradictions.
        hard_limit_threshold = 0.1
        tags_to_make_limits = set()

        for tag_name, roles_prefs in prefs.items():
            # If any role for a tag is below the threshold, the entire tag becomes a hard limit.
            if any(score < hard_limit_threshold for score in roles_prefs.values()):
                tags_to_make_limits.add(tag_name)

        for tag_name in tags_to_make_limits:
            if tag_name not in limits:
                limits.append(tag_name)
            # CRUCIAL: Remove the tag from the preferences dictionary to avoid contradiction.
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
        affinities = {
            "AA": {"Small Boobs": 100, "Medium Boobs": 0, "Big Boobs": 0, "Huge Boobs": 0 },
            "A": {"Small Boobs": 100, "Medium Boobs": 0, "Big Boobs": 0, "Huge Boobs": 0 },
            "B": {"Small Boobs": 80, "Medium Boobs": 20, "Big Boobs": 0, "Huge Boobs": 0 },
            "C": {"Small Boobs": 10, "Medium Boobs": 70, "Big Boobs": 20, "Huge Boobs": 0 },
            "D": {"Small Boobs": 0, "Medium Boobs": 20, "Big Boobs": 80, "Huge Boobs": 0 },
            "E": {"Small Boobs": 0, "Medium Boobs": 10, "Big Boobs": 90, "Huge Boobs": 0 },
            "F": {"Small Boobs": 0, "Medium Boobs": 5, "Big Boobs": 90, "Huge Boobs": 5 },
            "G": {"Small Boobs": 0, "Medium Boobs": 0, "Big Boobs": 80, "Huge Boobs": 20 },
            "H": {"Small Boobs": 0, "Medium Boobs": 0, "Big Boobs": 50, "Huge Boobs": 50 },
            "I": {"Small Boobs": 0, "Medium Boobs": 0, "Big Boobs": 20, "Huge Boobs": 80 },
            "J": {"Small Boobs": 0, "Medium Boobs": 0, "Big Boobs": 0, "Huge Boobs": 100 },
            "K": {"Small Boobs": 0, "Medium Boobs": 0, "Big Boobs": 0, "Huge Boobs": 100 },
            "L": {"Small Boobs": 0, "Medium Boobs": 0, "Big Boobs": 0, "Huge Boobs": 100 }
        }
        return affinities.get(cup, {"Small Boobs": 33, "Medium Boobs": 34, "Big Boobs": 33})

    def _calculate_dick_size_affinities(self, size: int) -> Dict[str, int]:
        """Calculates dick size-based tag affinities."""
        size_points =   [2, 5,   6,   8,   9,  12]
        small_values =  [100, 100,  50,   0,   0,   0]
        medium_values = [0,   0,  50, 100,  50,   0]
        big_values =    [0,   0,   0,   0,  50, 100]

        raw_small = np.interp(size, size_points, small_values)
        raw_medium = np.interp(size, size_points, medium_values)
        raw_big = np.interp(size, size_points, big_values)

        total = raw_small + raw_medium + raw_big
        if total == 0: return {"Small Dick": 0, "Medium Dick": 0, "Big Dick": 0}

        return {
            "Small Dick": int(round((raw_small / total) * 100)),
            "Medium Dick": int(round((raw_medium / total) * 100)),
            "Big Dick": int(round((raw_big / total) * 100))
        }

    def generate_talent(self, talent_id: int) -> Talent:
        """Generates a single, fully-formed Talent object."""
        # Core attributes
        age = self._generate_age()
        ethnicity = self._weighted_choice(self.ethnicity_data)
        gender = self._generate_gender()
        alias = self._generate_alias(gender, ethnicity)
        
        # Archetype and Orientation
        archetype_data = self._assign_archetype()
        orientation_score = self._generate_orientation_score()
        
        # Generate preferences based on archetype and orientation
        tag_preferences, hard_limits = self._generate_preferences_and_limits(gender, orientation_score, archetype_data)

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
            boob_cup=boob_cup,
            dick_size=dick_size,
            tag_affinities=tag_affinities,
            tag_preferences=tag_preferences,
            hard_limits=hard_limits,
            policy_requirements=policy_requirements
        )

    def generate_multiple_talents(self, count: int, start_id: int) -> List[Talent]:
        """Generates a list of new Talent objects."""
        return [self.generate_talent(start_id + i) for i in range(count)]