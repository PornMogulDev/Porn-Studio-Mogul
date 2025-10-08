import sys
from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from PyQt6.QtSvgWidgets import QSvgWidget
from save_load_ui import SaveLoadDialog
from ui.dialogs.settings_dialog import SettingsDialog
from paths import DISCORD_LOGO, GITHUB_LOGO, REDDIT_LOGO
from game_strings import version

class MenuButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        # Set the rules: This button can expand horizontally, but prefers a fixed height.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Set the safety nets
        self.setMinimumHeight(40)
        self.setMaximumHeight(100)

    """def sizeHint(self):
        # We tell the layout our ideal size is 250x60.
        return QSize(250, 60)"""
    
class ClickableSvgWidget(QSvgWidget):
    """A simplified, layout-friendly SVG widget."""
    def __init__(self, svg_file, url):
        super().__init__(svg_file)
        self.url = url
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Let the layout manager control our size. We are happy to expand.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # But don't let us get too big.
        self.setMinimumSize(80,45)
        self.setMaximumSize(320,180)

    def sizeHint(self):
        return QSize(240, 135)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl(self.url))
        super().mousePressEvent(event)

class MenuScreen(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        # A single stylesheet for the whole screen provides a consistent look.
        self.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 10px 20px;
            }
            QLabel {
                font-size: 14px;
            }
        """)

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)

        # Create containers
        top_container = QWidget()
        menu_container = QWidget()

        # Add containers with stretch factors to maintain vertical proportions
        main_layout.addWidget(top_container, 3)  # 20% of the space
        main_layout.addWidget(menu_container, 7) # 80% of the space

        # --- Top Section ---
        top_layout = QVBoxLayout(top_container)
        
        title_label = QLabel("Porn Studio Mogul\n(Maybe this will be a title card one day)")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 32px; font-weight: bold;") # Override for title
        
        version_label = QLabel(version)
        version_label.setAlignment(Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignBottom)

        top_layout.addWidget(title_label, 9)   # Give the title 9 shares of space
        top_layout.addWidget(version_label, 1) # Give it 1 share of space
    
        # --- Menu Section ---
        menu_layout = QHBoxLayout(menu_container)

        left_buttons_container = QWidget()
        middle_buttons_container = QWidget()
        right_links_container = QWidget()

        #Bottom margins. No need to do anything because they are blank
        left_margin_container = QWidget()
        one_inside_container = QWidget()
        two_inside_container = QWidget()
        right_margin_container = QWidget()

        # Add containers with stretch factors to maintain horizontal proportions
        menu_layout.addWidget(left_margin_container, 1)
        menu_layout.addWidget(left_buttons_container, 3)   # 20%
        menu_layout.addWidget(one_inside_container, 1)
        menu_layout.addWidget(middle_buttons_container, 7) # 60%
        menu_layout.addWidget(two_inside_container, 1)
        menu_layout.addWidget(right_links_container, 2)  # 20%
        menu_layout.addWidget(right_margin_container, 1)

        # --- Left Buttons ---
        left_layout = QVBoxLayout(left_buttons_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        settings_btn = MenuButton("Settings")
        settings_btn.clicked.connect(self.show_settings_dialog) 
        editor_btn = MenuButton("Editor")
        editor_btn.setEnabled(False)
        acknowledge_btn = MenuButton("Acknowledgements")
        acknowledge_btn.setEnabled(False)

        left_layout.addStretch(3)
        left_layout.addWidget(settings_btn, 2)
        left_layout.addStretch(1)
        left_layout.addWidget(editor_btn, 2)
        left_layout.addStretch(1)
        left_layout.addWidget(acknowledge_btn, 2)

        # --- Middle Buttons ---
        middle_layout = QVBoxLayout(middle_buttons_container)
        middle_layout.setContentsMargins(50, 0, 50, 0) # Less margin needed now
        
        self.continue_game_btn = MenuButton("Continue")
        self.continue_game_btn.setEnabled(False)
        self.continue_game_btn.clicked.connect(self.controller.continue_game)
        self.load_game_btn = MenuButton("Load Game")
        self.load_game_btn.setEnabled(False)
        self.load_game_btn.clicked.connect(self.show_load_dialog)
        new_game_btn = MenuButton("New Game")
        new_game_btn.clicked.connect(self.controller.new_game_started)
        quit_game_btn = MenuButton("Quit Game")
        quit_game_btn.clicked.connect(self.controller.quit_game)

        middle_layout.addWidget(self.continue_game_btn, 2)
        middle_layout.addStretch(1)
        middle_layout.addWidget(self.load_game_btn, 2)
        middle_layout.addStretch(1)
        middle_layout.addWidget(new_game_btn, 2)
        middle_layout.addStretch(1)
        middle_layout.addWidget(quit_game_btn, 2)
        middle_layout.addStretch(2) # Balances the stretch above

        # --- Right Links ---
        links_layout = QVBoxLayout(right_links_container)
        
        discord_link = ClickableSvgWidget(DISCORD_LOGO, "https://discord.com/")
        github_link = ClickableSvgWidget(GITHUB_LOGO, "https://github.com/")
        reddit_link = ClickableSvgWidget(REDDIT_LOGO, "https://reddit.com/")

        links_layout.addWidget(discord_link, 3)
        links_layout.addStretch(1)
        links_layout.addWidget(github_link, 3)
        links_layout.addStretch(1)
        links_layout.addWidget(reddit_link, 3)
        links_layout.addStretch(7)

        self.refresh_button_states()

    def refresh_button_states(self):
        has_saves = self.controller.check_for_saves()
        
        self.continue_game_btn.setEnabled(has_saves)
        self.load_game_btn.setEnabled(has_saves)

    def show_load_dialog(self):
        dialog = SaveLoadDialog(self.controller, mode='load', parent=self)
        dialog.save_selected.connect(self.controller.load_game)
        dialog.exec()
    
    def show_settings_dialog(self):
        """Creates and shows the settings dialog."""
        dialog = SettingsDialog(self.controller, self)
        dialog.exec()