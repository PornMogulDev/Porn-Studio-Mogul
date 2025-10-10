from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSizePolicy, QSpacerItem, QStyle,
    QTabWidget, QWidget, QVBoxLayout,
)

from ui.tabs.talent_tab import HireWindow
from ui.tabs.scenes_tab import ScenesTab
from ui.tabs.schedule_tab import ScheduleTab
from notifications import NotificationManager
from ui.dialogs.save_load_ui import SaveLoadDialog
from ui.dialogs.go_to_list import GoToTalentDialog
from ui.tabs.market_tab import MarketTab 
from ui.dialogs.email_dialog import EmailDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.incomplete_scheduled_scene import IncompleteCastingDialog
from ui.dialogs.interactive_event_dialog import InteractiveEventDialog
from ui.dialogs.help_dialog import HelpDialog
from game_state import Scene
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.presenters.hire_talent_presenter import HireTalentPresenter
from ui.widgets.help_button import HelpButton


class GameMenuDialog(GeometryManagerMixin, QDialog):
    """A dialog that serves as the in-game menu."""
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.setWindowTitle("Game Menu")
        self.setup_ui()
        self._restore_geometry()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        resume_btn = QPushButton("Resume Game")
        save_btn = QPushButton("Save Game")
        load_btn = QPushButton("Load Game")
        settings_btn = QPushButton("Settings")
        return_to_menu_btn = QPushButton("Return to Main Menu")
        quit_btn = QPushButton("Quit to Desktop")

        layout.addWidget(resume_btn)
        layout.addWidget(save_btn)
        layout.addWidget(load_btn)
        layout.addWidget(settings_btn)
        layout.addWidget(return_to_menu_btn)
        layout.addWidget(quit_btn)

        # Connections
        resume_btn.clicked.connect(self.accept)
        return_to_menu_btn.clicked.connect(self.return_to_menu)
        save_btn.clicked.connect(self.save_game)
        load_btn.clicked.connect(self.load_game)
        settings_btn.clicked.connect(self.show_settings_dialog)
        quit_btn.clicked.connect(self.quit_game)

    def return_to_menu(self):
        dialog = ExitDialog(self.controller, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            exit_save = dialog.get_data()
            self.controller.return_to_main_menu(exit_save)
        self.accept() # Close menu after action

    def save_game(self):
        dialog = SaveLoadDialog(self.controller, mode='save', parent=self)
        dialog.save_selected.connect(self.controller.save_game)
        dialog.exec()

    def load_game(self):
        dialog = SaveLoadDialog(self.controller, mode='load', parent=self)
        dialog.save_selected.connect(self.controller.load_game)
        dialog.exec()

    def show_settings_dialog(self):
        """Creates and shows the settings dialog."""
        dialog = SettingsDialog(self.controller, self)
        dialog.exec()
    def quit_game(self):
        dialog = ExitDialog(self.controller, text="Create 'Exit Save' before quitting?", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            exit_save = dialog.get_data()
            self.controller.quit_game(exit_save)


class MainGameWindow(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.hire_presenter = None
        self.go_to_list_dialog = None
        self.help_dialog = None
        self.email_dialog = None
        self.setup_ui()
        self.notification_manager = NotificationManager(self)

        self.controller.signals.notification_posted.connect(self.notification_manager.show_notification)
        self.controller.signals.money_changed.connect(self.update_money_display)
        self.controller.signals.time_changed.connect(self.update_time_display)
        self.controller.signals.emails_changed.connect(self.update_inbox_button)
        self.controller.signals.game_over_triggered.connect(self.game_over_ui)
        self.controller.signals.market_changed.connect(self.market_tab.refresh_view)
        self.controller.signals.incomplete_scene_check_requested.connect(self.handle_incomplete_scenes)
        self.controller.signals.interactive_event_triggered.connect(self.show_interactive_event_dialog)
        self.controller.signals.show_help_requested.connect(self.show_help_dialog)


    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Top bar ---
        top_bar_layout = QHBoxLayout()

        menu_btn = QPushButton("☰ Menu")
        menu_btn.setToolTip("Open Game Menu (Esc)")
        menu_btn.clicked.connect(self.show_game_menu)
        top_bar_layout.addWidget(menu_btn)

        next_week_btn = QPushButton("Next Week ►")
        next_week_btn.setToolTip("Advance to the next week (Spacebar)")
        next_week_btn.clicked.connect(self.controller.advance_week)
        top_bar_layout.addWidget(next_week_btn)

        top_bar_layout.addStretch()
        help_btn = HelpButton("general_overview", self.controller, self)
        top_bar_layout.addWidget(help_btn)
        
        top_bar_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        self.money_label = QLabel("Money: $---")
        self.money_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        top_bar_layout.addWidget(self.money_label)
        
        self.time_label = QLabel("Week: --, Year: ----")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        top_bar_layout.addWidget(self.time_label)
        
        layout.addLayout(top_bar_layout)

        # --- Tabs ---
        tabs = QTabWidget()
        tabs.setMovable(True)
        
        self.hire_tab = HireWindow()
        self.hire_presenter = HireTalentPresenter(self.controller, self.hire_tab)

        self.scenes_tab = ScenesTab(self.controller)
        self.schedule_tab = ScheduleTab(self.controller)
        self.market_tab = MarketTab(self.controller)

        tabs.addTab(self.schedule_tab, "Schedule")
        tabs.addTab(self.hire_tab, "Hire Talent")
        tabs.addTab(self.scenes_tab, "Scenes")
        tabs.addTab(self.market_tab, "Market")
        
        layout.addWidget(tabs)

        # Bottom layout
        bottom_bar_layout = QHBoxLayout()
        self.inbox_btn = QPushButton("✉ Inbox")
        self.inbox_btn.clicked.connect(self.show_inbox)
        bottom_bar_layout.addWidget(self.inbox_btn)
        go_to_list_btn = QPushButton("Go-To List")
        go_to_list_btn.clicked.connect(self.show_go_to_list)
        bottom_bar_layout.addWidget(go_to_list_btn)
        layout.addLayout(bottom_bar_layout)
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for the main window."""
        if event.key() == Qt.Key.Key_Escape:
            self.show_game_menu()
        elif event.key() == Qt.Key.Key_P:
            self.controller.advance_week()
        elif event.key() == Qt.Key.Key_F5:
            self.controller.quick_save()
        elif event.key() == Qt.Key.Key_F9:
            self.controller.quick_load()
        else:
            # Allow other widgets (like line edits) to process key presses
            super().keyPressEvent(event)

    def show_interactive_event_dialog(self, event_data: dict, scene_id: int, talent_id: int):
        """
        Handles the interactive_event_triggered signal. Pauses the UI and
        displays the event dialog to the player.
        """
        scene_data = self.controller.get_scene_for_planner(scene_id)
        talent_data = self.controller.talent_service.get_talent_by_id(talent_id)
        current_money = self.controller.game_state.money

        if not scene_data or not talent_data:
            print(f"[UI ERROR] Could not fetch required data for event ID '{event_data.get('id')}'. Scene: {scene_data}, Talent: {talent_data}")
            self.controller.resolve_interactive_event(event_data['id'], scene_id, talent_id, "error_fallback")
            return

        dialog = InteractiveEventDialog(
            event_data=event_data,
            scene_data=scene_data,
            talent_data=talent_data,
            current_money=current_money,
            controller=self.controller,
            parent=self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            choice_id = dialog.selected_choice_id
            event_id = event_data['id']
            
            if choice_id:
                self.controller.resolve_interactive_event(event_id, scene_id, talent_id, choice_id)
            else:
                print(f"[UI WARN] Event dialog for '{event_id}' was accepted but no choice ID was returned. Resuming.")
                self.controller.resolve_interactive_event(event_id, scene_id, talent_id, "no_choice_fallback")

    def show_game_menu(self):
        """Creates and shows the game menu dialog."""
        dialog = GameMenuDialog(self.controller, self)
        dialog.exec()
    
    def show_go_to_list(self):
        """Creates and shows the Go-To talent list dialog."""
        if self.go_to_list_dialog is None:
            self.go_to_list_dialog = GoToTalentDialog(self.controller, self)

        self.go_to_list_dialog.show()
        self.go_to_list_dialog.raise_()
        self.go_to_list_dialog.activateWindow()
    
    def show_inbox(self):
        """Creates and shows the email inbox dialog."""
        if self.email_dialog is None:
            self.email_dialog = EmailDialog(self.controller, self)

        self.email_dialog.show()
        self.email_dialog.raise_()
        self.email_dialog.activateWindow()

    def show_help_dialog(self, topic_key: str):
        """Creates and shows the Help dialog, focusing on a specific topic."""
        if self.help_dialog is None:
            self.help_dialog = HelpDialog(self.controller, self)

        # The show_topic method handles showing, raising, and activating the window
        self.help_dialog.show_topic(topic_key)

    def handle_incomplete_scenes(self, scenes: list):
        all_resolved = True
        for scene_data in scenes:
            fresh_scene_data = self.controller.get_scene_for_planner(scene_data.id)
            if not fresh_scene_data:
                continue 
            
            dialog = IncompleteCastingDialog(fresh_scene_data, self.controller, self)
            result = dialog.exec()

            if result == QDialog.DialogCode.Rejected:
                all_resolved = False
                self.controller.signals.notification_posted.emit("Week advancement cancelled.")
                break
        
        if all_resolved:
            self.controller.advance_week()
    
    def refresh_all_ui(self):
        """Pulls all current data from the controller and updates the entire UI."""
        self.update_money_display(self.controller.game_state.money)
        self.update_time_display(self.controller.game_state.week, self.controller.game_state.year)
        self.update_inbox_button()

        if self.hire_presenter:
            self.hire_presenter.view.refresh_from_state()

        self.scenes_tab.refresh_view()
        self.schedule_tab.update_year_selector()
        self.market_tab.refresh_view()

    def update_money_display(self, money: int):
        self.money_label.setText(f"Money: ${money:,}")

    def update_time_display(self, week: int, year: int):
        self.time_label.setText(f"Week {week}, {year}")
    
    def update_inbox_button(self):
        unread_count = self.controller.get_unread_email_count()
        if unread_count > 0:
            self.inbox_btn.setText(f"Inbox ({unread_count})")
            self.inbox_btn.setStyleSheet("background-color: #3d9046;") 
        else:
            self.inbox_btn.setText("Inbox")
            self.inbox_btn.setStyleSheet("")
    
    def game_over_ui(self, reason: str):
        self.setEnabled(False) 

        if reason == "bankruptcy":
            msg = QMessageBox()
            msg.setWindowTitle("Game Over: Bankruptcy")
            msg.setInformativeText("You accumulated too much debt. Game is over.")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec() 
            self.controller.handle_game_over()

        self.setEnabled(True)

class ExitDialog(GeometryManagerMixin, QDialog):
    def __init__(self, controller, text="Create 'Exit Save'?", parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.setup_ui(text)
        self._restore_geometry()
    
    def setup_ui(self, text):
        self.setWindowTitle("Confirm Action")
        layout = QVBoxLayout(self)
        
        cb_container = QWidget(); cb_layout = QHBoxLayout(cb_container)
        cb_text = QLabel(text); self.save_on_exit_cb = QCheckBox()
        
        default_checked = self.controller.settings_manager.get_setting("save_on_exit", True)
        self.save_on_exit_cb.setChecked(default_checked)
        
        cb_layout.addWidget(cb_text); cb_layout.addWidget(self.save_on_exit_cb)
        layout.addWidget(cb_container)
        
        button_box = QDialogButtonBox()
        button_box.addButton("Confirm", QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(button_box)
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def accept(self):
        new_state = self.save_on_exit_cb.isChecked()
        self.controller.settings_manager.set_setting("save_on_exit", new_state)
        super().accept()
        
    def get_data(self):
        return self.save_on_exit_cb.isChecked()