import unittest
from unittest.mock import Mock, MagicMock

from services.calculation.talent_availability_checker import TalentAvailabilityChecker, AvailabilityResult
from services.models.configs import HiringConfig

class TestTalentAvailabilityChecker(unittest.TestCase):
    
    def setUp(self):
        """Set up the test environment before each test."""
        self.data_manager = Mock()
        self.config = HiringConfig(
            location_to_location_cost=0,
            location_to_location_fatigue=0,
            base_talent_demand=0,
            demand_perf_divisor=1,
            ambition_demand_divisor=1,
            popularity_demand_scalar=0,
            minimum_talent_demand=0,
            rush_fee_multiplier=1.0,
            bulk_discount_tiers={},
            hazard_pay_modifiers={},
            # Fields that are actually used in the checker
            concurrency_default_limit=99,
            refusal_threshold=0.3,
            orientation_refusal_threshold=0.1,
            pickiness_popularity_scalar=0.01,
            pickiness_ambition_scalar=0.1,
            median_ambition=50,
            max_scenes_per_week_base=2,
            max_scenes_per_week_ambition_modifier=0.02,
            fatigue_refusal_threshold=90,
            burnout_penalty_scenes=1,
            total_budget_refusal_thresholds={"10": 10000, "20": 50000},
            department_budget_refusal_thresholds={
                "wardrobe": {"15": 5000},
                "makeup": {"25": 10000}
            }
        )

        self.data_manager.tag_definitions = {
            "Anal Sex": {"name": "Anal Sex", "concept": "Anal", "orientation": "Straight"},
            "Lesbian Sex": {"name": "Lesbian Sex", "concept": "Vaginal", "orientation": "Lesbian"},
            "Secret Tag": {"name": "Secret Tag"},
        }
        self.data_manager.studio_policies_data = {
            "policy_1": {"id": "policy_1", "name": "Required Policy"},
            "policy_2": {"id": "policy_2", "name": "Refused Policy"}
        }
        self.data_manager.production_departments = {
            "wardrobe": {"id": "wardrobe", "name": "Wardrobe"},
            "makeup": {"id": "makeup", "name": "Makeup"}
        }

        self.checker = TalentAvailabilityChecker(self.data_manager, self.config)

        # Basic mocks to be customized in each test
        self.talent = MagicMock()
        self.talent.fatigue = 0
        self.talent.ambition = 50
        self.talent.max_scene_partners = 10
        self.talent.hard_limits = set()
        self.talent.concurrency_limits = {}
        self.talent.tag_preferences = {}
        self.talent.policy_requirements = {}
        self.talent.popularity_scores = []
        self.talent.contract = None

        self.scene = MagicMock()
        self.scene.virtual_performers = []
        # Make the mock scene's method return what get_vp_role_context would
        self.checker.get_vp_role_context = Mock(return_value=(set(), {}))

        self.bloc_db = MagicMock()
        self.bloc_db.production_cost = 100000
        self.bloc_db.department_budgets = {}

        # Default arguments for the checker
        self.check_args = {
            "talent": self.talent,
            "scene": self.scene,
            "vp_id": 1,
            "bloc_db": self.bloc_db,
            "bookings_before": [],
            "bookings_current": [],
            "bookings_after": [],
            "estimated_fatigue_gain": 0,
            "studio_policies": []
        }

    def test_available_when_all_conditions_met(self):
        """Should return available when no refusal conditions are met."""
        result = self.checker.check(**self.check_args)
        self.assertTrue(result.is_available)
        self.assertIsNone(result.reason)

    def test_refuses_due_to_max_scenes_per_week(self):
        """Should refuse if already booked for the max number of scenes in a week."""
        self.check_args["bookings_current"] = [Mock(), Mock()] # Base max is 2
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertIn("Will not shoot more than 2 scenes", result.reason)

    def test_refuses_due_to_burnout_penalty(self):
        """Should refuse if burnout penalty reduces their weekly scene limit."""
        from dataclasses import replace

        self.talent.ambition = 50 
        self.check_args["bookings_before"] = [Mock()]
        self.check_args["bookings_after"] = [Mock()]
        self.check_args["bookings_current"] = [Mock(), Mock()]
        
        # Base max scenes for ambition 50 is 2.
        # Burnout penalty is 1, so effective_max_scenes is max(1, 2 - 1) = 1.
        # Talent is already booked for 2 scenes, which is >= 1.
        
        # To make this test specific, create a config where burnout is decisive
        test_config = replace(self.config, 
                              max_scenes_per_week_base=3, # Without burnout, they could take 3 scenes
                              burnout_penalty_scenes=1)   # With burnout, they can only take 2
        
        checker = TalentAvailabilityChecker(self.data_manager, test_config)
        self.check_args["bookings_current"] = [Mock(), Mock()] # Booked for 2 scenes

        result = checker.check(**self.check_args)

        self.assertFalse(result.is_available)
        self.assertIn("Will not shoot more than 2 scenes", result.reason)
        self.assertIn("(Avoiding burnout)", result.reason)

    def test_refuses_due_to_fatigue(self):
        """Should refuse if the role would cause extreme fatigue."""
        self.talent.fatigue = 50
        self.check_args["estimated_fatigue_gain"] = 41 # 50 + 41 > 90
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertEqual(result.reason, "Refuses work that would cause extreme fatigue.")

    def test_refuses_due_to_max_partners(self):
        """Should refuse if the scene has more partners than the talent allows."""
        self.talent.max_scene_partners = 2
        self.scene.virtual_performers = [Mock(), Mock(), Mock(), Mock()] # 4 performers = 3 partners
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertEqual(result.reason, "Refuses scenes with more than 2 partners.")

    def test_refuses_due_to_hard_limit(self):
        """Should refuse if the role involves a hard limit."""
        self.talent.hard_limits = {"Anal Sex"}
        self.checker.get_vp_role_context.return_value = ({"Anal Sex"}, {"Anal Sex": {"Giver"}})
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertEqual(result.reason, "Talent has a hard limit against 'Anal Sex'.")

    def test_refuses_due_to_concurrency_limit(self):
        """Should refuse if concurrent partners exceed the talent's limit for a concept."""
        self.talent.concurrency_limits = {"Anal": 1} # e.g., no DP
        
        # Simulate a scene segment with 1 receiver (our talent) and 2 givers
        segment_mock = Mock()
        segment_mock.tag_name = "Anal Sex"
        vp_assignment = Mock(virtual_performer_id=1, slot_id="Anal_Receiver_1")
        other_assignment1 = Mock(virtual_performer_id=2, slot_id="Anal_Giver_1")
        other_assignment2 = Mock(virtual_performer_id=3, slot_id="Anal_Giver_2")
        segment_mock.slot_assignments = [vp_assignment, other_assignment1, other_assignment2]
        
        self.scene.get_expanded_action_segments.return_value = [segment_mock]
        self.checker.get_vp_role_context.return_value = ({"Anal Sex"}, {"Anal Sex": {"Receiver"}})
        
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertEqual(result.reason, "Concurrency limit for 'Anal' exceeded (Max: 1, Scene has: 2).")

    def test_refuses_due_to_preference(self):
        """Should refuse if preference for a role is below the refusal threshold."""
        self.talent.tag_preferences = {"Anal Sex": {"Giver": 0.2}} # Below 0.3
        self.checker.get_vp_role_context.return_value = ({"Anal Sex"}, {"Anal Sex": {"Giver"}})
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertEqual(result.reason, "Strongly dislikes performing the 'Giver' role in 'Anal Sex'.")

    def test_refuses_due_to_orientation_conflict(self):
        """Should refuse with orientation reason if preference is very low."""
        self.talent.tag_preferences = {"Lesbian Sex": {"Giver": 0.05}} # Below 0.1
        self.checker.get_vp_role_context.return_value = ({"Lesbian Sex"}, {"Lesbian Sex": {"Giver"}})
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertEqual(result.reason, "Role involves 'Lesbian Sex', which conflicts with their sexual orientation.")

    def test_refuses_due_to_missing_required_policy(self):
        """Should refuse if a required studio policy is not active."""
        self.talent.policy_requirements = {"requires": ["policy_1"]}
        self.check_args["studio_policies"] = []
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertEqual(result.reason, "Requires the 'Required Policy' policy to be active.")

    def test_refuses_due_to_active_refused_policy(self):
        """Should refuse if a disliked studio policy is active."""
        self.talent.policy_requirements = {"refuses": ["policy_2"]}
        self.check_args["studio_policies"] = ["policy_2"]
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertEqual(result.reason, "Refuses to work with the 'Refused Policy' policy.")

    def test_refuses_due_to_low_total_budget(self):
        """Should refuse if total production budget is too low for their pickiness."""
        self.talent.popularity_scores = [Mock(score=500)] # total_pop=500
        self.talent.ambition = 60
        # Pickiness = (500 * 0.01) + (60 * 0.1) = 5 + 6 = 11. This is > 10.
        self.bloc_db.production_cost = 9000 # Below the 10k threshold for score 10.
        
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertIn("Considers the total production budget ($9,000) too low", result.reason)

    def test_refuses_due_to_low_department_budget(self):
        """Should refuse if a specific department budget is too low."""
        self.talent.popularity_scores = [Mock(score=800)] # total_pop=800
        self.talent.ambition = 80
        # Pickiness = (800 * 0.01) + (80 * 0.1) = 8 + 8 = 16. This is > 15.
        self.bloc_db.department_budgets = {"wardrobe": 4000} # Below the 5k threshold
        
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertIn("Requires a higher budget for Wardrobe", result.reason)

    def test_refuses_due_to_contract_dynamic_level(self):
        """Should refuse if scene dynamic exceeds contract max."""
        self.talent.contract = Mock(max_dynamic=1, allowed_concepts=["Anal"], allowed_orientations=["Straight"])
        self.scene.dom_sub_dynamic_level = 2
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertIn("Contract violation: Scene dynamic level (2) exceeds contract max (1)", result.reason)

    def test_refuses_due_to_contract_concept_violation(self):
        """Should refuse if scene concept is not in contract's allowed list."""
        self.talent.contract = Mock(max_dynamic=3, allowed_concepts=["Vaginal"], allowed_orientations=["Straight"])
        self.scene.dom_sub_dynamic_level = 1
        self.checker.get_vp_role_context.return_value = ({"Anal Sex"}, {"Anal Sex": {"Giver"}})
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertEqual(result.reason, "Contract violation: 'Anal' concept is not in the contract.")

    def test_refuses_due_to_contract_orientation_violation(self):
        """Should refuse if scene orientation is not in contract's allowed list."""
        self.talent.contract = Mock(max_dynamic=3, allowed_concepts=["Vaginal"], allowed_orientations=["Straight"])
        self.scene.dom_sub_dynamic_level = 1
        self.checker.get_vp_role_context.return_value = ({"Lesbian Sex"}, {"Lesbian Sex": {"Receiver"}})
        result = self.checker.check(**self.check_args)
        self.assertFalse(result.is_available)
        self.assertEqual(result.reason, "Contract violation: 'Lesbian' content is not in the contract.")

    def test_get_vp_role_context(self):
        """Should correctly parse roles and tags from scene segments."""
        # This test calls the original implementation of the method
        self.checker.get_vp_role_context = TalentAvailabilityChecker.get_vp_role_context
        
        segment1 = Mock()
        segment1.tag_name = "TagA"
        segment1.slot_assignments = [
            Mock(virtual_performer_id=1, slot_id="TagA_Role1_1"),
            Mock(virtual_performer_id=2, slot_id="TagA_Role2_1")
        ]
        
        segment2 = Mock()
        segment2.tag_name = "TagB"
        segment2.slot_assignments = [
            Mock(virtual_performer_id=1, slot_id="TagB_Role3_1"),
            Mock(virtual_performer_id=1, slot_id="TagB_Role4_1"), # VP 1 has two roles
            Mock(virtual_performer_id=3, slot_id="TagB_Role5_1")
        ]
        
        self.scene.get_expanded_action_segments.return_value = [segment1, segment2]

        tags, roles = self.checker.get_vp_role_context(self.checker, self.scene, 1)

        self.assertEqual(tags, {"TagA", "TagB"})
        self.assertEqual(roles, {
            "TagA": {"Role1"},
            "TagB": {"Role3", "Role4"}
        })

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
