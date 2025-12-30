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

## Calculation Flow (UI Quality Estimation)

This flow occurs in the `ShootingBlocBuilder` (and associated UI) to provide the player with a real-time *estimate* of the quality or skill they can expect from their budget allocations. This flow is for immediate UI feedback and differs slightly from the final calculation.

1.  The `ShootingBlocBuilder.get_ui_data()` method is called whenever the UI needs to be refreshed.
2.  It iterates through each department (e.g., Wardrobe) and crew slot (e.g., Director).
3.  For each item, it calculates the **per-scene budget** based on the user's allocation percentage.
4.  It calls `CrewSkillCalculator.calculate_efficiency_raw()` to get the raw, uncapped efficiency multiplier from the `BudgetEfficiencyCalculator`.
5.  **Crucially, it then calculates the estimated score differently for resources vs. crew:**
    *   **For Resources (Departments):** It calculates an uncapped quality score (`score = int(efficiency * baseline_multiplier)`). This allows the UI to show values over 100 (e.g., "Quality: 153"), demonstrating the full potential of a high budget.
    *   **For Crew:** It calculates a skill range that is capped at 100 (`min_s = max(1, ...)` and `max_s = min(100, ...)`). This aligns with the fact that the final "rolled" crew skill in the `production_cache` is also capped at 100.
6.  This provides the player with an accurate-but-distinct preview: "Quality" for departments can exceed 100, while "Skill" for crew members respects the 1-100 mechanic.

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

## Calculation Flow (Scene Revenue)

This flow describes how final revenue is calculated for a released scene, typically after a `shoot_scene` process is complete.

1.  A higher-level service (e.g., `SceneProcessingService` after a scene is shot) needs to calculate the revenue for a scene.
2.  It constructs a `RevenueInput` DTO containing all necessary data: global thematic tags, weighted content tags with quality scores, star power scores for each market group, etc.
3.  It calls `RevenueCalculator.calculate_revenue()`, passing the `RevenueInput` DTO, current `MarketGroupState` for all markets, and resolved market group preference data.
4.  The `RevenueCalculator` iterates through each `viewer_group` defined in the market data.
5.  For each group, it calculates a final `group_interest_score`:
    *   It starts by summing **additive appeal** from thematic tags (e.g., `+0.05` for "Romantic").
    *   It then calculates a **multiplicative content appeal**. This is a weighted average based on the quality and viewer preference for each physical and action tag. This score is normalized by the total weight of all content tags.
        *   Tag preferences are modified by orientation sentiments (e.g., "Straight", "Lesbian").
        *   Further adjustments are made based on `scaling_sentiments` rules, which can provide bonuses or penalties based on the count of performers in a specific role (e.g., diminishing returns for having too many "Givers" in a gangbang scene).
    *   The score is then modified by Dom/Sub preference, star power bonuses, and any focus group bonus.
6.  The `group_interest_score` is used to determine the revenue generated from that group, adjusted for market `saturation`, `market_share`, and `spending_power`. The calculator also determines the `saturation_cost` that will be applied to the market.
7.  After calculating revenue from all viewer groups, it calculates and applies **global penalties**:
    *   **Short Scene Penalty**: For scenes below a certain runtime.
    *   **Monotony Penalty**: For long scenes that lack conceptual variety.
    *   **Overstuffed Scene Penalty**: For scenes that have too many unique concepts per minute.
8.  The calculator returns a `SceneRevenueResult` dataclass containing the final total revenue, a breakdown of interest per viewer group, details on revenue modifiers/penalties, and the market saturation updates to be applied.
9.  The calling service uses this result to update the player's money and the market state.

## Calculation Flow (Talent Shoot Outcomes)

This is a backend-only flow that occurs as part of the `shoot_scene` process. It determines the impact of a shoot on the participating talent.

1.  `SceneProcessingService.run_shoot_calculations` is called for a given scene.
2.  It gathers all necessary data: the `Scene` dataclass, a list of all participating `Talent` dataclasses, active studio policies, and a `bloc_context` dictionary containing information about the shooting environment (e.g., `craft_services_efficiency`).
3.  It calls `ShootResultsCalculator.calculate_talent_outcomes()` with this data.
4.  The calculator first determines the total `stamina_cost` for each talent. This is done by iterating through the scene's (expanded) action segments and summing the costs for each role the talent performs, which are provided by the `RolePerformanceCalculator`.
5.  Then, for each talent, it calculates a series of outcomes:
    *   **Fatigue**: If the `stamina_cost` exceeds the talent's maximum stamina pool, a proportional fatigue gain is calculated.
    *   **Skill Gains**: Gains for Performance, Acting, and Stamina are calculated based on scene runtime, with diminishing returns for higher skill levels.
    *   **D/S Skill Gains**: If the scene has a Dom/Sub dynamic, gains are calculated based on the scene's focus, the talent's disposition (e.g., "Dom", "Sub"), and a disposition-based multiplier.
    *   **Experience Gain**: Calculated based on scene runtime, also with diminishing returns.
    *   **Stress & Burnout**: The calculator delegates to `StressCalculator` to determine stress gain. If the new total stress exceeds a threshold, a portion of the excess is converted into `burnout_gain`.
6.  The calculator returns a list of `TalentShootOutcome` DTOs, one for each talent, containing all the calculated results.
7.  `SceneProcessingService` then uses this DTO to build its own `ShootCalculationResult` DTO, which it passes to its caller, `SceneCommandService`.

## Validation Flow (Fatigue Estimation)

This is a "what-if" backend flow used to validate a potential role booking for a talent before it is confirmed. It is used to prevent booking a talent into a role that would immediately cause them to exceed their fatigue refusal threshold.

1.  During bulk hiring (`BulkBookingValidator`) or when finding eligible roles (`TalentQueryService`), the system needs to check the potential fatigue impact of a role.
2.  The calling service (e.g., `BulkBookingValidator.try_book_role()`) calls `ShootResultsCalculator.estimate_fatigue_gain()`.
3.  It passes the `Talent` (or `TalentDB`), the `Scene`, and the specific `vp_id` of the role being considered.
4.  `estimate_fatigue_gain` calculates the `stamina_cost` for that single role by calling its internal `_calculate_stamina_cost_for_role` helper. It does **not** consider the talent's current fatigue level.
5.  It compares this `stamina_cost` to the talent's maximum stamina pool (their `stamina` skill multiplied by a config value).
6.  If the cost exceeds the pool, it calculates a proportional `fatigue_gain` (an integer from 0-100) based on the size of the "overdraw".
7.  This estimated integer gain is returned to the calling service.
8.  The caller then adds this estimate to the talent's *current* fatigue to get a `projected_fatigue`, which it can then check against the `fatigue_refusal_threshold` from the game configuration.

## Request Flow (Email System)

This flow covers both the creation of emails by backend services and the player's interaction with them through the UI.

### 1. Email Creation (Backend)

This is a backend-only flow triggered by various game events (e.g., releasing a scene, a talent booking a tour).

1.  A command service (e.g., `SceneCommandService`, `TourCommandService`) performs an action that needs to notify the player.
2.  The service calls a dedicated convenience method on `EmailService` (e.g., `create_market_discovery_email()`, `create_tour_booking_email()`). This call is made within the service's active database transaction.
3.  The convenience method gathers and formats all the necessary variables for the email template.
4.  It calls the core `create_email_from_template()` method, providing the `template_key` (e.g., `"market_discovery"`) and the variables dictionary.
5.  `EmailService` looks up the `template_key` in `data/emails.json` to get the subject line and the HTML template filename.
6.  It uses the `DataManager`'s Jinja2 environment to render the subject and the body, substituting the variables.
7.  A new `EmailMessageDB` object is created with the rendered content and saved to the database.
8.  The calling service commits its transaction. If the service also emits `signals.emails_changed`, the UI will be notified.

### 2. Email Interaction (UI)

This flow describes how the user reads and manages emails.

1.  User opens the `EmailDialog` from the main UI.
2.  The `EmailPresenter`, upon view initialization (or via the `emails_changed` signal), calls `controller.get_all_emails()` to fetch all `EmailMessageDB` objects.
3.  The presenter creates a cache of these objects and formats them into a list of `EmailListItemViewModel`s.
4.  The view (`EmailDialog`) is updated with this list. The currently selected email is shown in the content pane.
5.  **Marking as Read**: When the user selects an unread email, `EmailPresenter.on_email_selected()` is triggered. It sees the email is unread and calls `controller.mark_email_as_read(email_id)`.
    - The `GameController` delegates this to `EmailService.mark_email_as_read()`.
    - The service updates the `is_read` flag in the database and emits `signals.emails_changed`.
    - The presenter's `load_initial_data` slot, connected to the signal, re-runs, and the view is updated to show the email with non-bold text.
6.  **Deleting**: The user selects one or more emails and clicks "Delete".
    - `EmailDialog` emits `delete_requested` with a list of email IDs.
    - `EmailPresenter` receives this, shows a confirmation box, and on "Yes", calls `controller.delete_emails(email_ids)`.
    - `GameController` delegates to `EmailService.delete_emails()`.
    - The service deletes the records from the database and emits `signals.emails_changed`, which triggers a view refresh.

## Validation Flow (Talent Availability)

This backend flow is the core "will they do it?" check for a talent. It is used in two primary ways: to find roles for a talent, and to find talent for a role. It is orchestrated by the `TalentQueryService` and executed by the `TalentAvailabilityChecker`.

### Flow 1: Finding Available Roles for a Talent (Annotation)

This flow is used in the `TalentProfilePresenter` to populate the "Available Roles" list in the `HiringWidget`. It checks every open role and *annotates* it with the talent's availability.

1.  The `TalentProfilePresenter.refresh_available_roles()` method is called.
2.  It calls `controller.find_available_roles_for_talent(talent_id)`.
3.  The `GameController` delegates this to `TalentQueryService.find_available_roles_for_talent()`.
4.  The `TalentQueryService` fetches all uncast scenes (`status='casting'`).
5.  For each potential role (`vp_id`) in each scene that matches the talent's basic attributes (e.g., gender):
    *   It fetches all required context: the talent's bookings for the surrounding weeks, the shooting bloc (for budget checks), and active studio policies.
    *   It pre-calculates the `estimated_fatigue_gain` for the role using `ShootResultsCalculator`.
    *   It calls `TalentAvailabilityChecker.check()` with the talent, scene, role, and all contextual data.
    *   The `TalentAvailabilityChecker` runs its full sequence of checks (schedule, fatigue, hard limits, preferences, contracts, budget, etc.).
6.  The `TalentQueryService` receives an `AvailabilityResult` for each potential role.
7.  It creates a list of dictionaries, each containing the role info, cost, and crucially, the `is_available` status and `refusal_reason` from the result.
8.  This annotated list is returned to the `TalentProfilePresenter`, which pushes it to the `HiringWidget`. The widget then displays all roles, graying out the unavailable ones and showing the refusal reason in the string.

### Flow 2: Finding Eligible Talent for a Role (Filtering)

This flow is used in the `TalentTabPresenter` when in "Casting Mode". It is used to find all talent who are available for a *single, specific role*, acting as a hard filter.

1.  The `TalentTabPresenter.on_filters_changed()` method detects it is in casting mode (a `scene_id` and `vp_id` are set).
2.  It calls `controller.get_eligible_talent_for_role(scene_id, vp_id, attribute_filters)`.
3.  The `GameController` delegates to `TalentQueryService.get_eligible_talent_for_role()`.
4.  The `TalentQueryService` first performs a pre-filter on the database to find all talents who match the role's hard requirements (gender, ethnicity) and any user-supplied filters.
5.  For each of these `potential_candidates_db`:
    *   It gathers the same context as in Flow 1 (bookings, bloc, policies).
    *   It estimates fatigue via `ShootResultsCalculator.estimate_fatigue_gain()`.
    *   It calls `TalentAvailabilityChecker.check()` with the candidate talent and the role context.
6.  **Crucially, it only proceeds if `result.is_available` is `True`**. If the checker returns `False`, the candidate is discarded.
7.  A list containing only the `TalentDB` objects that passed the availability check is returned to the `TalentTabPresenter`.
8.  The presenter updates the talent table view, showing only the fully eligible and willing candidates.
