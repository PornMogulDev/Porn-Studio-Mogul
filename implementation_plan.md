# Implementation Plan: Email Refactoring & Smart Entity Linking

This plan addresses three goals:
1.  **Refactor** the email service to eliminate hardcoded email content by using JSON-based templates.
2.  **Add** tour booking notifications when talents from the `go_to_list` are booked.
3.  **Enhance** the Email UI to support "Smart Links" (Alt-Click to open profile, Hover for summary card) within the email body.

## 1. Data Configuration

### [NEW] `data/email_templates.json`

Create a JSON file to store email templates.
*   **Change:** Use HTML tags to format text.
*   **New Convention:** Use `<a>` tags with a specific schema (e.g., `talent:ID`) to denote interactive entities.

```json
{
  "welcome": {
    "subject": "Welcome to the Studio!",
    "body": "<p>Welcome to your new studio! Your goal is to become a successful producer.</p><p>Design scenes, cast talent, and make a profit!</p>"
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
    "body": "<p>Your sponsored tour for <b><a href='talent:{talent_id}'>{talent_name}</a></b> has been confirmed!</p><p><b>Destination:</b> {destination}</p><p><b>Duration:</b> {duration} weeks</p><p>They will be available for casting in {destination} during this period.</p>"
  },
  "tour_booked_autonomous": {
    "subject": "Tour Update: {talent_name}",
    "body": "<p><b><a href='talent:{talent_id}'>{talent_name}</a></b> from your Go-To List has booked a tour!</p><p><b>Destination:</b> {destination}</p><p><b>Start Date:</b> Week {start_week}</p>"
  },
  "tour_booked_ai_sponsored": {
    "subject": "Tour Update: {talent_name}",
    "body": "<p><b><a href='talent:{talent_id}'>{talent_name}</a></b> from your Go-To List has been sponsored for a tour by <b>{ai_studio_name}</b>!</p>"
  }
}
```

## 2. Core Services

### [MODIFY] `src/services/command/email_service.py`

*   **Dependency:** Inject `DataManager` to access `email_templates.json`.
*   **Method:** Add `create_email_from_template(session, template_key, variables, ...)`
    *   This method loads the JSON template.
    *   It performs generic string substitution (e.g., `{talent_name}`, `{talent_id}`).
*   **Method:** Add `create_tour_booking_email(...)`.
    *   Prepares the variables (including extracting `talent.id` for the smart link).
    *   Calls `create_email_from_template`.

### [MODIFY] `src/services/command/tour_command_service.py`

*   **Logic:**
    *   In `sponsor_tour` and `process_autonomous_tour_decisions`:
    *   Check `GameQueryService` to see if the talent is in a `go_to_list`.
    *   If yes, call `EmailService.create_tour_booking_email`.
    *   *Constraint:* Ensure `talent_id` is passed to the email service to populate the `<a>` tag.

### [MODIFY] `src/services/game_session_service.py`

*   Refactor `start_new_game` to use `EmailService.create_email_from_template` for the welcome email instead of hardcoding text.

## 3. UI Implementation (Smart Links)

### [NEW] `src/ui/widgets/smart_text_browser.py`

Create a specialized text widget to replace the standard `QTextEdit` in the Email Dialog. This adapts the logic found in `LinkHoverDelegate`.

*   **Inherits:** `QTextBrowser` (provides better HTML/Link support than `QTextEdit`).
*   **Signals:**
    *   `link_hover_entered(int, QPoint)`: Emits ID and global mouse position.
    *   `link_hover_left()`: Emits when mouse leaves a link.
    *   `link_alt_clicked(int)`: Emits ID when Alt+Clicked.
*   **Implementation Details:**
    *   Set `setOpenExternalLinks(False)` to prevent opening the browser.
    *   Override `mouseMoveEvent`: Use `self.anchorAt(event.pos())`. If the anchor string starts with `talent:`, parse the ID and emit `link_hover_entered`.
    *   Override `mousePressEvent`: Check for `Qt.AltModifier`. If true and clicking an anchor, emit `link_alt_clicked`.

### [MODIFY] `src/ui/dialogs/email_dialog.py`

*   **Imports:** Import the new `SmartTextBrowser`.
*   **UI Setup:** Replace `self.body_text = QTextEdit()` with `self.body_text = SmartTextBrowser()`.
*   **Signals:**
    *   Expose the browser's signals at the Dialog level (e.g., define `smart_link_hovered` signal in `EmailDialog`).
    *   Connect `self.body_text` signals to these dialog-level signals.

### [MODIFY] `src/ui/ui_manager.py`

*   **Method:** `show_inbox()`
*   **Wiring:**
    *   When creating `EmailDialog`, connect its new signals to the `TooltipManager` and `TalentProfile` logic.
    *   *Example Pattern:*
        ```python
        # inside show_inbox factory
        dialog.smart_link_hovered.connect(self.show_talent_summary)
        dialog.smart_link_left.connect(self.hide_talent_summary)
        dialog.smart_link_clicked.connect(self.show_talent_profile_by_id)
        ```

## 4. Dependency Injection

### [MODIFY] `src/core/game_controller.py`

*   Update initialization of `EmailService` to include `DataManager`.
*   Update `TourCommandService` to include `EmailService`.

## 5. Verification Plan

1.  **Test Template Loading:**
    *   Start a new game. Verify the Welcome Email loads with correct text.
2.  **Test Variable Substitution:**
    *   Force a Tour Event (or use debug tools).
    *   Verify the email contains the Talent's name and that the name is styled as a link (blue/underlined usually, or per theme).
3.  **Test Smart Interactions:**
    *   **Hover:** Move mouse over the talent name in the email. Verify `EntitySummaryCard` appears at the correct position. Move mouse away; verify it disappears.
    *   **Alt+Click:** Hold Alt and Click the name. Verify `TalentProfileWindow` opens for that specific talent.
    *   **Normal Click:** Verify clicking without Alt does nothing (or follows standard behavior if we decide to allow simple clicks later).
4.  **Test Go-To-List Logic:**
    *   Sponsor a tour for a talent *not* in the list -> No Email.
    *   Add talent to list -> Sponsor tour -> Receive Email.