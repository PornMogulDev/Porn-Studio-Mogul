import pytest

from data.builders.action_tag_builder import ActionTagBuilder


@pytest.mark.parametrize(
    ("receiver_gender", "expected_slots"),
    [
        ("Male", {"Straight": ("Male", "Female"), "Gay": ("Male", "Male"), "Bi": ("Male", "Any")}),
        ("Female", {"Straight": ("Female", "Male"), "Lesbian": ("Female", "Female"), "Bi": ("Female", "Any")}),
        ("Any", {"Straight": ("Any", "Any"), "Gay": ("Male", "Male"), "Lesbian": ("Female", "Female")}),
    ],
    ids=["male-receiver", "female-receiver", "flexible-receiver"],
)
def test_template_expansion_resolves_slots_for_each_orientation(receiver_gender, expected_slots):
    template = {
        "name": "Test Tag",
        "orientation": "Template",
        "is_orientation_template": True,
        "is_template": True,
        "expands_to": list(expected_slots),
        "slots": [
            {"role": "Receiver", "gender": receiver_gender},
            {"role": "Giver", "gender": "Dependent"},
        ],
    }

    expanded = ActionTagBuilder.expand_template(template)

    assert [tag["orientation"] for tag in expanded] == list(expected_slots)
    for tag in expanded:
        receiver, giver = expected_slots[tag["orientation"]]
        assert tag["slots"] == [
            {"role": "Receiver", "gender": receiver},
            {"role": "Giver", "gender": giver},
        ]
        assert tag["is_template"] is True
        assert "is_orientation_template" not in tag
        assert "expands_to" not in tag
    assert template["orientation"] == "Template"
    assert template["slots"][1]["gender"] == "Dependent"
