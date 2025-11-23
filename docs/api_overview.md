
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

## Request Flow (Role Demand & Stamina Needs)

1. A higher-level service (like TalentDemandCalculator) needs a modifier for a performer (vp_id) in a specificActionSegment of a Scene.
2. It calls either get_role_demand_modifier() or get_role_stamina_modifier() on the RolePerformanceCalculator instance, passing in the segment, vp_id, scene, and the master tag_definitions dictionary.
3. The calculator first finds the performer's role (e.g., "Giver") by parsing the slot_id of their assignment in the segment.
4. It then looks up the definition for that role within the specific action tag's definition (e.g., the "Giver" slot in the "Blowjob (Straight)" tag definition). Validating against malformed strings.
5. Using this slot definition, it retrieves the base modifier (e.g., stamina_modifier) and any scaling factors (e.g., stamina_modifier_scaling_per_peer).
6. It checks the segment's parameters to see how many "peers" (performers in the same role) and "others" (performers in the opposing role) are involved.
7. It calculates a final modifier by adding the scaled bonuses to the base modifier.
8. This final float value is returned to the calling service (TalentDemandCalculator or ShootResultsCalculator), which uses it in its own higher-level calculations.
