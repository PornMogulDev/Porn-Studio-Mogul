
## Request Flow (Scene Editing)

1. User interacts with `ScenePlannerDialog` (UI)
2. UI events trigger signals connected to `ScenePlannerPresenter`
3. Presenter calls methods on `SceneStateEditor` (Service)
   - e.g., `editor.update_performer_count(3)`, `editor.add_style_tag("Romantic")`
4. `SceneStateEditor` modifies the `working_scene` (Data Model)
   - It may query `DataManager` for tag definitions or validation rules.
   - It uses `TagValidationChecker` for complex logic (e.g., orientation checks).
5. Presenter refreshes the UI by reading the updated `working_scene` state.
6. On Save:
   - Presenter calls `editor.finalize_for_saving()`
   - Presenter calls `controller.update_scene_full(scene)`
   - Controller persists changes to DB via `DataManager` (or relevant repository).

## Request Flow (Bulk Hiring & Validation)

This flow uses a two-phase validation approach: a fast, responsive **Preview Phase** for the UI and a transactional **Commit Phase** to act as a final guardrail.

### 1. Preview Phase (UI Feedback)

This phase happens in real-time as the user selects roles in the `HiringWidget`.

1.  User selects one or more roles in `HiringWidget` (UI).
2.  `HiringWidget` emits `preview_cost_requested` signal with the selected roles.
3.  `TalentProfilePresenter` receives the signal and calls `controller.validate_potential_bookings(talent_id, roles)`.
4.  `GameController` instantiates `BulkBookingValidator` with the talent's current state and existing bookings (fetched via `TalentQueryService`).
5.  The controller iterates through the roles, calling `validator.try_book_role()` for each.
6.  The controller then calls `controller.calculate_bulk_hiring_costs()` with only the *valid* roles.
7.  The final breakdown of costs and any invalid roles (with reasons) is returned to the presenter.
8.  `TalentProfilePresenter` pushes the results to `HiringWidget.update_cost_preview()`, which updates the total cost label and highlights any invalid roles in red.

### 2. Commit Phase (Transactional Guardrail)

This phase executes when the user clicks the final "Hire" button.

1.  User clicks "Hire" in `HiringWidget`.
2.  `HiringWidget` emits `hire_confirmed` with the final hiring data (which includes pre-calculated costs from the preview phase).
3.  `TalentProfilePresenter` calls `controller.cast_talent_for_multiple_roles(talent_id, hiring_data)`.
4.  `GameController` delegates this to `CastingCommandService.cast_talent_for_multiple_roles()`.
5.  The `CastingCommandService` starts a database transaction.
6.  **Crucially, it instantiates a new `BulkBookingValidator`** using data from within the current DB transaction.
7.  It re-validates all bookings by calling `validator.try_book_role()` for each role.
    - If validation fails, it raises an exception, and the entire transaction is rolled back. No changes are saved.
    - This ensures data integrity and prevents invalid states, even if the UI layer had a bug or the game state changed between the preview and commit.
8.  If validation succeeds, it proceeds to create `SceneCastDB` entries, update player money, and commits the transaction.
9.  Success signals (`money_changed`, `scenes_changed`) are emitted.

## Calculation Flow (Role Performance Modifiers)

This is a low-level, backend-only flow for a pure utility calculator.

1.  A higher-level service (e.g., `TalentDemandCalculator` or `ShootResultsCalculator`) needs to determine a modifier for a performer's role in a specific `ActionSegment`.
2.  It calls either `get_role_demand_modifier()` or `get_role_stamina_modifier()` on the `RolePerformanceCalculator` instance.
3.  The calculator finds the performer's assigned `slot_id` (e.g., `"Blowjob (Straight)_Giver_1"`).
4.  It parses the `slot_id` to extract the `role` name (e.g., `"Giver"`) and validates this role against the list of possible roles in the tag's definition.
5.  It looks up the slot definition for that role in the tag definition (from `action_tags.json`).
6.  From the slot definition, it retrieves the base modifier (e.g., `stamina_modifier`) and any scaling factors (e.g., `stamina_modifier_scaling_per_peer`).
7.  It checks the `segment.parameters` to find the number of "peers" (performers in the same role) and "others" (performers in the opposing role).
8.  It calculates a final modifier by adding the scaled bonuses to the base modifier and returns this `float` value to the calling service.

## Calculation Flow (Production Quality & Skill)

This backend flow determines the final quality of production departments (e.g., Wardrobe) and the skill of generic crew members when a new `ShootingBloc` is created. These values are "rolled" once and cached for the duration of the bloc.

1.  User finalizes a `ShootingBloc` via the UI, which calls `SceneCommandService.create_shooting_bloc()`.
2.  The `SceneCommandService` gathers all budget data (`department_budgets`, `crew_assignments`, `budget_per_scene`, etc.).
3.  It calls `CrewSkillCalculator.generate_production_cache()`, passing in the budget information.
4.  The `CrewSkillCalculator` iterates through each budgeted item (resource or generic crew).
5.  For each item, it determines the **per-scene budget**.
6.  It fetches the item's definition (from `production_departments.json`, `production_jobs.json`, or dynamically for the location).
7.  It calls `BudgetEfficiencyCalculator.calculate_efficiency()` with the per-scene budget to get a raw efficiency multiplier (e.g., 1.15).
8.  The `CrewSkillCalculator` converts this efficiency into a base score (e.g., 85) and applies a random variance (`random.gauss`) to get the final score.
9.  The final score is clamped between 1 and 100.
10. The calculator returns a complete `production_cache` dictionary (e.g., `{'wardrobe': 88, 'camera_a': 75}`).
11. `SceneCommandService` stores this cache on the new `ShootingBlocDB` record in the database.

## Request Flow (Scene Quality Calculation)

This is a backend-only flow that occurs when the game week is advanced. It calculates the final quality of a scene after it has been "shot".

1.  The `TimeService.advance_week` method begins the weekly update transaction.
2.  For each scene scheduled for the current week, it calls `SceneCommandService.shoot_scene`.
3.  This eventually delegates to `SceneProcessingService.run_shoot_calculations`, which orchestrates the process.
4.  The `SceneProcessingService` fetches all required data from the database: the full `Scene`, all cast `Talent` objects, and the parent `ShootingBloc`'s production settings.
5.  It calls `SceneQualityCalculator.calculate_quality()`, passing in all the prepared data.
6.  The `SceneQualityCalculator` executes its complex, multi-stage calculation:
    *   First, it aggregates modifiers from **Thematic Tags** (e.g., to amplify chemistry or production settings).
    *   Next, it calculates the quality of **Action Tags** by determining each performer's contribution based on their skills, fatigue, stamina, and chemistry.
    *   Then, it calculates the quality of **Physical Tags** based on the `quality_source` rules in the tag definition.
    *   Finally, it calculates a total **Production Modifier** from bloc settings (e.g., camera, location), which is then applied to all scores.
7.  The calculator returns a `SceneQualityResult` dataclass containing all the calculated scores.
8.  The `SceneProcessingService` receives this result and calls `apply_shoot_calculation_results` to write the final `tag_qualities` and `performer_contributions` into the `SceneDB` model, completing the process.

## Calculation Flow (Shooting Bloc Cost)

This flow details how the total upfront financial cost of a `ShootingBloc` is determined when a new bloc is created.

1.  A user finalizes planning for a `ShootingBloc` (e.g., via a UI action), leading to a call to `SceneCommandService.create_shooting_bloc()`.
2.  The `SceneCommandService` collects all budget-related data, including:
    *   `location_id`
    *   `department_budgets` (total dollar amounts allocated per department for the bloc)
    *   `crew_assignments` (specific assignments, including freelancer budgets)
    *   `picture_set_settings`
3.  The service then calls `BlocCostCalculator.calculate_shooting_bloc_cost()` with this collected data.
4.  The `BlocCostCalculator` performs the following steps:
    *   It sums the total `dollar_amount` from all `department_budgets`.
    *   It iterates through `crew_assignments` and adds the `budget` for any entries identified as `'freelancer'` type.
    *   (Note: Costs related to `picture_set_settings` are currently not directly calculated by this method, but are assumed to be integrated into `department_budgets` or `crew_assignments` if applicable).
5.  The `BlocCostCalculator` returns the grand `total_cost` for the entire shooting bloc.
6.  The `SceneCommandService` then deducts this `total_cost` from the player's `StudioState` money and proceeds to create the `ShootingBlocDB` entry in the database.
