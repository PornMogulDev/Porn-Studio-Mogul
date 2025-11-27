import logging
from collections import defaultdict
from typing import List, Tuple, Union, Dict

from data.game_state import Scene, Talent
from data.data_manager import DataManager
from database.db_models import TalentDB
from services.models.configs import SceneCalculationConfig
from services.calculation.role_performance_calculator import RolePerformanceCalculator
from services.calculation.stress_calculator import StressCalculator
from services.models.results import TalentShootOutcome, FatigueResult

logger = logging.getLogger(__name__)

class ShootResultsCalculator:
    """
    Calculates outcomes for talents involved in a shoot, including stamina,
    fatigue, skill gains, experience gains, stress, and burnout.
    """
    def __init__(self, data_manager: DataManager, config: SceneCalculationConfig,
                 role_perf_calculator: RolePerformanceCalculator, stress_calculator: StressCalculator):
        self.data_manager = data_manager
        self.config = config
        self.role_performance_calculator = role_perf_calculator
        self.stress_calculator = stress_calculator

    def calculate_talent_outcomes(
        self, scene: Scene, talents: List[Talent], 
        bloc_context: dict
    ) -> List[TalentShootOutcome]:
        """
        Calculates all per-talent effects from shooting a scene.
        bloc_context must contain: location_def, craft_services_efficiency, crew_assignments
        """
        talent_stamina_cost = self._calculate_stamina_costs(scene)
        
        vp_id_to_talent_id = {int(k): v for k, v in scene.final_cast.items()}
        talent_id_to_vp = {v: k for k, v in vp_id_to_talent_id.items()}
        vp_map = {vp.id: vp for vp in scene.virtual_performers}
        
        crew_assignments = bloc_context.get('crew_assignments', {})
        location_def = bloc_context.get('location_def', {})
        cs_efficiency = bloc_context.get('craft_services_efficiency', 1.0)
        hs_score = bloc_context.get('health_safety_score', 50)

        outcomes = []
        for talent in talents:
            stamina_cost = talent_stamina_cost.get(talent.id, 0.0)
            fatigue_result = self._calculate_fatigue(talent, stamina_cost)
            
            p_gain, a_gain, s_gain = self._calculate_skill_gain(talent, scene.total_runtime_minutes)
            
            dom_gain, sub_gain = 0.0, 0.0
            vp_id = talent_id_to_vp.get(talent.id)
            if vp_id and (vp := vp_map.get(vp_id)):
                dom_gain, sub_gain = self._calculate_ds_skill_gain(talent, scene, vp.disposition)
                
            exp_gain = self._calculate_experience_gain(talent, scene.total_runtime_minutes)
            
            # --- Calculate Stress & Burnout ---
            jobs = self._get_jobs_for_talent(talent.id, crew_assignments)
            
            stress_gain = self.stress_calculator.calculate_stress_gain(
                talent=talent,
                jobs=jobs,
                location_def=location_def,
                craft_services_efficiency=cs_efficiency,
                health_safety_score=hs_score,
                events_modifier=0.0 
            )
            
            # Calculate Burnout (Overflow of stress)
            burnout_gain = 0.0
            projected_total_stress = talent.stress + stress_gain
            if projected_total_stress > self.config.max_stress_threshold:
                excess_stress = projected_total_stress - self.config.max_stress_threshold
                burnout_gain = excess_stress * self.config.burnout_conversion_rate

            skill_gains = {
                'performance': p_gain, 'acting': a_gain, 'stamina': s_gain,
                'dom_skill': dom_gain, 'sub_skill': sub_gain
            }

            outcomes.append(TalentShootOutcome(
                talent_id=talent.id,
                stamina_cost=stamina_cost,
                fatigue_result=fatigue_result,
                skill_gains=skill_gains,
                experience_gain=exp_gain,
                stress_gain=stress_gain,
                burnout_gain=burnout_gain
            ))

        return outcomes
    
    def _get_jobs_for_talent(self, talent_id: int, crew_assignments: Dict) -> List[str]:
        """Identifies all roles (Actor + Crew) a talent is performing."""
        jobs = ['actor'] # Implicitly an actor if they are in this list
        
        # Check assignments in the new dict structure: 
        # {'director': {'type': 'character', 'id': 5}, 'camera': {'type': 'generic', ...}}
        for slot_id, assignment in crew_assignments.items():
            if assignment.get('type') == 'character' and assignment.get('id') == talent_id:
                jobs.append(slot_id)
        return jobs
    
    def estimate_fatigue_gain(self, talent: Union[Talent, TalentDB], scene: Scene, vp_id: int) -> int:
        """
        Estimates the fatigue gain for a specific talent in a given scene without
        considering their current fatigue or relying on scene.final_cast.
        This is a "what-if" calculation for a potential role.
        """
        stamina_cost = self._calculate_stamina_cost_for_role(vp_id, scene)
        max_stamina = talent.stamina * self.config.stamina_to_pool_multiplier
        
        if stamina_cost <= max_stamina:
            return 0

        overdraw_ratio = (stamina_cost - max_stamina) / max_stamina
        fatigue_gain = min(100, int(overdraw_ratio * 100))
        return fatigue_gain

    def _calculate_stamina_cost_for_talent(self, talent_id: int, scene: Scene) -> float:
        """Calculates the total stamina cost for a single talent in the scene."""
        vp_id_to_talent_id = {int(k): v for k, v in scene.final_cast.items()}
        talent_id_to_vp_id = {v: k for k, v in vp_id_to_talent_id.items()}
        vp_id = talent_id_to_vp_id.get(talent_id)

        if vp_id:
            return self._calculate_stamina_cost_for_role(vp_id, scene)

        return 0.0

    def _calculate_stamina_cost_for_role(self, vp_id: int, scene: Scene) -> float:
        """Calculates the total stamina cost for a single virtual performer role in a scene."""
        stamina_cost = 0.0
        action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in action_segments_for_calc:
            if not any(a.virtual_performer_id == vp_id for a in segment.slot_assignments):
                continue

            segment_runtime = scene.total_runtime_minutes * (segment.runtime_percentage / 100.0)
            stamina_cost += segment_runtime * self.role_performance_calculator.get_role_stamina_modifier(segment, vp_id, scene, self.data_manager.tag_definitions)
        return stamina_cost

    def _calculate_stamina_costs(self, scene: Scene) -> defaultdict[int, float]:
        """Calculates the total stamina cost for each talent in the scene."""
        talent_stamina_cost = defaultdict(float)
        all_talent_ids = set(scene.final_cast.values())
        for talent_id in all_talent_ids:
            talent_stamina_cost[talent_id] = self._calculate_stamina_cost_for_talent(talent_id, scene)
        return talent_stamina_cost

    def _calculate_fatigue(self, talent: Talent, stamina_cost: float) -> FatigueResult | None:
        """Calculates fatigue gain if stamina pool is overdrawn."""
        max_stamina = talent.stamina * self.config.stamina_to_pool_multiplier
        if stamina_cost <= max_stamina:
            return None

        overdraw_ratio = (stamina_cost - max_stamina) / max_stamina
        fatigue_gain = min(100, int(overdraw_ratio * 100))
        new_fatigue = min(100, talent.fatigue + fatigue_gain)
            
        return FatigueResult(
            new_fatigue_level=new_fatigue,
        )
    
    def _calculate_skill_gain(self, talent: Talent, runtime_minutes: int) -> Tuple[float, float, float]:
        """Calculates potential skill gains for a talent based on scene runtime."""
        base_rate = self.config.skill_gain_base_rate
        curve_steepness = self.config.skill_gain_curve_steepness

        def get_gain(skill_value):
            diminishing_return_factor = 1 - (skill_value / 100) ** curve_steepness
            return (runtime_minutes * base_rate) * diminishing_return_factor

        return get_gain(talent.performance), get_gain(talent.acting), get_gain(talent.stamina)

    def _calculate_ds_skill_gain(self, talent: Talent, scene: Scene, disposition: str) -> Tuple[float, float]:
        """Calculates D/S skill gain based on scene dynamic and talent disposition."""
        if scene.dom_sub_dynamic_level == 0:
            return 0.0, 0.0

        dom_gain, sub_gain = 0.0, 0.0
        runtime = scene.total_runtime_minutes

        base_rate = self.config.ds_skill_gain_base_rate
        disposition_multiplier = self.config.ds_skill_gain_disposition_multiplier
        dynamic_level_multipliers = self.config.ds_skill_gain_dynamic_level_multipliers
        level_multiplier = dynamic_level_multipliers.get(scene.dom_sub_dynamic_level, 1.0)
        base_gain = runtime * base_rate * level_multiplier

        dom_focus, sub_focus = 0.5, 0.5
        if scene.dom_sub_dynamic_level == 1: dom_focus, sub_focus = 0.0, 1.0
        elif scene.dom_sub_dynamic_level == 3: dom_focus, sub_focus = 1.0, 0.0

        if disposition == "Dom":
            dom_focus *= disposition_multiplier
        elif disposition == "Sub":
            sub_focus *= disposition_multiplier

        total_focus = dom_focus + sub_focus # Renormalize
        if total_focus > 0:
            dom_gain = base_gain * (dom_focus / total_focus)
            sub_gain = base_gain * (sub_focus / total_focus)
        
        return dom_gain, sub_gain

    def _calculate_experience_gain(self, talent: Talent, runtime_minutes: int) -> float:
        """Calculates experience gain, with diminishing returns."""
        base_rate = self.config.exp_gain_base_rate
        curve_steepness = self.config.exp_gain_curve_steepness
        diminishing_return_factor = 1 - (talent.experience / 100) ** curve_steepness
        return max(0, (runtime_minutes * base_rate) * diminishing_return_factor)