from typing import Dict, Tuple
from services.models.configs import ProductionConfig

class BlocSimulationCalculator:
    """
    Calculates changes to the Shooting Bloc's simulation state (Momentum, Stress)
    based on the outcome of a scene shoot and logistical factors.
    """
    def __init__(self, data_manager, config: ProductionConfig):
        self.data_manager = data_manager
        self.config = config

    def calculate_simulation_deltas(self, bloc_context: Dict) -> Tuple[float, float]:
        """
        Returns (momentum_delta, stress_delta).
        bloc_context requires: picture_set_settings, location_def, current_momentum.
        """
        # 1. Momentum Change
        # Driven by: Success of previous scene (not passed yet, assumed neutral for now),
        # and interruptions like Picture Sets.
        momentum_delta = 0.0
        
        pic_settings = bloc_context.get('picture_set_settings', {})
        pic_type_id = pic_settings.get('type_id', 'video_grabs')
        pic_type_def = self.data_manager.picture_set_types.get(pic_type_id, {})
        
        momentum_delta += pic_type_def.get('momentum_impact', 0.0)
        
        # 2. Stress Accumulation (Set-wide)
        # Driven by: Location difficulty, Picture Set interruptions, Current Momentum.
        stress_delta = self.config.bloc_base_stress
        stress_delta += pic_type_def.get('stress_impact', 0.0)
        
        location_def = bloc_context.get('location_def', {})
        loc_mods = location_def.get('simulation_modifiers', {})
        stress_delta += loc_mods.get('base_stress', 0)
        
        # Apply Momentum Bonus/Penalty to Stress
        # High momentum (flow state) reduces stress accumulation.
        # Low momentum (grinding) increases it.
        current_momentum = bloc_context.get('current_momentum', self.config.bloc_base_momentum)
        if current_momentum > self.config.momentum_bonus_threshold:
            stress_delta *= self.config.momentum_bonus_multiplier
        elif current_momentum < self.config.momentum_penalty_threshold:
            stress_delta *= self.config.momentum_penalty_multiplier 

        return momentum_delta, stress_delta