# Service Layer Architecture Guide

## 1. Executive Summary

This document outlines the architectural principles and structure of the application's service layer. Following a major refactoring, the layer has been organized to strictly adhere to established design patterns to maximize **maintainability**, **testability**, and **readability**.

The core philosophy is a clear **Separation of Concerns**. The architecture is designed to make the role and responsibility of every class immediately obvious from its location and name. This guide serves as the map to that structure, explaining where new code should go and why.

---

## 2. Core Architectural Principles

Our service layer is built upon the following foundational principles:

1.  **Controller as a Façade:** The `GameController` is the single entry point from the UI. Its methods are lean, performing no business logic. Their only job is to delegate calls to the appropriate service(s) and return the result.

2.  **Dependency Injection & Composition Root:** Services do not create their own dependencies. The `ServiceContainer` acts as the application's **Composition Root**. It is the *only* place responsible for instantiating services and their configurations, and injecting them where they are needed.

3.  **Single Responsibility Principle (SRP):** Every class has one, and only one, reason to change. A service that calculates revenue should not also be responsible for updating the market. This is the primary driver for our directory structure.

4.  **CQRS (Command Query Responsibility Segregation):** The architecture strictly separates operations that change state (Commands) from operations that read state (Queries). This is reflected in our `/command` and `/query` directories.

5.  **Orchestrator vs. Executor:** Complex, multi-step business processes (like `advance_week`) are managed by an **Orchestrator** (`TimeService`), which calls multiple fine-grained **Executors** (`SceneCommandService`, `MarketService`, etc.) to perform the actual work.

---

## 3. The New Service Layer Structure

The following structure is not just a set of folders; it is a physical representation of our architectural rules.

services/
│ # General, cross-cutting services
│ email_service.py
│ game_session_service.py
│ market_service.py
│ ...
│
├───builders/
│ # Stateful classes for constructing complex objects
│ scene_state_editor.py
│
├───calculation/
│ # Stateless, pure business logic calculators
│ revenue_calculator.py
│ talent_demand_calculator.py
│ ...
│
├───command/
│ # Services that WRITE or MODIFY game state
│ scene_command_service.py
│ talent_command_service.py
│ ...
│
├───events/
│ # Services for the event-driven subsystem
│ scene_event_trigger_service.py
│ scene_event_command_service.py
│
├───models/
│ # Data Transfer Objects (DTOs): Configs and Results
│ configs.py
│ results.py
│
└───query/
# Services that READ and FETCH game data
game_query_service.py
talent_query_service.py
...

---

## 4. Roles and Responsibilities of Each Directory

### `/` (Root Services)

*   **Role:** These are general-purpose services that encapsulate a broad domain but may involve both read and write operations internally.
*   **Example:** `MarketService` is responsible for the entire "market" domain, which includes updating saturation (a command) and checking for discoveries (could be a query). It acts as a Façade for its specific domain.
*   **When to use:** Use for a major domain that doesn't fit neatly into a pure Command or Query service.

### `/builders`

*   **Role:** To encapsulate the logic for constructing a complex object step-by-step. Unlike calculators, builders are **stateful**.
*   **Example:** `SceneStateEditor` holds the state of a `Scene` as a user adds VPs, sets roles, and validates the configuration in the scene planner UI.
*   **When to use:** When you have a multi-step creation process for an object that requires validation at each step before the final object is created.

### `/calculation`

*   **Role:** To house pure, **stateless** business logic. Calculators take data, perform calculations, and return a result. They have **no side effects** and **never write to the database**.
*   **Example:** `RevenueCalculator` takes scene data and returns a `RevenueResult`. It doesn't know or care how that result is used or saved.
*   **When to use:** For any complex business rule, formula, or algorithm. This makes the logic extremely easy to test in isolation.

### `/command`

*   **Role:** The "C" in CQRS. These services are solely responsible for **changing the state of the application**. They perform all `create`, `update`, and `delete` operations.
*   **Example:** `SceneCommandService` handles actions like creating a scene, casting talent, and releasing the final product.
*   **Key Pattern:** These services are the primary users of the transaction patterns defined in `SESSION_AND_TRANSACTION_MANAGEMENT.md`.

### `/events`

*   **Role:** Manages the logic for the game's interactive event system.
*   **Example:** `SceneEventTriggerService` (a query-like service) checks if an event should happen. `SceneEventCommandService` (a command service) resolves the outcome of the player's choice.
*   **When to use:** For any logic related to triggering and resolving dynamic game events.

### `/models`

*   **Role:** To define the data structures that services use to communicate. These are our Data Transfer Objects (DTOs).
*   **`configs.py`:** Contains dataclasses used to pass configuration into services (e.g., `HiringConfig`).
*   **`results.py`:** Contains dataclasses used to return complex results from services (e.g., `ShootCalculationResult`, `EventResolutionResult`).
*   **Why they are critical:** DTOs are the contracts that decouple our services. A command service returns a `Result` DTO instead of calling another service directly, allowing the `GameController` to orchestrate the next step.

### `/query`

*   **Role:** The "Q" in CQRS. These services are **read-only**. Their job is to fetch data from the database, convert it into convenient dataclasses, and return it, typically for UI display.
*   **Example:** `TalentQueryService` finds available talent. `TagQueryService` provides tags for the UI.
*   **Key Pattern:** Query services always use the short-lived, "session-per-query" pattern with eager loading to prevent `DetachedInstanceError`. (See `SESSION_AND_TRANSACTION_MANAGEMENT.md`).

---

## 5. A Practical Example: The `advance_week` Flow

This flow demonstrates how the different components collaborate:

1.  **UI Action:** User clicks the "Advance Week" button.
2.  **Façade (`GameController`):** The `advance_week()` method is called. It does nothing but call `self.time_service.advance_week()`.
3.  **Orchestrator (`TimeService`):** The `advance_week()` method starts. It creates a **single database session** that will live for the entire process.
4.  **Executor (`SceneCommandService`):** `TimeService` calls `scene_command_service.process_weekly_shoots(session)`. The command service iterates through scenes to be shot.
5.  **Sub-Executor (`SceneProcessingService`):** `SceneCommandService` calls `scene_processing_service.run_shoot_calculations(session, ...)`.
6.  **Calculator (`ShootResultsCalculator`, etc.):** `SceneProcessingService` calls multiple calculators, passing them data. They return pure results with no side effects.
7.  **DTO (`ShootCalculationResult`):** The results are collected into this DTO.
8.  **Executor (`SceneProcessingService`):** The service now calls `apply_shoot_calculation_results(session, result_dto)` to write all the changes to the database.
9.  **Orchestrator (`TimeService`):** Control returns to `TimeService`, which proceeds to call other services (`MarketService`, `TalentCommandService`), all using the **same session**.
10. **Commit:** Once all steps are successful, `TimeService` calls `session.commit()`. If any step failed, it would call `session.rollback()`. The entire week advancement is atomic.
11. **Façade (`GameController`):** Control returns to the controller, which then updates the UI.

This entire process is now clear, traceable, and composed of small, testable, single-responsibility components.