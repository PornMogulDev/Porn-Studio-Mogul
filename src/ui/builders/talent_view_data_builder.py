from typing import Dict
from data.game_state import Talent
from core.interfaces import IGameController
from utils.formatters import get_fuzzed_skill_range, format_skill_range, format_fatigue, format_orientation, format_physical_attribute

class TalentViewDataBuilder:
    """
    Helper class to construct dictionary payloads for Talent UI widgets
    (specifically DetailsWidget) to ensure consistency between the
    Main Profile View and the Smart Hover Tooltip.
    """
    @staticmethod
    def build_basic_info(talent: Talent, controller: IGameController) -> Dict:
        ethnicity_str = talent.ethnicity
        if talent.primary_ethnicity and talent.ethnicity != talent.primary_ethnicity:
            ethnicity_str = f"{talent.ethnicity}"

        traits_display = []
        for t_id in talent.traits:
            if t_def := controller.data_manager.get_trait_definition(t_id):
                traits_display.append(t_def)

        return {
            'age': talent.age,
            'gender': talent.gender,
            'orientation': talent.orientation_score, # DetailsWidget expects score/enum, internal formatter handles it
            'ethnicity': ethnicity_str,
            'nationality': talent.nationality,
            'base_location': talent.base_location,
            'current_location': talent.current_location,
            'popularity': round(sum(talent.popularity.values())),
            'fatigue': format_fatigue(talent.fatigue),
            'traits_data': traits_display
        }

    @staticmethod
    def build_skills_info(talent: Talent) -> Dict:
        return {
            'performance': format_skill_range(get_fuzzed_skill_range(talent.performance, talent.experience, talent.id)),
            'acting': format_skill_range(get_fuzzed_skill_range(talent.acting, talent.experience, talent.id)),
            'stamina': format_skill_range(get_fuzzed_skill_range(talent.stamina, talent.experience, talent.id)),
            'dom_skill': format_skill_range(get_fuzzed_skill_range(talent.dom_skill, talent.experience, talent.id)),
            'sub_skill': format_skill_range(get_fuzzed_skill_range(talent.sub_skill, talent.experience, talent.id)),
            'experience': int(talent.experience)
        }