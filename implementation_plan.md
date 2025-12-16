# Email Service Refactoring and Tour Booking Notifications

This plan addresses two goals:
1. Refactor the email service to eliminate hardcoded email content by using JSON-based templates
2. Add email notifications when talents from the player's go_to_list are booked for tours

## Background

Currently, email content is hardcoded in three locations:
- [`EmailService.create_market_discovery_email`](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/command/email_service.py#L64-L80) - Creates HTML-formatted market discovery emails
- [`GameSessionService.start_new_game`](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/game_session_service.py#L82-L89) - Creates welcome email with hardcoded text
- [`MarketService.process_discoveries_from_release`](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/market_service.py#L67-L110) - Handles discovery logic that feeds into email creation

The go_to_list is a feature that allows players to track their favorite talents across categories. The system uses:
- `GoToListCategoryDB` - Categories for organizing talents
- `GoToListAssignmentDB` - Many-to-many relationship between talents and categories
- Signals (`go_to_list_changed`) - For UI updates

Tour bookings happen in two ways:
- **Player-sponsored**: [`TourCommandService.sponsor_tour`](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/command/tour_command_service.py#L38-L105) - Player pays upfront to sponsor a tour
- **Autonomous**: [`TourCommandService.process_autonomous_tour_decisions`](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/command/tour_command_service.py#L107-L172) - Talents decide to tour on their own

## Proposed Changes

### Data Configuration

#### [NEW] [email_templates.json](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/data/email_templates.json)

Create a new JSON file to store all email templates with support for variable substitution:

```json
{
  "welcome": {
    "subject": "Welcome to the Studio!",
    "body": "<p>Welcome to your new studio! Your goal is to become a successful producer.</p><p>Design scenes, cast talent, and make a profit!</p><p>Good luck!</p>"
  },
  "market_discovery": {
    "subject": "Market Research Results: '{scene_title}'",
    "body_header": "<p>Our analysis of the release of your recent scene has yielded new market insights.</p>",
    "body_group": "<p><b>{group_name}:</b></p>",
    "body_tag_item": "<li>Discovered preference for '<b>{tag}</b>'</li>",
    "body_footer": "<p>This information has been added to our market intelligence reports.</p>"
  },
  "tour_booked_player_sponsored": {
    "subject": "Tour Booking Confirmation: {talent_name}",
    "body": "<p>Your sponsored tour for <b>{talent_name}</b> has been confirmed!</p><p><b>Destination:</b> {destination}</p><p><b>Duration:</b> {duration} weeks</p><p><b>Start Date:</b> Week {start_week}</p><p>They will be available for casting in {destination} during this period.</p>"
  },
  "tour_booked_autonomous": {
    "subject": "Tour Update: {talent_name}",
    "body": "<p><b>{talent_name}</b> from your Go-To List has booked a tour!</p><p><b>Destination:</b> {destination}</p><p><b>Duration:</b> {duration} weeks</p><p><b>Start Date:</b> Week {start_week}</p><p>They decided to travel on their own to explore new opportunities. You can still cast them in {destination} during this time.</p>"
  },
  "tour_booked_ai_sponsored": {
    "subject": "Tour Update: {talent_name}",
    "body": "<p><b>{talent_name}</b> from your Go-To List has been sponsored for a tour by <b>{ai_studio_name}</b>!</p><p><b>Destination:</b> {destination}</p><p><b>Duration:</b> {duration} weeks</p><p><b>Start Date:</b> Week {start_week}</p><p>You can still cast them in {destination} during this time if needed.</p>"
  }
}
```

---

### Core Services

#### [MODIFY] [email_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/command/email_service.py)

**Changes:**
1. Add `DataManager` dependency to access email templates
2. Add new generic `create_email_from_template` method that loads templates and performs variable substitution
3. Refactor `create_market_discovery_email` to use the new template system
4. Add new `create_tour_booking_email` method for tour notifications
5. Keep the internal `_create_email` helper method unchanged

**Key additions:**
```python
def create_email_from_template(self, session, template_key: str, variables: dict, current_absolute_week: int):
    """Creates an email using a template from email_templates.json"""
    
def create_tour_booking_email(self, session, talent_name: str, tour_details: dict, 
                              sponsor_type: str, current_absolute_week: int, 
                              ai_studio_name: str = None):
    """Creates notification email for when a go_to_list talent books a tour"""
```

---

#### [MODIFY] [market_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/market_service.py)

**Changes:**
1. No changes needed to the core logic
2. The `EmailService.create_market_discovery_email` method signature remains the same
3. Email content generation moves to templates, but the method interface is unchanged

---

#### [MODIFY] [game_session_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/game_session_service.py)

**Changes:**
1. Replace hardcoded welcome email in `start_new_game` with template-based approach
2. Call `EmailService.create_email_from_template` instead of manually creating `EmailMessageDB`

**Before:**
```python
welcome_email = EmailMessageDB(
    subject="Welcome to the Studio!",
    body="Welcome to your new studio!...",
    absolute_week=game_state.absolute_week,
    is_read=False
)
session.add(welcome_email)
```

**After:**
```python
email_service.create_email_from_template(
    session, 'welcome', {}, game_state.absolute_week
)
```

---

#### [MODIFY] [tour_command_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/command/tour_command_service.py)

**Changes:**
1. Add `EmailService` and `GameQueryService` (for go_to_list lookups) as dependencies
2. In `sponsor_tour`: Check if talent is in any go_to_list category, create email if so
3. In `process_autonomous_tour_decisions`: Check each touring talent against go_to_list, create email if matched

**Key integration points:**

In `sponsor_tour` (after tour creation, before commit):
```python
# Check if talent is in go_to_list
talent_categories = self.game_query_service.get_talent_categories(talent_id)
if talent_categories:
    # Create tour booking email
    self.email_service.create_tour_booking_email(
        session, talent_db.alias, tour_details, 'player', current_absolute_week
    )
```

In `process_autonomous_tour_decisions` (inside the loop where tours are created):
```python
# After creating autonomous tour
talent_categories = self.game_query_service.get_talent_categories(talent_db.id)
if talent_categories:
    tour_details = {
        'destination_location': dest,
        'duration_weeks': duration,
        'start_absolute_week': start_absolute_week
    }
    self.email_service.create_tour_booking_email(
        session, talent_db.alias, tour_details, 'self', current_absolute_week
    )
```

---

### Dependency Injection Updates

#### [MODIFY] [game_controller.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/core/game_controller.py) *(likely location)*

**Changes:**
1. Update `EmailService` initialization to receive `DataManager` dependency
2. Update `TourCommandService` initialization to receive `EmailService` and `GameQueryService` (if not already present)
3. Update `GameSessionService` initialization to receive `EmailService` dependency

---

## Verification Plan

### Automated Tests

I'll verify the changes by:

1. **Start a new game** - Confirm welcome email uses template
   ```
   Check email inbox shows welcome email with proper formatting
   ```

2. **Trigger market discovery** - Release a scene and confirm discovery email uses template
   ```
   Create and release a scene
   Verify market discovery email appears with proper formatting
   ```

3. **Test tour notifications**:
   
   a. **Player-sponsored tour for go_to_list talent:**
   ```
   - Add a talent to go_to_list
   - Sponsor a tour for that talent
   - Verify tour booking email appears with correct details
   ```
   
   b. **Player-sponsored tour for non-go_to_list talent:**
   ```
   - Sponsor a tour for a talent NOT in go_to_list
   - Verify NO tour booking email is created
   ```
   
   c. **Autonomous tour for go_to_list talent:**
   ```
   - Add talents to go_to_list
   - Advance time to trigger autonomous tour decisions
   - Verify tour booking email appears when go_to_list talent books tour
   ```

4. **Verify template flexibility** - Edit `email_templates.json` and confirm changes appear in-game

### Manual Verification

- Visually inspect all email types in the game's email inbox
- Confirm HTML formatting renders correctly
- Verify variable substitution works properly (talent names, locations, dates)
- Test edge cases (empty discoveries, missing template variables)
