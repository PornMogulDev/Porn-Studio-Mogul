## Component Overview

| Module | Responsibility | Key Dependencies |
|---|---|---|
| `game_controller.py` | Acts as the central mediator, connecting the UI, game state, and service layer. | `ServiceContainer`, `GameSignals`, `GameState` |
| `game_signals.py` | Provides a centralized collection of Qt signals for decoupled communication between components. | `PyQt6.QtCore` |
| `interfaces.py` | Defines the `IGameController` protocol, ensuring a consistent contract for presenters and UI components. | `Protocol`, `GameSignals`, `DataManager` |
| `notifications_manager.py` | Manages the display and lifecycle of on-screen, temporary user notifications. | `IGameController`, `PyQt6` |
| `service_container.py` | Creates, configures, and manages the lifecycle of all services (Dependency Injection). | `DataManager`, `SaveManager`, `GameSignals` |
| `talent_generator.py` | Procedurally generates new talent characters with detailed attributes, skills, and preferences. | `data.game_state.Talent` |

## Service Layer Overview

| Module | Responsibility | Key Dependencies |
|---|---|---|
| `game_session_service.py` | Manages the game session lifecycle: new, save, load, and quit. | `SaveManager`, `DataManager`, `TalentGenerator` |
| `market_service.py` | Manages market dynamics, including saturation recovery and sentiment discovery. | `MarketGroupResolver`, `Session` |
| `player_settings_service.py` | Manages player-specific settings persisted in the database, like favorite tags. | `Session`, `GameSignals` |
| `time_service.py` | Orchestrates all weekly game state changes (shoots, post-pro, talent updates) in a single transaction. | `SceneCommandService`, `TalentCommandService`, `MarketService` |
| `tour_feasibility_service.py` | Pure logic class to check for tour schedule conflicts and determine accommodation needs for talent. | `DataManager`, `HiringConfig` |
| `tour_sponsorship_preview_service.py` | Orchestrates the gathering of all data needed to generate a preview for a tour sponsorship negotiation. | `GameQueryService`, `TourFeasibilityService`, `UpfrontTourCostCalculator` |

## Calculation Services Overview

| Module | Responsibility | Key Dependencies |
|---|---|---|
| `bloc_cost_calculator.py` | Calculates the authoritative cost for creating a shooting bloc based on settings and policies. | `DataManager` |
| `market_group_resolver.py` | Resolves inheritance for static market group data, merging parent and child preferences. | (None - Pure Logic) |
| `post_production_calculator.py` | Calculates the quality and revenue modifiers from post-production choices (e.g., editing). | `DataManager` |
| `revenue_calculator.py` | Calculates a scene's final revenue based on market interest, star power, and penalties. | `DataManager`, `SceneCalculationConfig` |
| `role_performance_calculator.py` | Calculates dynamic modifiers for stamina and hiring demand based on a talent's role in an action segment. | (None - Pure Logic) |
| `scene_quality_calculator.py` | Calculates a scene's pre-production quality from cast performance, chemistry, and production settings. | `DataManager`, `SceneCalculationConfig` |
| `shoot_results_calculator.py` | Calculates the outcomes for a talent after a shoot, including stamina cost, fatigue, and skill/exp gain. | `DataManager`, `SceneCalculationConfig`, `RolePerformanceCalculator` |
| `tag_validation_checker.py` | Validates manual physical tag assignments and auto-discovers tags based on cast composition. | `DataManager` |
| `talent_affinity_calculator.py` | Recalculates a talent's tag affinities based on their age, typically run once per year. | `SceneCalculationConfig` |
| `talent_availability_checker.py` | Runs a series of checks (schedule, fatigue, limits, preferences) to see if a talent will accept a role. | `DataManager`, `HiringConfig` |
| `talent_demand_calculator.py` | Calculates the authoritative hiring cost (demand) for talent, including bulk discounts and fees. | `DataManager`, `HiringConfig`, `RolePerformanceCalculator`, `TalentAvailabilityChecker` |
| `upfront_tour_cost_calculator.py` | Calculates the immediate upfront costs (travel + accommodation) for sponsoring a talent tour. | `DataManager` |

