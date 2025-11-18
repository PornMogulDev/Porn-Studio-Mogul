## Data Flow

The `GameController` orchestrates the primary gameplay loops by delegating to various services. The most critical flows are:

- **Game Loop (`advance_week`)**: The main heartbeat of the game. It triggers scene processing, market updates, and talent state changes via the `TimeService`. This is the central flow that moves the game forward.

- **Session Management (`new_game`, `load_game`, `save_game`)**: The `GameSessionService` handles the start, end, and persistence of a game session, managing the lifecycle of the game state and database session.

- **Scene Creation & Release (`create_shooting_bloc` -> `update_scene_full` -> `release_scene`)**: This represents the core creative loop. The player plans a `ShootingBloc`, defines the creative details of a `Scene`, casts talent, and finally releases it to the market, which triggers revenue and market discovery calculations.

- **Talent Hiring & Casting (`find_available_roles_for_talent` -> `calculate_bulk_hiring_costs` -> `cast_talent_for_multiple_roles`)**: This flow covers finding available roles for a talent, calculating the financial implications of hiring them for multiple scenes at once, and executing the casting. It involves complex calculations for travel, fees, and discounts.

- **Tour Sponsorship (`get_tour_sponsorship_preview` -> `sponsor_tour`)**: A specialized version of the hiring flow where the player sponsors a tour for a talent, which involves significant upfront costs but makes the talent available for a set of scenes.

- **Interactive Event Resolution (`resolve_interactive_event`)**: During a scene shoot, random events can occur. This flow handles player choices and their consequences, which can range from cancelling the scene to chaining into another event.
