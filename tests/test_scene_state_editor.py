from types import SimpleNamespace

from data.game_state import Scene
from services.builders.scene_state_editor import SceneStateEditor
from services.calculation.tag_validation_checker import TagValidationChecker


def test_shrinking_segment_clears_removed_slot_before_casting():
    data_manager = SimpleNamespace(tag_definitions={
        "Test Segment": {
            "type": "Action",
            "slots": [
                {"role": "Receiver", "parameterized_by": "count", "min_count": 1},
                {"role": "Giver", "count": 1},
            ],
        },
    })
    scene = Scene(
        id=1, title="Test Scene", status="design", focus_target="Test Group",
        scheduled_absolute_week=1, location="Studio",
    )
    editor = SceneStateEditor(scene, data_manager, TagValidationChecker(data_manager))
    editor.update_performer_count(3)
    receiver, extra_receiver, giver = editor.working_scene.virtual_performers
    segment_id = editor.add_action_segment("Test Segment")
    editor.update_action_segment_runtime(segment_id, 100)
    editor.update_action_segment_parameter(segment_id, "Receiver", 2)
    editor.update_slot_assignment(segment_id, "Test Segment_Receiver_1", "Receiver", receiver.id)
    editor.update_slot_assignment(segment_id, "Test Segment_Receiver_2", "Receiver", extra_receiver.id)
    editor.update_slot_assignment(segment_id, "Test Segment_Giver_1", "Giver", giver.id)

    editor.update_action_segment_parameter(segment_id, "Receiver", 1)

    assert editor.validate_and_set_status("Casting") == (True, "")
    saved_scene = editor.finalize_for_saving()
    segment, = saved_scene.action_segments
    assert saved_scene.status == "casting"
    assert saved_scene.is_locked
    assert segment.parameters == {"Receiver": 1, "Giver": 1}
    assert [(slot.slot_id, slot.virtual_performer_id) for slot in segment.slot_assignments] == [
        ("Test Segment_Receiver_1", receiver.id),
        ("Test Segment_Giver_1", giver.id),
    ]
