from typing import Dict, List, Any

class PhysicalEthnicityTagBuilder:
    """
    Generates ethnicity-based Physical tags (Individual and Pairs) 
    based on the loaded ethnicity hierarchy.
    """
    def __init__(self, ethnicity_hierarchy: Dict[str, List[str]], game_config: Dict[str, Any]):
        self.hierarchy = ethnicity_hierarchy
        self.config = game_config
        
        # Mapping (Ethnicity, Gender) -> Custom Tag Name
        # If an entry exists, it replaces the default "{Ethnicity}" name.
        self.custom_names = {
            ("Black", "Female"): "Ebony",
            ("Latin", "Female"): "Latina",
        }
        
        # Short codes for generating compact pair names like (BM/WF)
        self.short_codes = {
            "White": "W", "Black": "B", "Asian": "A", 
            "Latin": "L", "Arab": "Ar", "Amerindian": "Am",
            "Male": "M", "Female": "F"
        }

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
        
        code1 = self.short_codes.get(eth1, eth1[0])
        code2 = self.short_codes.get(eth2, eth2[0])
        
        g1 = "M" if gender1 == "Male" else "F"
        g2 = "M" if gender2 == "Male" else "F"
        
        # e.g. BM/WF or BM/WM
        pair_code = f"{code1}{g1}/{code2}{g2}"

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

        # Revenue Weights
        focused_w = self.config.get("ethnic_tag_pair_focused", 15.0)
        auto_w = self.config.get("ethnic_tag_pair_auto", 3.0)

        return {
            "name": base_name,
            "full_name": base_name,
            "type": "Physical",
            "concept": concept,
            "orientation": orientation,
            "categories": ["Race", "Interracial"] if not is_same_ethnicity else ["Race"],
            "is_auto_taggable": True,
            "tooltip": f"{eth1} {gender1} & {eth2} {gender2}",
            # Compositional validation rule
            "validation_rule": {
                "mode": "match_all",
                "profiles": [
                    { "gender": gender1, "ethnicity": eth1 },
                    { "gender": gender2, "ethnicity": eth2 }
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