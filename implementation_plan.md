# AI Studios - Basic Prototype Implementation Plan

## Overview

This plan outlines the implementation of a first, very basic prototype for AI-controlled Studios in the game. AI Studios will function as autonomous competitors that create and release scenes in parallel with the player's studio. The primary goal is to establish the minimum viable functionality for AI Studios to:

1. **Create scenes** based on simple decision-making logic
2. **Release scenes** and generate market activity
3. **Exist as entities** in the game world that the player can observe

This prototype will focus on the core scene creation and release loop, laying the foundation for future expansions such as hiring talent, reputation systems, and market competition dynamics.

## User Review Required

> [!IMPORTANT]
> **Market Impact Architecture Decision**
> 
> AI Studios will release scenes that impact market saturation, creating dynamic competition. The current market system (`MarketService`) tracks saturation per market group. We need to decide:
> 
> - Should AI studio scenes immediately saturate the market (simple approach)?
> - Should we track AI studio revenue separately for future analytics?
> - Should AI studios have visible "studio profiles" the player can inspect, or remain behind-the-scenes?
> 
> **Recommended approach for prototype**: AI studios create and release scenes that increase market saturation but don't generate visible revenue. Studio profiles can be deferred to a future iteration.

> [!IMPORTANT]
> **Talent Sharing Decision**
> 
> Should AI studios:
> - **Share the same talent pool** as the player (simple, creates competition for talent)?
> - **Have their own independent talent pool** (easier to implement, no conflicts)?
> 
> **Recommended approach for prototype**: Independent talent pool. AI studios reference talent by archetype/properties rather than specific Talent IDs, avoiding scheduling conflicts and simplifying implementation.

> [!IMPORTANT]
> **AI Studio Count and Generation**
> 
> - How many AI studios should exist initially? (Suggested: 3-5 for prototype)
> - Should they be generated at game start or added dynamically?
> - Should they have different "personalities" or behaviors? (Suggested: defer to future iteration)
> 
> **Recommended approach for prototype**: Generate 3 fixed AI studios at game start with identical behavior patterns.

---

## Proposed Changes

### Data Layer

#### [NEW] [ai_studio.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/data/ai_studio.py)

New dataclass to represent an AI-controlled studio:

```python
@dataclass_json
@dataclass
class AIStudio:
    id: int
    name: str
    location: str  # Base location like player studio
    money: int = 100000  # Simple resource tracking
    active: bool = True  # Can be disabled/retired
    
    # Simple behavior parameters for prototype
    scenes_per_month_target: int = 4  # How many scenes they aim to create
    preferred_market_groups: List[str] = field(default_factory=list)  # Target audiences
```

This will be added to `game_state.py` alongside the `StudioState` and `GameState` definitions.

#### [MODIFY] [game_state.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/data/game_state.py)

Add AI studios tracking to the main game state:

```python
@dataclass
class GameState:
    studio: StudioState    
    absolute_week: int = 1
    ai_studios: List[AIStudio] = field(default_factory=list)  # NEW
```

---

### Database Layer

#### [MODIFY] [db_models.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/database/db_models.py)

Add database model for AI Studios:

```python
class AIStudioDB(Base, DataclassMapper):
    __tablename__ = 'ai_studios'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    money = Column(Integer, default=100000)
    active = Column(Boolean, default=True)
    scenes_per_month_target = Column(Integer, default=4)
    preferred_market_groups = Column(JSON, default=list)
    
    dataclass_type = AIStudio
```

Also add a simple AI Scene tracking table to record what AI studios have created (for future analytics and player visibility):

```python
class AISceneDB(Base):
    __tablename__ = 'ai_scenes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ai_studio_id = Column(Integer, ForeignKey('ai_studios.id'), nullable=False)
    title = Column(String, nullable=False)
    created_absolute_week = Column(Integer, nullable=False)
    released_absolute_week = Column(Integer)
    
    # Simple scene properties for market impact
    target_market_group = Column(String, nullable=False)
    quality_score = Column(Float, default=50.0)  # 0-100 scale
    
    # Relationship
    studio = relationship('AIStudioDB', backref='scenes')
```

---

### Service Layer - Command Services

#### [NEW] [ai_studio_command_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/command/ai_studio_command_service.py)

Service to handle AI studio database operations:

- `create_ai_studio(name, location, behavior_params)` - Create new AI studio
- `create_ai_scene(studio_id, scene_params)` - Record an AI scene creation
- `release_ai_scene(scene_id)` - Mark AI scene as released
- `get_all_ai_studios()` - Retrieve all AI studios
- `get_ai_studio_scenes(studio_id, status_filter)` - Get scenes for a studio

This follows the same pattern as `SceneCommandService` and `TalentCommandService`.

---

### Service Layer - AI Decision Logic

#### [NEW] [ai_studio_director.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/ai/ai_studio_director.py)

Core AI decision-making service that determines what actions each AI studio should take. For the prototype, this will implement very simple logic:

**Weekly Decision Loop** (called by `TimeService`):
1. Check if studio should create a scene this week (based on `scenes_per_month_target` and random variation)
2. If yes, generate scene parameters:
   - Title (random from predefined list)
   - Target market group (from studio's preferred list)
   - Quality score (random 40-70 for prototype)
   - Production duration (fixed 2 weeks for prototype)
3. Schedule scene release (current_week + production_duration)
4. Return scene creation request

**Scene Release Handling**:
1. Check for scenes ready to release this week
2. Apply market saturation impact via `MarketService`
3. Mark scene as released

Methods:
- `process_weekly_ai_decisions(session, current_absolute_week)` - Main entry point
- `_should_create_scene(studio, current_week)` - Decision logic
- `_generate_scene_params(studio)` - Scene parameter generation
- `_process_scene_releases(session, current_week)` - Handle releases

---

### Service Layer - Integration

#### [MODIFY] [time_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/time_service.py)

Integrate AI studio weekly processing into the main game loop. Add to the `advance_week` method after player scene shooting but before talent updates:

```python
# After scene shooting (around line 107)
# --- Process AI Studio Actions ---
if self.ai_studio_director:
    self.ai_studio_director.process_weekly_ai_decisions(session, current_absolute_week)
```

Constructor will need new dependency: `ai_studio_director: AIStudioDirector`

---

### Service Layer - Service Container

#### [MODIFY] [service_container.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/core/service_container.py)

Register the new AI studio services in the dependency injection system:

1. Add to `__init__` and instance variables:
   - `ai_studio_command_service`
   - `ai_studio_director`

2. Add to `initialize_and_populate_services`:
   ```python
   # After other command services
   self.ai_studio_command_service = AIStudioCommandService(
       session_factory=self.session_factory,
       signals=signals,
       data_manager=data_manager
   )
   
   # After other high-level services
   self.ai_studio_director = AIStudioDirector(
       session_factory=self.session_factory,
       ai_studio_command_service=self.ai_studio_command_service,
       market_service=self.market_service,
       data_manager=data_manager
   )
   ```

3. Update `_populate_controller` to inject services into controller

4. Add to cleanup methods

---

### Core Layer

#### [MODIFY] [game_controller.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/core/game_controller.py)

Add AI studio services to the controller for UI access (if needed for future features):

1. Add instance variables in `__init__`:
   ```python
   self.ai_studio_command_service: Optional[AIStudioCommandService] = None
   self.ai_studio_director: Optional[AIStudioDirector] = None
   ```

2. Add getter methods (following existing patterns):
   ```python
   def get_all_ai_studios(self) -> List[AIStudio]:
       """Retrieve all AI studios for display/inspection."""
       if self.ai_studio_command_service:
           return self.ai_studio_command_service.get_all_ai_studios()
       return []
   ```

---

### Data Initialization

#### [MODIFY] [game_session_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/game_session_service.py)

Initialize AI studios when creating a new game. Add to the `start_new_game` method:

```python
# After creating initial talent pool
# --- Create Initial AI Studios ---
ai_studio_names = ["Studio Venus", "Passion Productions", "Crimson Films"]
ai_studio_locations = ["Los Angeles (US)", "Miami (US)", "Las Vegas (US)"]

for i, (name, location) in enumerate(zip(ai_studio_names, ai_studio_locations), start=1):
    ai_studio = AIStudio(
        id=i,
        name=name,
        location=location,
        money=100000,
        scenes_per_month_target=4,
        preferred_market_groups=["mainstream", "premium"]  # Simple default
    )
    game_state.ai_studios.append(ai_studio)
    
    # Persist to database
    session.add(AIStudioDB.from_dataclass(ai_studio))
```

---

### Configuration Data

#### [NEW] [ai_scene_names.json](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/data/ai_scene_names.json)

Simple JSON file with pre-generated scene titles for AI studios to use:

```json
{
  "generic_titles": [
    "Heat Wave",
    "Midnight Rendezvous",
    "Private Affairs",
    "Forbidden Desires",
    "Summer Passion",
    ["...50-100 more titles..."]
  ]
}
```

This file will be loaded by `AIStudioDirector` for random scene title generation.

---

## Verification Plan

### Automated Tests

1. **Data Layer Tests** (`tests/data/test_ai_studio.py`)
   - Test `AIStudio` dataclass serialization/deserialization
   - Test `AIStudioDB` database model CRUD operations

2. **Service Layer Tests** (`tests/services/test_ai_studio_director.py`)
   - Test scene creation decision logic
   - Test scene parameter generation
   - Test scene release processing
   - Mock database interactions

3. **Integration Tests** (`tests/integration/test_ai_studios_weekly_cycle.py`)
   - Create a game session with AI studios
   - Advance several weeks
   - Verify AI scenes are created and released
   - Verify market saturation is affected

### Manual Verification

1. **New Game Creation**
   - Start a new game
   - Verify 3 AI studios are created in the database
   - Check that each has appropriate initial values

2. **Weekly Advancement Observation**
   - Advance 10-20 weeks in-game
   - Query the `ai_scenes` database table
   - Verify scenes are being created sporadically (not every week for every studio)
   - Verify scenes have `released_absolute_week` set correctly (created_week + 2)

3. **Market Impact**
   - Check market saturation values before advancing weeks
   - Advance several weeks to allow AI scene releases
   - Verify market saturation increases from AI activity
   - Compare saturation with and without AI studios active

4. **Database Inspection**
   ```sql
   SELECT * FROM ai_studios;
   SELECT * FROM ai_scenes ORDER BY created_absolute_week;
   ```

5. **No Player Impact** (Critical for prototype)
   - Ensure player scene creation/shooting is unaffected
   - Ensure no crashes or errors during week advancement
   - Ensure player talent pool is unaffected (no conflicts)

---

## Future Enhancements (Out of Scope for Prototype)

The following features are intentionally deferred to future iterations:

- **Talent Competition**: AI studios hiring from shared talent pool
- **Reputation System**: AI studio reputation and market share tracking
- **Financial Impact**: AI studios affecting scene revenue/market prices
- **Studio Profiles UI**: Player-visible information about AI studios and their scenes
- **Differentiated Behavior**: Different AI "personalities" or strategies
- **Dynamic Studio Entry/Exit**: Studios opening/closing based on market conditions
- **AI Studio Relationships**: Rivalry, partnerships, etc.
- **Player Interactions**: Buying AI studios, poaching talent, etc.

These can be built incrementally on top of this foundation.
