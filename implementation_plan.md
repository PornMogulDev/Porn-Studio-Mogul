# Implementation Plan: Ethnic Tag Builder & Collapsible Categories

## Overview

Create a runtime tag builder system that generates ethnicity-gender physical tags dynamically, supporting hierarchical ethnicity validation, and enhance the Scene Planner UI with collapsible category support for better organization.

## Requirements Summary

**Tag Generation:**
- **Individual Tags:** Generate tags for *every* defined ethnicity (Primary groups AND Sub-groups).
    - Example: "White Male", "Western European Male", "Eastern European Male".
- **Pair Tags:** Generate tags only for *Primary* ethnicity combinations.
    - Example: "Interracial (Black/White)", "White/White", but *not* "Western European/Southern European".
- **Custom Names:** Replace specific generic names with industry terms (e.g., "Ebony" instead of "Black Female").
- **Runtime Builder:** A new class `PhysicalEthnicityTagBuilder`.

**Validation Logic:**
- Primary ethnicity tags must match performers of that primary ethnicity *or* any of its sub-groups (e.g., "Asian Female" tag accepts a "Southeast Asian" performer).
- Sub-group tags must match exact ethnicity (e.g., "Japanese Female" tag only accepts "Japanese").

**UI Enhancement:**
- Collapsible category headers for Physical tags in the Scene Planner.
- Group tags by `concept` (e.g., "Individual Ethnic", "Interracial", "Same-Ethnicity Pairs").

---

## Proposed Changes

### 1. [NEW] [PhysicalEthnicityTagBuilder](file:///src/data/builders/physical_ethnicity_tag_builder.py)

A runtime builder class initialized with the ethnicity hierarchy.

**Key Data Structure:**
It requires `ethnicity_hierarchy` from `DataManager` (e.g., `{ "White": ["Western European", ...], "Black": [] }`).

**Core Methods:**

1.  `generate_individual_tags()`:
    *   Iterate through **Primary** keys. Create tags (e.g., "White Male").
    *   Iterate through **Sub-group** lists. Create tags (e.g., "Western European Male").
    *   Apply `_apply_custom_name` (e.g., "Black Female" -> "Ebony").
    *   Set `concept` to `"Individual Ethnic"`.

2.  `generate_pair_tags()`:
    *   Iterate through **Primary** keys only.
    *   Generate all combinations (A/B) and Same-Ethnicity pairs (A/A).
    *   **Do not** descend into sub-groups for pairs.
    *   Set `concept` based on comparison:
        *   If A == B: `"Same-Ethnicity Pairs"`
        *   If A != B: `"Interracial Pairs"`

3.  `_create_tag_definition(name, gender, ethnicity, ...)`:
    *   Constructs the dictionary.
    *   **Validation Rule:** The builder simply sets the `ethnicity` field in the rule. The existing `TagValidationChecker` calling `DataManager.is_ethnicity_match` already handles the sub-group logic.

**Tag Structure Example (Individual - Primary):**
```python
{
    "name": "Asian Female",
    "type": "Physical",
    "concept": "Individual Ethnic",
    "categories": ["Race"],
    "gender": "Female",
    "ethnicity": "Asian", # Validator will accept "Southeast Asian" performer here
    "is_auto_taggable": True,
    "auto_detection_rule": {
        "conditions": [
             # Check affinity OR exact ethnicity match logic handled by checker
            {"type": "affinity", "key": "Asian", "comparison": "eq", "value": 100}
        ]
    },
    ...
}
```

**Tag Structure Example (Individual - Sub-group):**
```python
{
    "name": "Western European Female",
    "type": "Physical",
    "concept": "Individual Ethnic",
    "categories": ["Race"],
    "gender": "Female",
    "ethnicity": "Western European", # Validator requires exact match or match to self
    ...
}
```

---

### 2. [MODIFY] [data_manager.py](file:///src/data/data_manager.py)

Integrate the builder into the data loading pipeline.

**Changes:**
- Import `PhysicalEthnicityTagBuilder`.
- In `_load_scene_tags`:
    1.  Retrieve `self.get_ethnicity_hierarchy()`.
    2.  Instantiate builder.
    3.  Call `builder.generate_all_tags()`.
    4.  Update `tags` dictionary with results.
- **Verification:** Ensure `is_ethnicity_match` (already implemented in provided files) is available and correct. It currently checks: `if specific in primary_to_sub[required]: return True`. This supports the requirement that "Asian" tag accepts "Southeast Asian" performer.

---

### 3. [MODIFY] [game_config.json](file:///data/game_config.json)

Add configuration for ethnic tag revenue weights.

**New Config Keys:**
```json
{
  "ethnic_tag_individual_focused": 10.0,
  "ethnic_tag_individual_auto": 2.5,
  "ethnic_tag_pair_focused": 15.0,
  "ethnic_tag_pair_auto": 3.0
}
```

---

### 4. [NEW] [CollapsibleCategoryWidget](file:///src/ui/widgets/collapsible_category_widget.py)

Reusable widget replacing the standard `QListWidget` for Physical Tags.

**Logic:**
- Takes a list of Tag Dictionaries.
- Sorts them by `concept` field.
- Creates a `QTreeWidget` (or simulated list) where `concept` values are root nodes/headers.
- Individual tags are child items.
- Root nodes are collapsible.
- Supports drag-and-drop (mimicking `DraggableListWidget`).

**API:**
```python
class CollapsibleCategoryWidget(QTreeWidget): # Inherits QTreeWidget for native hierarchy support
    itemSelectionChanged = pyqtSignal()
    
    def set_tags(self, tags: List[Dict]) # Groups by 'concept'
    def get_selected_items(self) -> List[QTreeWidgetItem]
```

---

### 5. [MODIFY] [scene_planner_dialog.py](file:///src/ui/dialogs/scene_planner_dialog.py)

Replace the flat list for Physical Tags with the new collapsible widget.

**Changes:**
- Replace `self.available_physical_list` (DraggableListWidget) with `CollapsibleCategoryWidget`.
- Update `update_available_physical_tags` to pass the full tag data (so the widget can read the `concept`).
- Ensure `get_selected_available_physical_tags` works with the new widget API.

---

## Verification Plan

### Tag Generation
1.  **Check Primary:** Verify "Asian Male" exists.
2.  **Check Sub:** Verify "East Asian Male" exists.
3.  **Check Pairs:** Verify "Asian/White" exists.
4.  **Check Invalid Pairs:** Verify "East Asian/Western European" does **NOT** exist (Sub/Sub pairs should be skipped).

### Validation Logic (Unit Test)
1.  **Scenario A:** Cast a "Southeast Asian" performer.
    *   Check eligibility for "Asian Female" tag. **Expect: True** (Sub matches Primary).
    *   Check eligibility for "Southeast Asian Female" tag. **Expect: True** (Exact match).
    *   Check eligibility for "East Asian Female" tag. **Expect: False** (Sibling sub-group mismatch).
2.  **Scenario B:** Cast an "Asian" (Generic) performer.
    *   Check eligibility for "Asian Female" tag. **Expect: True**.
    *   Check eligibility for "Southeast Asian Female" tag. **Expect: False** (Parent does not match Sub).

### UI Behavior
1.  Open Scene Planner -> Physical Tags.
2.  Verify headers: "Individual Ethnic", "Interracial Pairs", "Same-Ethnicity Pairs".
3.  Expand "Individual Ethnic".
4.  Verify list includes both generic (White) and specific (Western European) tags.