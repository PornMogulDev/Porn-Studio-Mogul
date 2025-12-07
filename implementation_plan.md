# AI Studio Archetypes Implementation

Replaces the hardcoded AI studio creation and simple quality-based saturation with a comprehensive archetype-based system that generates scenes with random tags, runs full revenue calculations, and generates saturation effects per viewer group based on interest scores.

## User Review Required

> [!IMPORTANT]
> **Database Schema Changes**: The `AISceneDB` model will need new fields to store tag data and revenue calculation results. This will require database migration handling.

> [!WARNING]
> **No Data Migration for Existing Saves**: Per user requirement, we will NOT migrate existing save files. Only the `migrate_to_sqlite.py` script will be updated to reference the new schema.

## Proposed Changes

### Data Layer

#### [NEW] [ai_studio_archetypes.json](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/data/ai_studio_archetypes.json)

Create AI studio archetype definitions similar to `talent_archetypes.json`:

```json
[
  {
    "id": "mainstream_hetero",
    "name": "Mainstream Straight Studio",
    "weight": 30,
   "orientation": "Straight",
    "focus_groups": ["Straight Men", "Straight Women"],
    "locations": ["South West (US)", "South East (US)", "Midwest (US)"],
    "scenes_per_month": {"min": 3, "max": 5},
    "tag_quality_range": {"min": 50.0, "max": 85.0},
    "tag_preferences": {
      "action_tags": {
        "Blowjob": 1.5,
        "Vaginal": 2.0,
        "Anal": 1.2,
        "Facial": 1.3
      },
      "physical_tags": {
        "Big Boobs": 1.5,
        "Teen": 1.3,
        "MILF": 1.2
      },
      "thematic_tags": {
        "Boobs Worship": 0.8
      }
    }
  }
]
```

Structure:
- Basic info: `id`, `name`, `weight` for generation probability
- `orientation`: Scene orientation (Straight, Gay, Lesbian, Bi) - all tags must match this
- `focus_groups`: List of viewer groups this studio targets (pick one per scene)
- `locations`: Possible studio locations (pick one)
- `scenes_per_month`: Min/max range for monthly production
- `tag_quality_range`: Min/max for generated tag quality scores
- `tag_preferences`: Weighted probabilities for tag selection by category

Tags with "Male" or "Female" pseudo-orientations can be selected for any scene if listed in the archetype.

---

### Core Generation Layer

#### [NEW] [ai_studio_generator.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/core/ai_studio_generator.py)

Create generator class following the pattern from `talent_generator.py`:

- `__init__(self, archetype_data, tag_definitions, market_data, location_data)`: Initialize with data dependencies
- `_weighted_choice(self, options)`: Utility for weighted random selection
- `_select_archetype(self)`: Choose archetype based on weights
- `generate_ai_studio(self, studio_id)`: Generate single AI studio from archetype
- `generate_multiple_studios(self, count, start_id)`: Generate multiple studios

Returns `AIStudio` dataclass instances ready to be converted to `AIStudioDB`.

---

### Database Layer

#### [MODIFY] [db_models.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/database/db_models.py)

Update `AIStudioDB` to add:
- `archetype_id` (String, nullable): Reference to archetype used for this studio

Update `AISceneDB` to replace simple `quality_score` with full tag and revenue data:
- Remove: `quality_score` field
- Add: `orientation` (String): Scene orientation
- Add: `global_tags` (JSON, list): Thematic tags
- Add: `assigned_tags` (JSON, dict): Physical tags with quality
Add: `action_segments` (JSON, list): Action tags with runtime and quality
- Add: `tag_qualities` (JSON, dict): Quality scores per tag
- Add: `viewer_group_interest` (JSON, dict): Interest scores per viewer group
- Add: `revenue` (Integer, default=0): Total calculated revenue
- Add: `revenue_modifier_details` (JSON, dict): Revenue modifiers for debugging

Keep `target_market_group` for backwards compatibility.

---

### Service Layer - AI Director

#### [MODIFY] [ai_studio_director.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/ai/ai_studio_director.py)

Update `_create_scene()` method to:

1. **Generate Scene Data**:
   - Select orientation from studio's archetype
   - Select focus group from archetype's `focus_groups`
   - Generate 2-5 tags from each category (physical, action, thematic)
   - Weight tag selection by archetype preferences
   - Filter tags by orientation (tags must match scene orientation OR have "Male"/"Female" pseudo-orientation)
   - Generate random quality for each tag within archetype's quality range

2. **Create Scene Mock Object**:
   - Build minimal `Scene` dataclass with required fields for revenue calculation
   - Populate: `global_tags`, `assigned_tags`, `action_segments`, `tag_qualities`, `focus_target`
   - Create simple `action_segments` with runtime percentages (distribute evenly)
   - Use default `dom_sub_dynamic_level` of 1
   - Set `total_runtime_minutes` to a standard value (e.g., 30)

3. **Calculate Revenue**:
   - Call `revenue_calculator.calculate_revenue()` with mock Scene, empty cast list, current market states, resolved groups
   - Extract `viewer_group_interest` and `total_revenue` from result

4. **Persist**:
   - Pass all generated data to `ai_studio_command_service.create_ai_scene()`

Update `_process_scene_releases()` to:
- Use `viewer_group_interest` scores instead of single `quality_score`
- Apply saturation updates to ALL groups based on their interest scores
- Scale saturation impact: `impact = (interest_score / max_possible_interest) * base_impact`

---

### Service Layer - Command Service

#### [MODIFY] [ai_studio_command_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/command/ai_studio_command_service.py)

Update `create_ai_scene()` signature and logic:
- Add parameters: `orientation`, `global_tags`, `assigned_tags`, `action_segments`, `tag_qualities`, `viewer_group_interest`, `revenue`
- Create `AISceneDB` with all new fields populated

---

### Game Session Service

#### [MODIFY] [game_session_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/game_session_service.py)

In `start_new_game()` method:
1. Remove hardcoded AI studio creation (lines 74-89)
2. Add dependency injection for `AIStudioGenerator`
3. Call `ai_studio_generator.generate_multiple_studios(count=3, start_id=1)` 
4. Persist generated studios to database via `AIStudioDB.from_dataclass()`

Set initial studio count to 3 (matching current behavior).

---

### Data Manager Integration

#### [MODIFY] [data_manager.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/data/data_manager.py)

Add loading for AI studio archetypes:
- Add `ai_studio_archetypes` property
- Load from `data/ai_studio_archetypes.json` in `__init__()`
- Handle file loading errors gracefully

---

### Service Container

#### [MODIFY] [service_container.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/core/service_container.py)

Add `AIStudioGenerator` to dependency injection:
- Instantiate with archetype data, tag definitions, market data, location data
- Make available to `GameSessionService`
- Wire up dependencies for `AIStudioDirector` (needs `revenue_calculator`)

---

### Migration

#### [MODIFY] [migrate_to_sqlite.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/data/scripts/migrate_to_sqlite.py)

Update to reflect new schema:
- Update `AIStudioDB` table creation to include `archetype_id`
- Update `AISceneDB` table creation with new JSON fields
- No need to handle old data migration per user requirement

---

## Verification Plan

### Automated Tests

No existing automated tests were found for AI studios. We will verify manually.

### Manual Verification

1. **Start New Game**:
   - Run `python src/main.py`
   - Create a new game
   - Verify 3 AI studios are created with varied archetypes, locations, and preferences
   - Check database directly: should see AIStudioDB records with `archetype_id` populated

2. **Advance Time to Trigger Scene Creation**:
   - Advance to week 2 (first week of first month)
   - Check logs for scene creation messages
   - Verify scenes are created with tags and calculated revenue
   - Check database: AISceneDB should have `global_tags`, `assigned_tags`, `action_segments`, `tag_qualities`, `viewer_group_interest`, and `revenue` fields populated

3. **Verify Revenue Calculation**:
   - Check that `viewer_group_interest` contains scores for multiple groups
   - Verify `revenue` is non-zero and reasonable
   - Check logs for saturation updates to multiple market groups

4. **Verify Scene Release**:
   - Advance time to scene release week (creation week + 2)
   - Verify saturation is applied to market groups based on interest scores
   - Check `MarketGroupStateDB` to see saturation changes

5. **Verify Tag Selection Follows Archetype**:
   - Examine generated scenes in database
   - Verify all action/physical tags match the archetype's orientation
   - Verify tags with weights in archetype appear more frequently
   - Verify tag qualities fall within archetype's quality range
