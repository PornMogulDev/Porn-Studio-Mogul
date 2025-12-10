from typing import Tuple

from data.game_state import ShootingBloc
from services.models.configs import ProductionConfig
from services.models.results import SceneQualityResult

class BlocSimulationCalculator:
    """
    Calculates the initial shooting conditions for a scene based on the parent
    bloc's state, and then calculates the change in the bloc's state (Momentum, Stress)
    based on the scene's outcome.
    """
    def __init__(self, data_manager, config: ProductionConfig):
        self.data_manager = data_manager
        self.config = config

    def calculate_initial_modifiers(self, bloc: ShootingBloc) -> Tuple[float, float]:
        """
        Calculates the starting conditions for a scene shoot.

        - Set Momentum is the bloc's momentum carrying over into the scene.
        - Set Stress Modifier is a multiplier derived from the bloc's current stress.

        Returns:
            A tuple of (set_momentum, set_stress_modifier).
        """
        # Set momentum is simply the current momentum of the bloc.
        set_momentum = bloc.current_momentum
        
        # Map current stress (0-100+) to a modifier (e.g., 1.0 -> 0.8)
        # Higher stress makes quality targets harder to hit.
        stress_scaled = bloc.current_stress / 100.0
        # Example: At 100 stress, modifier is 1.0 - (1.0 * 0.2) = 0.8
        set_stress_modifier = 1.0 - (stress_scaled * self.config.bloc_stress_impact_factor)
        
        return set_momentum, max(0.0, set_stress_modifier)

    def calculate_post_shoot_deltas(self, bloc: ShootingBloc) -> Tuple[float, float]:
        """
        Calculates the change in momentum and stress for the bloc after a shoot.

        - Momentum changes based on scene quality and logistical interruptions.
        - Stress accumulates based on location, logistics quality, and current momentum.

        Returns:
            A tuple of (momentum_delta, stress_delta).
        """
        # 1. Momentum Change
        momentum_delta = 0.0
        
        # TODO: Add momentum change from scene quality once SceneQualityResult.overall_quality is available.
        
        # Apply momentum impact from picture set interruptions
        pic_settings = bloc.picture_set_settings
        pic_type_id = pic_settings.get('type_id', 'video_grabs')
        pic_type_def = self.data_manager.picture_set_types.get(pic_type_id, {})
        momentum_delta += pic_type_def.get('momentum_impact', 0.0)
        
        # 2. Stress Accumulation (Set-wide)
        stress_delta = self._calculate_stress_gain(bloc)

        return momentum_delta, stress_delta

    def _calculate_stress_gain(self, bloc: ShootingBloc) -> float:
        """Helper to calculate the stress gained during the scene."""
        # Base stress gained per scene
        stress_delta = self.config.bloc_base_stress
        
        # Add stress from picture sets
        pic_settings = bloc.picture_set_settings
        pic_type_id = pic_settings.get('type_id', 'video_grabs')
        pic_type_def = self.data_manager.picture_set_types.get(pic_type_id, {})
        stress_delta += pic_type_def.get('stress_impact', 0.0)
        
        # Add stress from location, modified by logistics quality
        location_def = self.data_manager.production_locations.get(bloc.set_location_id, {})
        if location_def:
            loc_mods = location_def.get('simulation_modifiers', {})
            base_loc_stress = loc_mods.get('base_stress', 0)
            
            # Get rolled quality of logistics from the bloc's cache
            loc_quality = bloc.production_cache.get('location_logistics', 50)
            
            # Quality modifier: 50 quality = 1.0x, 100 quality = 0.5x, 0 quality = 1.5x
            quality_mod = 1.5 - (loc_quality / 100.0)
            stress_delta += (base_loc_stress * quality_mod)
        
        # Apply momentum bonus/penalty to stress gain
        # High momentum (flow state) reduces stress accumulation.
        current_momentum = bloc.current_momentum
        if current_momentum > self.config.momentum_bonus_threshold:
            stress_delta *= self.config.momentum_bonus_multiplier
        elif current_momentum < self.config.momentum_penalty_threshold:
            stress_delta *= self.config.momentum_penalty_multiplier

        return stress_delta