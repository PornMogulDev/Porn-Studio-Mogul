# Presenter Lifecycle Management: Best Practices

## Overview

This document describes the presenter lifecycle issue discovered in the inbox unread email bug, the solutions implemented, and architectural recommendations for robust presenter cleanup across the entire application.

---

## The Problem: Stale Signal Connections

### What Happened

When dialogs are closed and reopened across different game sessions, presenter instances could remain connected to controller signals even after their associated views were closed. This caused stale presenters to react to signals from new game sessions, leading to incorrect state updates.

### The Inbox Bug Case Study

**Symptom:** After reading the welcome email in one game, returning to main menu, and starting a new game, the welcome email in the new game was already marked as read.

**Root Cause:**
1. `EmailDialog` and `EmailPresenter` created when user opens inbox
2. `EmailPresenter` connects to `controller.signals.emails_changed`
3. User reads email and returns to main menu
4. `close_all_dialogs()` closes the dialog, but widget destruction is **asynchronous**
5. User starts new game **before** the dialog is destroyed
6. Old `EmailPresenter` is still connected to `emails_changed`
7. Old presenter reacts to new game's signal and marks the new email as read

**Key Issue:** The `view.destroyed` signal fires asynchronously, after Qt's event loop processes the deletion. By the time it fires, the new game has already started, and the old presenter has already processed the signal.

---

## Solutions Implemented

### Solution A: Explicit Cleanup in close_all_dialogs()

**Location:** [ui_manager.py:514-540](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/managers/ui_manager.py#L514-L540)

Instead of relying on the `view.destroyed` signal, explicitly call `cleanup()` on presenters before closing dialogs:

```python
def close_all_dialogs(self):
    """Closes and clears all managed dialog instances."""
    logger.info("[UIManager] close_all_dialogs() called, cleaning up presenters...")
    
    # Collect all dialogs
    dialog_list = []
    dialog_list.extend(self._dialog_instances.values())
    if self._talent_profile_window_singleton:
        dialog_list.append(self._talent_profile_window_singleton)
    dialog_list.extend(self._open_scene_dialogs.values())
    dialog_list.extend(self._open_shot_scene_dialogs.values())
    
    self.tooltip_manager.cleanup()

    for dialog in dialog_list:
        if dialog:
            # ⭐ Explicitly call cleanup on presenter BEFORE closing
            if hasattr(dialog, 'presenter') and dialog.presenter and hasattr(dialog.presenter, 'cleanup'):
                try:
                    dialog.presenter.cleanup()
                except Exception as e:
                    logger.warning(f"Error during presenter cleanup for {type(dialog).__name__}: {e}")

            # Then close the dialog
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.close()

    # Clear tracking dictionaries
    self._dialog_instances.clear()
    self._talent_profile_window_singleton = None
    self._open_scene_dialogs.clear()
    self._open_shot_scene_dialogs.clear()
```

**Benefits:**
- Cleanup happens **synchronously** before new game starts
- No race condition with widget destruction
- Guaranteed signal disconnection

---

### Solution C: Defensive Guard in load_initial_data()

**Location:** [email_presenter.py:58-65](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/presenters/email_presenter.py#L58-L65)

Add a guard to prevent processing signals if the view is no longer visible:

```python
@pyqtSlot()
def load_initial_data(self):
    """
    The main entry point for refreshing the dialog. Fetches all emails,
    formats them into view models, and commands the view to update.
    """
    # ⭐ Guard: Don't process if view is hidden or deleted
    if not self.view or not self.view.isVisible():
        logger.info(f"[EmailPresenter #{self._instance_id}] Skipping load_initial_data - view is not visible.")
        return
        
    logger.info(f"[EmailPresenter #{self._instance_id}] load_initial_data() called.")
    all_emails = self.controller.get_all_emails()
    # ... rest of method
```

**Benefits:**
- Defense-in-depth: prevents stale processing even if cleanup fails
- No errors from trying to update a closed/deleted view
- Minimal performance overhead

---

### The cleanup() Method

**Location:** [email_presenter.py:49-55](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/presenters/email_presenter.py#L49-L55)

Every presenter that connects to controller signals should implement a `cleanup()` method:

```python
def cleanup(self):
    logger.info(f"[EmailPresenter #{self._instance_id}] cleanup() called.")
    try:
        self.controller.signals.emails_changed.disconnect(self.load_initial_data)
        logger.info(f"[EmailPresenter #{self._instance_id}] Successfully disconnected from emails_changed")
    except (RuntimeError, TypeError) as e:
        logger.warning(f"[EmailPresenter #{self._instance_id}] Failed to disconnect from emails_changed: {e}")
```

**Note:** The `view.destroyed.connect(self.cleanup)` connection (line 46) is still kept as a backup, but we don't rely on it for critical cleanup.

---

## Application-Wide Recommendations

### 1. Standard Presenter Pattern

All presenters that connect to controller signals should follow this pattern:

```python
class SomePresenter(QObject):
    def __init__(self, controller, view, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        
        # Connect to controller signals
        self.controller.signals.some_signal.connect(self.on_signal)
        
        # Backup cleanup on view destruction
        self.view.destroyed.connect(self.cleanup)
    
    def cleanup(self):
        """Disconnect all signal connections to prevent stale presenters."""
        try:
            self.controller.signals.some_signal.disconnect(self.on_signal)
        except (RuntimeError, TypeError):
            pass
    
    def on_signal(self):
        """Guard against processing when view is closed."""
        if not self.view or not self.view.isVisible():
            return
        # ... handle signal
```

### 2. Audit Existing Presenters

Review all presenters that connect to controller signals:

**Presenters to check:**
- ✅ `EmailPresenter` - Fixed
- `TalentTabPresenter`
- `ScenesTabPresenter`
- `ScheduleTabPresenter`
- `MarketTabPresenter`
- `AIStudiosTabPresenter`
- `MainWindowPresenter`
- `ScenePlannerPresenter`
- `ShotSceneDetailsPresenter`
- `TalentProfilePresenter`
- `PolicyPresenter`
- `CallSheetPresenter`

**For each presenter:**
1. Identify all `controller.signals.XXX.connect()` calls
2. Add corresponding `disconnect()` calls in `cleanup()`
3. Add visibility guard in signal handler methods
4. Ensure `view.destroyed.connect(self.cleanup)` is present

### 3. Tab Presenters Special Case

Tab presenters are different from dialog presenters:
- They are **long-lived** (exist for the entire game session)
- They should **not** be cleaned up when returning to main menu
- They should **only** be cleaned up when the main window is destroyed

**Current behavior is correct:** Tab presenters remain connected throughout the game session and are automatically cleaned up when the main window is destroyed (because they're parented to their view).

**No changes needed for tab presenters.**

### 4. Create a Base Presenter Class (Optional)

To enforce this pattern, consider creating a base class:

```python
class BaseDialogPresenter(QObject):
    """
    Base class for dialog presenters that connect to controller signals.
    Ensures proper lifecycle management and signal cleanup.
    """
    def __init__(self, controller, view, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self._signal_connections = []
        
        # Auto-cleanup on view destruction
        if hasattr(view, 'destroyed'):
            view.destroyed.connect(self.cleanup)
    
    def connect_signal(self, signal, slot):
        """
        Helper to track signal connections for automatic cleanup.
        Use this instead of direct signal.connect() calls.
        """
        signal.connect(slot)
        self._signal_connections.append((signal, slot))
    
    def cleanup(self):
        """Disconnect all tracked signal connections."""
        for signal, slot in self._signal_connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._signal_connections.clear()
```

**Usage:**
```python
class EmailPresenter(BaseDialogPresenter):
    def __init__(self, controller, view, parent=None):
        super().__init__(controller, view, parent)
        
        # Use helper instead of direct connect
        self.connect_signal(self.controller.signals.emails_changed, self.load_initial_data)
        self.connect_signal(self.view.email_selected, self.on_email_selected)
```

### 5. Logging Strategy

Keep minimal logging for important lifecycle events:

```python
# Keep these:
logger.info(f"[PresenterName #{instance_id}] Created.")
logger.info(f"[PresenterName #{instance_id}] cleanup() called.")

# Optional during debugging:
logger.info(f"[PresenterName #{instance_id}] Successfully disconnected from signal_name")
logger.warning(f"[PresenterName #{instance_id}] Failed to disconnect from signal_name: {e}")

# Remove verbose logging after bugs are fixed:
# logger.info(f"[PresenterName] load_initial_data() called.") # Too verbose for production
```

---

## Testing Checklist

When implementing cleanup for a presenter:

1. ✅ Start app, open dialog, perform action
2. ✅ Close dialog (or return to main menu)
3. ✅ Start new game
4. ✅ Verify old presenter doesn't react to new game signals
5. ✅ Check logs for "cleanup() called" message
6. ✅ Check logs for successful disconnect messages
7. ✅ Verify no duplicate signal processing

---

## Summary

### The Core Issue
Qt's asynchronous widget destruction creates a race condition where presenters can remain connected to signals after their views are closed.

### The Solution
1. **Synchronous cleanup**: Call `presenter.cleanup()` explicitly in `close_all_dialogs()`
2. **Defensive guards**: Check `view.isVisible()` before processing signals
3. **Standard pattern**: All presenters implement `cleanup()` to disconnect signals

### Benefits
- Prevents stale state bugs across game sessions
- Ensures clean separation between game instances
- Reduces memory leaks from lingering signal connections
- Makes presenter lifecycle explicit and controllable

### Next Steps
- Audit all presenters for signal connections
- Implement `cleanup()` methods where missing
- Add visibility guards to signal handlers
- Consider creating `BaseDialogPresenter` for consistency
