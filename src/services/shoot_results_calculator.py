import logging
from collections import defaultdict
from typing import List

from data.game_state import Scene, Talent
from data.data_manager import DataManager
from services.talent_service import TalentService
from services.service_config import SceneCalculationConfig
from services.role_performance_service import RolePerformanceService
from services.calculation_models import TalentShootOutcome, FatigueResult

logger = logging.getLogger(__name__)

class ShootResultsCalculator:
    """
    Calculates outcomes for talents involved in a shoot, including stamina,
    fatigue, skill gains, and experience gains.
    """
    def __init__(self, data_manager: DataManager, config: SceneCalculationConfig,
                 role_perf_service: RolePerformanceService, talent_service: 'TalentService'):
        self.data_manager = data_manager
        self.config = config
        self.role_performance_service = role_perf_service
        self.talent_service = talent_service # Used for pure gain calculations

    def calculate_talent_outcomes(
        self, scene: Scene, talents: List[Talent], current_week: int, current_year: int
    ) -> List[TalentShootOutcome]:
        """
        Calculates all per-talent effects from shooting a scene.

        Args:
            scene: The Scene dataclass.
            talents: A list of participating Talent dataclasses.
            current_week: The current game week.
            current_year: The current game year.

        Returns:
            A list of TalentShootOutcome objects, one for each talent.
        """
        talent_stamina_cost = self._calculate_stamina_costs(scene)
        
        # Map talent IDs to their virtual performer to get disposition
        vp_id_to_talent_id = {int(k): v for k, v in scene.final_cast.items()}
        talent_id_to_vp = {v: k for k, v in vp_id_to_talent_id.items()}
        vp_map = {vp.id: vp for vp in scene.virtual_performers}
        
        outcomes = []
        for talent in talents:
            stamina_cost = talent_stamina_cost.get(talent.id, 0.0)
            fatigue_result = self._calculate_fatigue(talent, stamina_cost, current_week, current_year)
            
            p_gain, a_gain, s_gain = self.talent_service.calculate_skill_gain(talent, scene.total_runtime_minutes)
            
            dom_gain, sub_gain = 0.0, 0.0
            vp_id = talent_id_to_vp.get(talent.id)
            if vp_id and (vp := vp_map.get(vp_id)):
                dom_gain, sub_gain = self.talent_service.calculate_ds_skill_gain(talent, scene, vp.disposition)
                
            exp_gain = self.talent_service.calculate_experience_gain(talent, scene.total_runtime_minutes)
            
            skill_gains = {
                'performance': p_gain, 'acting': a_gain, 'stamina': s_gain,
                'dom_skill': dom_gain, 'sub_skill': sub_gain
            }

            outcomes.append(TalentShootOutcome(
                talent_id=talent.id,
                stamina_cost=stamina_cost,
                fatigue_result=fatigue_result,
                skill_gains=skill_gains,
                experience_gain=exp_gain
            ))
        return outcomes

    def _calculate_stamina_costs(self, scene: Scene) -> defaultdict[int, float]:
        """Calculates the total stamina cost for each talent in the scene."""
        talent_stamina_cost = defaultdict(float)
        action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)

        for segment in action_segments_for_calc:
            segment_runtime = scene.total_runtime_minutes * (segment.runtime_percentage / 100.0)
            slots = scene._get_slots_for_segment(segment, self.data_manager.tag_definitions)
            for assignment in segment.slot_assignments:
                talent_id = scene.final_cast.get(str(assignment.virtual_performer_id))
                if not talent_id: continue
                try:
                    _, role, _ = assignment.slot_id.rsplit('_', 2)
                except ValueError:
                    continue
                slot_def = next((s for s in slots if s['role'] == role), None)
                if not slot_def: continue

                final_mod = self.role_performance_service.get_final_modifier(
                    'stamina_modifier', slot_def, segment, role
                )
                cost = segment_runtime * final_mod
                talent_stamina_cost[talent_id] += cost
        return talent_stamina_cost

    def _calculate_fatigue(self, talent: Talent, stamina_cost: float, current_week: int, current_year: int) -> FatigueResult | None:
        """Calculates fatigue gain if stamina pool is overdrawn."""
        max_stamina = talent.stamina * self.config.stamina_to_pool_multiplier
        if stamina_cost <= max_stamina:
            return None

        overdraw_ratio = (stamina_cost - max_stamina) / max_stamina
        fatigue_gain = min(100, int(overdraw_ratio * 100))
        new_fatigue = min(100, talent.fatigue + fatigue_gain)
        
        duration_weeks = self.config.base_fatigue_weeks
        end_week, end_year = current_week + duration_weeks, current_year
        if end_week > 52:
            end_week -= 52
            end_year += 1
            
        return FatigueResult(
            new_fatigue_level=new_fatigue,
            fatigue_end_week=end_week,
            fatigue_end_year=end_year
        )