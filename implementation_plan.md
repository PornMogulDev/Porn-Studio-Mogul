# Implementation Plan: AI Studio Archetypes

## 1. Data Layer

### [NEW] `data/ai_studio_archetypes.json`
Use the specific structure provided.

```json
[
  {
    "id": "mainstream_hetero",
    "name": "Mainstream Straight Studio",
    "weight": 30,
    "orientation": "Straight",
    "focus_groups": {"Straight Women": 0.2, "Straight Men": 0.8},
    "locations": {"South West (US)": 0.8, "South East (US)": 0.3, "Spain": 0.2 },
    "scenes_per_month": {"min": 3, "max": 5},
    "tag_quality_range": {"min": 30.0, "max": 85.0},
    "dom_sub_dynamic": {"0": 0.3, "1": 0.7, "2": 0.5, "3": 0.4 },
    "tag_weights": {
      "action_tags": {
        "Blowjob": 1.5,
        "Vaginal": 2.0
      },
      "physical_tags": {
        "Big Boobs": 1.5,
        "Teen": 1.3
      },
      "thematic_tags": {
        "Boobs Worship": 0.8
      }
    }
  }
]
```

### 2. Core Generation Layer

#### [NEW] `src/core/ai_studio_generator.py`

Create a new generator class. Unlike `TalentGenerator` which takes unpacked dicts, pass `DataManager` to the constructor for cleaner access to tag definitions and market data.

*   **`__init__(self, data_manager: DataManager)`**:
    *   Store `data_manager`.
    *   Cache `tag_definitions` and `market_data` for quick access.

*   **`generate_studios(self, count: int, start_id: int) -> List[AIStudio]`**:
    *   Load `ai_studio_archetypes.json` from `data_manager` (you may need to add this loader to `DataManager` first).
    *   Loop `count` times:
        *   **Select Archetype**: Weighted random choice from the loaded archetypes.
        *   **Resolve Location**: Weighted random choice from `archetype.locations`.
        *   **Resolve Name**: Use `archetype.name` (or append a number/variation if desired).
        *   **Resolve Focus**: Identify `preferred_market_groups` from `archetype.focus_groups`.
        *   **Instantiate**: Create and return `AIStudio` dataclass (ensure `archetype_id` is populated).

*   **`generate_scene_parameters(self, archetype: dict, current_week: int) -> dict`**:
    *   **Objective**: Return a dictionary of parameters required to build a `Scene` object (orientation, dynamic level, tags).
    *   **Orientation**: Taken directly from `archetype['orientation']`.
    *   **Dynamic Level**: Weighted choice from `archetype['dom_sub_dynamic']`.
    *   **Target Market**: Weighted choice from `archetype['focus_groups']`.
    *   **Tag Generation**:
        *   Initialize an empty list `selected_tags`.
        *   Determine target count (approx 5 total, or derived from `scenes_per_month` complexity logic if added).
        *   Iterate through `archetype['tag_weights']` (which contains categories like `action_tags`, `physical_tags`, `thematic_tags`).
        *   For each category, perform **Concept Resolution**:
            *   Iterate the keys (e.g., "Blowjob", "Big Boobs").
            *   Check `tag_definitions`:
                *   **Is it a Concept?** (Check if any tag has this `concept` string). If yes, gather all tags with that concept that match the studio's `orientation`.
                *   **Is it a Tag Name?** (Check if key exists as a specific tag name).
            *   Add valid specific tags to a weighted pool based on the archetype's value.
        *   Select tags from this pool until target count is reached.
        *   **Quality Assignment**: For each selected tag, generate a quality score using `random.uniform` within `archetype['tag_quality_range']`.
    *   **Return**: `{'orientation': str, 'dom_sub_level': int, 'target_market': str, 'tags': Dict[str, float]}`.

#### [MODIFY] `src/core/talent_generator.py`

*   **No Code Changes needed inside the file**, but its **lifecycle** changes. It is no longer instantiated in `GameController`.

## 3. Database Layer

### `src/database/db_models.py`

**Modify `AIStudioDB`**:
*   Add `archetype_id` (String).

**Modify `AISceneDB`**:
*   **Remove**: `target_market_group` (Legacy field removed).
*   **Remove**: `quality_score` (Legacy field removed).
*   **Add**: `orientation` (String).
*   **Add**: `dom_sub_dynamic_level` (Integer).
*   **Add**: `global_tags` (JSON List) - Thematic tags.
*   **Add**: `assigned_tags` (JSON Dict) - Physical tags (Name -> Quality).
*   **Add**: `action_segments` (JSON List) - Action tags.
*   **Add**: `viewer_group_interest` (JSON Dict) - The calculated interest scores.
*   **Add**: `revenue` (Integer) - Calculated synthetic revenue.
*   **Add**: `revenue_modifier_details` (JSON Dict) - Saved for debugging/player insight (e.g. "Why did this rival movie do well?").

### 4. Service Layer

#### [MODIFY] `src/core/service_container.py`

Update the container to manage the lifecycle of the generators.

*   **Update `__init__`**:
    *   Add `self.talent_generator: Optional[TalentGenerator] = None`
    *   Add `self.ai_studio_generator: Optional[AIStudioGenerator] = None`

*   **Update `initialize_and_populate_services`**:
    *   **Level 0 (No dependencies)**:
        *   Instantiate `TalentGenerator`.
            *   *Note:* Pass the specific dictionaries from `self.data_manager` as currently required by `TalentGenerator.__init__` (e.g., `game_constant`, `generator_data`, `affinity_data`, etc.).
        *   Instantiate `AIStudioGenerator`.
            *   Pass `self.data_manager`.

    *   **Injection (Level 2/3)**:
        *   When instantiating `AIStudioDirector`, inject `self.ai_studio_generator`.
        *   *Correction to GameSessionService:* The `GameSessionService` currently takes `talent_generator` in `__init__`. You must now update the instantiation of `GameSessionService` in `initialize_and_populate_services` (or wherever it is created) to pass these two generator instances.

*   **Update `_clear_container_services`**:
    *   Set `self.talent_generator = None`.
    *   Set `self.ai_studio_generator = None`.

#### [MODIFY] `src/services/game_session_service.py`

*   **Update `__init__`**:
    *   Add argument `ai_studio_generator: AIStudioGenerator`.
    *   Store it as `self.ai_studio_generator`.

*   **Update `start_new_game`**:
    *   Remove the hardcoded AI studio generation logic (lines 74-89 in the provided snippet).
    *   Call `studios = self.ai_studio_generator.generate_studios(count=3, start_id=1)`.
    *   Iterate through `studios` and persist them: `session.add(AIStudioDB.from_dataclass(studio))`.

#### [MODIFY] `src/services/ai/ai_studio_director.py`

*   **Update `__init__`**:
    *   Add argument `ai_studio_generator: AIStudioGenerator`.
    *   Store it as `self.generator`.

*   **Update `_create_scene(self, session, studio_db, current_week)`**:
    *   **Fetch Archetype**: Use `studio_db.archetype_id` to look up the full archetype definition from `self.data_manager.ai_studio_archetypes`.
    *   **Generate Params**: Call `params = self.generator.generate_scene_parameters(archetype, current_week)`.
    *   **Build Mock Scene**:
        *   Create `Scene` dataclass.
        *   Set `orientation`, `dom_sub_dynamic_level` from `params`.
        *   Populate `global_tags` (Thematic) and `assigned_tags` (Physical) from `params['tags']`.
        *   Create dummy `ActionSegment` objects for the Action tags in `params['tags']`.
        *   Set `tag_qualities` using the scores from `params['tags']`.
    *   **Calculate**: Pass mock scene to `self.revenue_calculator.calculate_revenue`.
    *   **Persist**: Pass `params` and revenue results to `command_service.create_ai_scene`.

## 5. Migration Script

### `data/scripts/migrate_to_sqlite.py`
*   Since we are not keeping `target_market_group`, this is a breaking schema change.
*   **Action**: Drop `ai_scenes` table and recreate it with the new columns.
*   **Action**: Alter `ai_studios` to add `archetype_id`.
*   *Note:* Since this is a dev/prototype phase, dropping the AI scene table is acceptable (player loses history of AI movies, but not their own).

## 6. Implementation Steps

1.  **JSON**: Create `ai_studio_archetypes.json`.
2.  **Model**: Update `db_models.py` (Drop columns, add JSON fields).
3.  **Generator**: Implement `AIStudioGenerator` with the "Concept vs Tag" resolution logic.
4.  **Container**: Wire generators into `ServiceContainer`.
5.  **Logic**: Update `AIStudioDirector` to use `RevenueCalculator`.
6.  **Command**: Update `AIStudioCommandService` signatures.
7.  **Startup**: Update `GameSessionService` to use the generator.
8.  **Run Migration**.

