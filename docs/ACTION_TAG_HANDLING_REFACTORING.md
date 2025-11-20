# Action Tag Handling Refactoring

## Overview
The Action Tag system was refactored to support **Template Expansion** and **Fluid Orientation Logic**. This replaces the need for hardcoded variations of every act (e.g., "Blowjob (Male)", "Blowjob (Female)") with a single definition that adapts to the scene's context.

This system distinguishes between **Anatomy-Locked Actions** (e.g., Blowjobs, where genitals matter) and **Universal Actions** (e.g., Peeing, Rimming, where anatomy is secondary to the orientation pairing).

---

## 1. Data Model: Action Templates
Action tags in `action_tags.json` can now be defined as **Templates**.

### New Properties
*   **`orientation`**: Set to `"Template"`.
*   **`expands_to`**: A list of target orientations (e.g., `["Straight", "Gay", "Lesbian", "Bi"]`) or pseudo-orientations (`["Male", "Female"]` for solo acts).
*   **`slots[].gender`**:
    *   `"Any"`: Represents a fluid slot (used for Universal acts).
    *   `"Dependent"`: Represents a slot that changes based on the specific expansion (used for Anatomy-Locked acts).

### Example: Anatomy-Locked (Blowjob)
*Logic: A Straight Blowjob implies a Male Receiver. A Gay Blowjob implies a Male Receiver.*
```json
{
  "name": "Blowjob",
  "orientation": "Template",
  "expands_to": ["Straight", "Gay"],
  "slots": [
    { "role": "Receiver", "gender": "Male" },     // Fixed
    { "role": "Giver", "gender": "Dependent" }    // Calculates based on Receiver
  ]
}
```

### Example: Universal/Fluid (Pee in Mouth)
*Logic: A Straight Pee scene allows M->F or F->M. A Gay scene is only M->M.*
```json
{
  "name": "Pee in Mouth",
  "orientation": "Template",
  "expands_to": ["Straight", "Gay"],
  "slots": [
    { "role": "Receiver", "gender": "Any" },
    { "role": "Giver", "gender": "Any" }
  ]
}
```

---

## 2. The Builder: `ActionTagBuilder`
Located in `src/data/builders/action_tag_builder.py`.
This class runs at application startup (inside `DataManager`) to expand templates into concrete tags in memory.

### Logic Rules
1.  **Gay / Male Expansion**:
    *   `Any` -> Becomes `Male`.
    *   `Dependent` -> Becomes `Male`.
2.  **Lesbian / Female Expansion**:
    *   `Any` -> Becomes `Female`.
    *   `Dependent` -> Becomes `Female`.
3.  **Straight Expansion**:
    *   `Any` -> **Remains `Any`** (allows for fluid roles).
    *   `Dependent` -> Checks the *other* slot. If other is `Male`, this becomes `Female`, and vice versa.

---

## 3. Validation: `TagValidationChecker`
Located in `src/services/calculation/tag_validation_checker.py`.
Because the Builder allows "Straight" tags to have `Any/Any` slots, we need runtime validation to ensure the player doesn't create a "Straight" scene with two Men.

### Validation Logic
1.  **Straight Validation**:
    *   If a tag is `Straight` and has >1 participant, the group **MUST** contain at least one Male and one Female.
    *   *M + M* = Invalid.
    *   *F + F* = Invalid.
    *   *M + F* = Valid.
2.  **Mono-Gender Validation**:
    *   `Gay`: Error if any Female is present.
    *   `Lesbian`: Error if any Male is present.

---

## 4. UI Integration: `ScenePlannerPresenter`
The UI was updated to provide immediate feedback and prevent invalid states.

### A. Dropdown Filtering (Hard Stop)
When the user opens a dropdown to assign a performer to a slot:
1.  The system checks the **Gender** requirement of the slot.
2.  The system performs a **Hypothetical Assignment Check**: "If I put this specific Performer in this slot, does it violate the Orientation rules?"
3.  *Example:* In a "Straight" scene where Slot A is already "Male", the dropdown for Slot B will **hide** all Male performers.

### B. Dynamic Labels (Visual Feedback)
The labels above the dropdowns (e.g., "Requires: Any") now update in real-time based on context.

**Logic:**
1.  **Peer Check:** If a peer slot has a `Male` assigned in a Straight scene, the current slot label updates to **"Requires: Female"**.
2.  **Self Check:** If the current slot has a `Male` assigned, the label updates to **"Requires: Male"** to reflect the current state.

### Implementation Details
*   **Presenter**: Calculates the `effective_gender_req` string.
*   **Dialog**: Passes this string to the widget.
*   **`SlotAssignmentWidget`**: Displays the overridden string instead of the static database definition.