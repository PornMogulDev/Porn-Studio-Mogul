# Email System Documentation

## Overview
The **Email System** serves as the primary notification center for the player. It handles game events (e.g., market discoveries, tour confirmations, welcome messages) and presents them in an interactive "Inbox" UI.

The system is designed with a **Separation of Concerns** principle:
1.  **Content** is decoupled from logic using **Jinja2 templates**.
2.  **UI Logic** is handled by a Presenter with O(1) caching.
3.  **Interactivity** is provided via a custom "Smart Link" system that allows hovering and clicking on game entities (e.g., Talents) within the email body.

---

## Architecture

### 1. Data Layer (`DataManager`)
*   **Role**: Infrastructure configuration.
*   **Responsibility**:
    *   Loads metadata from `data/emails.json`.
    *   Initializes the **Jinja2 Environment** pointing to `data/email_templates/`.
    *   This ensures templates are compiled and ready for the service layer.

### 2. Service Layer (`EmailService`)
*   **Role**: Business Logic.
*   **Responsibility**:
    *   `create_email_from_template()`: Merges dictionary data with Jinja2 templates to generate HTML bodies and Subject lines.
    *   Manages Database operations (Create, Read status, Delete) on the `EmailMessageDB` model.
    *   Emits `signals.emails_changed` to notify the UI.

### 3. Presentation Layer (`EmailPresenter` & `EmailDialog`)
*   **Role**: User Interface.
*   **Responsibility**:
    *   **Presenter**: Fetches emails, caches them for performance, formats data into ViewModels, and handles user actions (delete, mark read).
    *   **View**: A "dumb" QDialog that displays lists and renders HTML.
    *   **SmartTextBrowser**: A subclassed `QTextBrowser` that intercepts specific HTML links to trigger tooltips.

---

## Adding a New Email Type

To add a new email notification to the game, follow these 3 steps:

### Step 1: Create the HTML Template
Create a new file in `data/email_templates/` (e.g., `new_event.html`).
You can use standard **Jinja2 syntax** (loops, variables, conditionals).

```html
<!-- data/email_templates/new_event.html -->
<p>Hello <b>{{ player_name }}</b>,</p>
<p>An event occurred regarding:</p>
<ul>
    {% for item in items %}
        <li>{{ item.name }} - Cost: ${{ item.cost }}</li>
    {% endfor %}
</ul>
```

### Step 2: Register in `emails.json`
Add an entry to `data/emails.json`. The key is the ID you will use in Python code.

```json
{
  "new_event_notification": {
    "subject": "Update regarding {{ event_type }}",
    "template": "new_event.html"
  }
}
```
*Note: The `subject` field also supports Jinja2 variable substitution.*

### Step 3: Trigger in Python
Inject `EmailService` into your command service and call `create_email_from_template`.

```python
# In YourCommandService.py

def trigger_event(self, session):
    variables = {
        "player_name": "Boss",
        "event_type": "Production Delay",
        "items": [
            {"name": "Camera Rental", "cost": 500},
            {"name": "Catering", "cost": 200}
        ]
    }
    
    self.email_service.create_email_from_template(
        session, 
        "new_event_notification", 
        variables
    )
```

---

## Smart Link System

The email body supports "Smart Links"—hyperlinks that interact with the game's Entity Card system (Tooltips and Profile Windows).

### Syntax
In your HTML templates, use the custom `talent:` protocol:

```html
<!-- Creates a link to Talent with ID 105 -->
<a href='talent:105'>Lexi Starr</a>
```

### Behavior
1.  **Hover**: The `SmartTextBrowser` detects the mouse over a `talent:` link and emits a signal to `TooltipManager`, which renders the floating `EntitySummaryCard`.
2.  **Alt + Click**: The browser detects the modifier key. Instead of following the link, it emits a signal to `UIManager` to open the full `TalentProfileWindow`.
3.  **Standard Click**: Ignored (prevents navigation errors).

---

## File Structure

| Path | Description |
| :--- | :--- |
| `data/emails.json` | Metadata registry mapping keys to subjects and template files. |
| `data/email_templates/*.html` | Jinja2 HTML templates. |
| `services/command/email_service.py` | Core logic for rendering and saving emails. |
| `ui/presenters/email_presenter.py` | UI logic, caching, and state management. |
| `ui/dialogs/email_dialog.py` | The visual dialog window. |
| `ui/widgets/entity_card/smart_text_browser.py` | Custom widget handling HTML link interaction. |

---

## Troubleshooting

### "Template not found" Error
*   Ensure the file exists in `data/email_templates/`.
*   Ensure `emails.json` references the exact filename (case-sensitive).

### "KeyError" during email creation
*   If your template uses `{{ variable_name }}`, you **must** pass that key in the `variables` dictionary in Python.
*   The system logs Jinja2 errors to the console/log file but prevents the game from crashing.

### Tooltips sticking on screen (Alt-Tab)
*   The `UIManager` listens for Application State changes. If the tooltip persists when the game loses focus, ensure `ui_manager._on_app_state_changed` is connected to `QApplication.instance().applicationStateChanged`.