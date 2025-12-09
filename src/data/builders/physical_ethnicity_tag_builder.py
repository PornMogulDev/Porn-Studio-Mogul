from typing import Dict, List, Any

class PhysicalEthnicityTagBuilder:
    """
    Generates ethnicity-based Physical tags (Individual and Pairs).
    Ensures pair tags are canonical (e.g. BM/WF is always generated, never WF/BM).
    """
    def __init__(self, ethnicity_hierarchy: Dict[str, List[str]], game_config: Dict[str, Any]):
        self.hierarchy = ethnicity_hierarchy
        self.config = game_config
        
        self.custom_names = {
            ("Black", "Female"): "Ebony",
            ("Latin", "Female"): "Latina",
        }
        
        # Predefined short codes. 
        # Can be expanded via DB or Config in the future.
        self.short_codes = {
            "White": "W", "Black": "B", "Asian": "A", 
            "Latin": "L", "Arab": "Ar", "Amerindian": "Am",
            "Male": "M", "Female": "F"
        }

    def _get_short_code(self, ethnicity: str) -> str:
        """
        Returns a short code for the ethnicity. 
        Safe fallback to first 2 letters if unknown.
        """
        if ethnicity in self.short_codes:
            return self.short_codes[ethnicity]
        
        # Fallback: First 2 letters, uppercase
        if ethnicity and len(ethnicity) >= 2:
            return ethnicity[:2].upper()
        return (ethnicity or "??")[:2].upper()

    def generate_all_tags(self) -> List[Dict[str, Any]]:
        tags = []
        tags.extend(self.generate_individual_tags())
        tags.extend(self.generate_pair_tags())
        return tags

    def generate_individual_tags(self) -> List[Dict[str, Any]]:
        tags = []
        
        # Flatten hierarchy to get all ethnicity strings (Primary + Sub-groups)
        all_ethnicities = set(self.hierarchy.keys()) # Primaries
        for subs in self.hierarchy.values():
            all_ethnicities.update(subs)
            
        genders = ["Male", "Female"]
        
        for ethnicity in all_ethnicities:
            for gender in genders:
                tags.append(self._create_individual_tag(ethnicity, gender))
                
        return tags

    def generate_pair_tags(self) -> List[Dict[str, Any]]:
        tags = []
        # Only primary ethnicities here for now
        primaries = sorted(self.hierarchy.keys())
        
        # 1. Straight Pairs (Male + Female) - All permutations of ethnicity
        for eth1 in primaries:
            for eth2 in primaries:
                tags.append(self._create_pair_tag(eth1, "Male", eth2, "Female"))

        # 2. Gay Pairs (Male + Male) - Combinations (ignore order to avoid duplicates)
        for i, eth1 in enumerate(primaries):
            for eth2 in primaries[i:]:
                 tags.append(self._create_pair_tag(eth1, "Male", eth2, "Male"))

        # 3. Lesbian Pairs (Female + Female) - Combinations
        for i, eth1 in enumerate(primaries):
            for eth2 in primaries[i:]:
                 tags.append(self._create_pair_tag(eth1, "Female", eth2, "Female"))
                
        return tags

    def _create_individual_tag(self, ethnicity: str, gender: str) -> Dict[str, Any]:
        # Determine Name (defaults to Ethnicity name, e.g. "White" or "Western European")
        # DataManager will append " ({Gender})" to the key, resulting in "White (Male)".
        name = self.custom_names.get((ethnicity, gender), ethnicity)
        
        # Revenue Weights
        focused_w = self.config.get("ethnic_tag_individual_focused", 10.0)
        auto_w = self.config.get("ethnic_tag_individual_auto", 2.5)
        
        return {
            "name": name,
            "full_name": name, # Placeholder, will be adjusted by DataManager logic if needed
            "type": "Physical",
            "concept": "Individual Ethnic",
            "categories": ["Race"],
            "gender": gender,
            "orientation": gender, # Helper for filtering
            "ethnicity": ethnicity,
            "is_auto_taggable": True,
            # Auto detection rule: strict check on the ethnicity stat
            "auto_detection_rule": {
                "conditions": [
                    { "type": "stat", "key": "ethnicity", "comparison": "eq", "value": ethnicity }
                ]
            },
            "quality_source": {
                "base": "acting",
                "quality_blend": [
                    { "source": "static", "value": 100, "weight": 0.7 },
                    { "source": "base", "weight": 0.3 }
                ]
            },
            "revenue_weights": {
                "focused": focused_w,
                "auto": auto_w
            }
        }

    def _create_pair_tag(self, eth1: str, gender1: str, eth2: str, gender2: str) -> Dict[str, Any]:
        is_same_ethnicity = (eth1 == eth2)
        
        code1 = self._get_short_code(eth1)
        code2 = self._get_short_code(eth2)
        
        g1 = "M" if gender1 == "Male" else "F"
        g2 = "M" if gender2 == "Male" else "F"

        part1 = f"{code1}{g1}"
        part2 = f"{code2}{g2}"
        
        # CANONICAL SORTING:
        # We strictly order by the code string.
        # This ensures that "Black Male + White Female" generates "BM/WF"
        # And "White Female + Black Male" ALSO generates "BM/WF"
        # This prevents duplicate tags in the system.
        if part1 < part2:
            pair_code = f"{part1}/{part2}"
            # Keep track of which descriptive vars belong to which side for the tooltip
            t_eth1, t_gen1 = eth1, gender1
            t_eth2, t_gen2 = eth2, gender2
        else:
            pair_code = f"{part2}/{part1}"
            # Swap vars for tooltip consistency
            t_eth1, t_gen1 = eth2, gender2
            t_eth2, t_gen2 = eth1, gender1

        # Orientation Logic
        if gender1 != gender2:
            orientation = "Straight"
        elif gender1 == "Male":
            orientation = "Gay"
        else:
            orientation = "Lesbian"
        
        if is_same_ethnicity:
            concept = f"Same-Ethnicity Pairs ({orientation})"
            base_name = f"({pair_code})"
        else:
            concept = f"Interracial Pairs ({orientation})"
            base_name = f"Interracial ({pair_code})"

        # Configurable Weights
        focused_w = self.config.get("ethnic_tag_pair_focused", 15.0)
        auto_w = self.config.get("ethnic_tag_pair_auto", 3.0)

        return {
            "name": base_name,
            "full_name": base_name,
            "type": "Physical",
            "concept": concept,
            "orientation": orientation,
            # If they are same ethnicity, it's just Race. If different, it's Interracial.
            "categories": ["Race", "Interracial"] if not is_same_ethnicity else ["Race"],
            "is_auto_taggable": True,
            # Tooltip matches canonical order
            "tooltip": f"{t_eth1} {t_gen1} & {t_eth2} {t_gen2}",
            
            # Validation Rule: Match all profiles
            "validation_rule": {
                "mode": "match_all",
                "profiles": [
                    { "gender": t_gen1, "ethnicity": t_eth1 },
                    { "gender": t_gen2, "ethnicity": t_eth2 }
                ]
            },
             "quality_source": {
                "scope": "matched",
                "base": "acting",
                "quality_blend": [
                    { "source": "static", "value": 100, "weight": 0.7 },
                    { "source": "base", "weight": 0.3 }
                ]
            },
            "revenue_weights": {
                "focused": focused_w,
                "auto": auto_w
            }
        }