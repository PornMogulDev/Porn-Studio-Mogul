# Time System Refactoring Overview

This document provides an overview of the recent refactoring of the game's time-handling system. The primary goal of this refactoring was to centralize the complex and error-prone time calculations by moving from a `(week, year)` tuple representation to a single `absolute_week` integer.

## Summary of Changes

The previous system involved manual calculations like `year * 52 + week` scattered across numerous services, calculators, and UI components. This was difficult to maintain and prone to bugs. The new system uses a single integer, the `absolute_week`, as the authoritative source of time for all game logic.

The core changes include:

1.  **New Time Utility**: A new module `src/utils/time_utils.py` was created to handle all conversions between `absolute_week` and the display-friendly `(year, week)` format.
2.  **Data Layer Refactoring**: All database models in `src/database/db_models.py` and data classes in `src/data/game_state.py` that previously stored `week` and `year` have been updated to use a single `*_absolute_week` integer field.
3.  **Service Layer Overhaul**: Key services were refactored to natively use `absolute_week`, simplifying their logic considerably. This includes `TimeService`, `TourCommandService`, `TalentQueryService`, `ContractCommandService`, and many others.
4.  **Controller Update**: The main `GameController` was updated to manage its internal state using `absolute_week` and to correctly drive the application logic and UI signals based on the new system.

---

## Potential Issues & Risks

This was a large-scale, cross-cutting refactoring. While it addresses the core architectural issue, the sheer number of modified files introduces risks. Thorough testing is highly recommended.

### 1. Immediate Time-Related Issues

*   **Database Migration**: The refactoring changes the database schema. I have implemented a simple, on-the-fly migration for the main game clock in `TimeService` (it will automatically convert the `week` and `year` in the `game_info` table to `absolute_week`). **However, this migration does not cover other tables like `scenes`, `tours`, etc.** Existing save files will be incompatible without a proper database migration strategy. You will need to either update your database manually or use a migration tool like Alembic to update the schema and data for existing saves.
*   **Off-by-One Errors**: Calculations involving dates are sensitive to 0-indexed vs. 1-indexed assumptions. While I have been careful to consistently use a 1-based `absolute_week`, an error in this logic could cause events to trigger a week early or late.
*   **Date Display**: UI components like the schedule and top bar still expect `(week, year)`. The conversion back to this format happens at the last moment before the signal is emitted. Any error in this conversion could lead to incorrect dates being displayed to the user.

### 2. Side Effects of Widespread Changes

*   **Broken Dependencies**: Although I have followed the dependency chain carefully, it is possible that I missed an indirect call to a refactored method in a part of the UI or logic that was not immediately obvious. This could lead to runtime errors.
*   **Incorrect Method Signatures**: Some methods had their signatures changed (e.g., from taking `week, year` to `absolute_week`). If a call to one of these methods was missed, it will raise a `TypeError` at runtime.
*   **Merge Conflicts**: Given that over a dozen files were modified, this branch will have significant merge conflicts with any other branches that have modified the same files. Careful merging will be required.
*   **Inadvertent Logic Changes**: While aiming to only change the time-handling mechanism, it's possible that some business logic was unintentionally altered. For example, a condition that was previously `year > X` might not have been perfectly translated to its `absolute_week` equivalent in all cases.

---

## Recommendations for Testing

To ensure the stability of the application after this refactoring, I recommend the following testing strategy:

1.  **Database & Save/Load**:
    *   Start a **new game** to ensure the database is created correctly with the new schema.
    *   Test saving the game, closing the application, and loading it again.
    *   Test the "Continue Game" and "Quick Save/Load" functionalities.

2.  **Core Time-Dependent Features**:
    *   **Scheduling**: Plan scenes and shooting blocs in different weeks and years. Verify they appear correctly on the schedule.
    *   **Tours**: Sponsor tours and observe autonomous tours. Check that they start and end on the correct weeks and that cooldown periods are respected.
    *   **Contracts**: Sign contracts and verify their duration is handled correctly across week/year boundaries.
    *   **Weekly Advancement**: Advance the week multiple times, paying close attention to the week 52 -> week 1 rollover.

3.  **UI Verification**:
    *   Check the `TopBarWidget` to ensure the week and year display correctly after each advancement.
    *   Check the `ScheduleTab` to ensure the year selector works and the schedule is displayed for the correct year.

By focusing on these areas, you should be able to quickly identify and resolve any issues that may have been introduced during this refactoring.
