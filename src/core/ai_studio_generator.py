import random
import logging
from typing import List, Dict, Optional, Any
from data.game_state import AIStudio
from data.data_manager import DataManager

logger = logging.getLogger(__name__)

class AIStudioGenerator:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        self.archetypes = self.data_manager.ai_studio_archetypes
        self.tag_definitions = self.data_manager.tag_definitions

    def generate_studios(self, count: int, start_id: int) -> List[AIStudio]:
        studios = []
        if not self.archetypes:
            logger.warning("No AI Studio archetypes found. Skipping generation.")
            return studios

        # Weighted choice of archetypes
        archetype_choices = self.archetypes
        weights = [a.get('weight', 10) for a in archetype_choices]

        for i in range(count):
            archetype = random.choices(archetype_choices, weights=weights, k=1)[0]
            
            # Resolve Location
            locations = archetype.get('locations', {})
            location = "South West (US)" # Fallback
            if locations:
                loc_names = list(locations.keys())
                loc_weights = list(locations.values())
                location = random.choices(loc_names, weights=loc_weights, k=1)[0]
            
            # Resolve Name and ID
            # Using start_id + i ensures unique IDs for this batch
            studio_id = start_id + i
            base_name = archetype.get('name', "AI Studio")
            full_name = f"{base_name} {studio_id}" # Append ID to ensure distinct names

            # Resolve Focus Groups
            focus_groups = archetype.get('focus_groups', {})
            preferred_markets = list(focus_groups.keys())
            
            # Scenes per month target
            spm_range = archetype.get('scenes_per_month', {'min': 3, 'max': 5})
            spm = random.randint(spm_range.get('min', 3), spm_range.get('max', 5))

            studio = AIStudio(
                id=studio_id,
                name=full_name,
                location=location,
                money=100000,
                active=True,
                scenes_per_month_target=spm,
                preferred_market_groups=preferred_markets,
                archetype_id=archetype.get('id')
            )
            studios.append(studio)
            
        return studios

    def generate_scene_parameters(self, archetype_id: str, current_week: int) -> dict:
        """
        Generates parameters for a new scene based on the studio's archetype.
        """
        archetype = next((a for a in self.archetypes if a['id'] == archetype_id), None)
        if not archetype:
            return {}
            
        params = {}
        
        # Orientation
        params['orientation'] = archetype.get('orientation', 'Straight')
        
        # Dynamic Level
        dyn_weights = archetype.get('dom_sub_dynamic', {'0': 1.0})
        levels = list(dyn_weights.keys())
        weights = list(dyn_weights.values())
        params['dom_sub_level'] = int(random.choices(levels, weights=weights, k=1)[0])
        
        # Target Market
        focus_groups = archetype.get('focus_groups', {})
        if focus_groups:
            markets = list(focus_groups.keys())
            m_weights = list(focus_groups.values())
            params['target_market'] = random.choices(markets, weights=m_weights, k=1)[0]
        else:
            params['target_market'] = "General"

        # Tags Generation
        selected_tags = {}
        tag_config = archetype.get('tag_weights', {})
        
        # Process each category (Action, Physical, Thematic)
        # We pick roughly 2 Action, 2 Physical, 1 Thematic tag.
        categories = [
            ('action_tags', 'Action', 2),
            ('physical_tags', 'Physical', 2),
            ('thematic_tags', 'Thematic', 1)
        ]

        for cat_key, tag_type, pick_count in categories:
            cat_weights = tag_config.get(cat_key, {})
            if not cat_weights: continue
            
            pool = self._build_tag_pool(cat_weights, params['orientation'], tag_type)
            
            if pool:
                tags = list(pool.keys())
                weights = list(pool.values())
                
                for _ in range(pick_count):
                    if not tags: break
                    chosen = random.choices(tags, weights=weights, k=1)[0]
                    
                    # Generate Quality
                    q_range = archetype.get('tag_quality_range', {'min': 50.0, 'max': 85.0})
                    quality = random.uniform(q_range['min'], q_range['max'])
                    
                    selected_tags[chosen] = quality
                    
                    # Remove chosen to avoid duplicates
                    idx = tags.index(chosen)
                    tags.pop(idx)
                    weights.pop(idx)
                    
        params['tags'] = selected_tags
        return params

    def _build_tag_pool(self, weights_config: dict, orientation: str, tag_type: str) -> Dict[str, float]:
        pool = {}
        
        for tag_name, tag_def in self.tag_definitions.items():
            if tag_def.get('type') != tag_type: continue
            
            # Filter by Orientation (if tag is specific)
            t_orient = tag_def.get('orientation')
            if t_orient and t_orient not in ["Universal", "Any"] and t_orient != orientation:
                continue
                
            # Determine Priority: Specific Name > Concept
            # We check if the tag name or its concept exists in the weights config
            name_weight = weights_config.get(tag_def.get('name', ''))
            concept_weight = weights_config.get(tag_def.get('concept', ''))
            
            if name_weight is not None:
                pool[tag_name] = name_weight # Specific tag weight takes precedence
            elif concept_weight is not None:
                pool[tag_name] = concept_weight # Fallback to concept weight
                
        return pool