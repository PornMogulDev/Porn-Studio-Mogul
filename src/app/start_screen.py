import logging
from pathlib import Path
from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import ( QDialog, QLabel, QPushButton, QSizePolicy, 
                             QVBoxLayout, QWidget, QTextEdit, QGridLayout,
                              QDialogButtonBox )
from PyQt6.QtSvgWidgets import QSvgWidget

from ui.dialogs.save_load_ui import SaveLoadDialog
from ui.dialogs.settings_dialog import SettingsDialog
from utils.paths import DISCORD_LOGO, GITHUB_LOGO, REDDIT_LOGO, ACKNOWLEDGEMENTS_FILE
from ui.widgets.clickable_svg_widget import ClickableSvgWidget

logger = logging.getLogger(__name__)

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
    """A simplified, layout-friendly SVG widget that maintains its aspect ratio."""
    def __init__(self, svg_file: str | Path, url: str):
        if isinstance(svg_file, Path):
            super().__init__(str(svg_file))
        else:
            super().__init__(svg_file)
        self.url = url
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.renderer = self.renderer()
        if self.renderer.defaultSize().width() > 0:
            self.aspect_ratio = self.renderer.defaultSize().height() / self.renderer.defaultSize().width()
        else:
            self.aspect_ratio = 1.0  # Fallback for invalid SVGs

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumSize(50, int(50 * self.aspect_ratio))
        self.setMaximumSize(250, int(250 * self.aspect_ratio))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return int(width * self.aspect_ratio)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl(self.url))
        super().mousePressEvent(event)

class MenuScreen(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

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
        title_label.setStyleSheet("font-size: 30pt; font-weight: bold;") # Override for title
        
        version_label = QLabel("0.5.1 (font implementation)")
        version_label.setAlignment(Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignBottom)

        top_layout.addWidget(title_label, 9)   # Give the title 9 shares of space
        top_layout.addWidget(version_label, 1) # Give it 1 share of space
    
        # --- Menu Section ---
        menu_layout = QGridLayout(menu_container)
        menu_layout.setColumnStretch(0, 4)  # first column stretch factor
        menu_layout.setColumnStretch(1, 8)
        menu_layout.setColumnStretch(2, 1)
        menu_layout.setHorizontalSpacing(100)

        # --- Left Buttons ---
        
        settings_btn = MenuButton("Settings")
        settings_btn.clicked.connect(self.show_settings_dialog) 
        editor_btn = MenuButton("Editor")
        editor_btn.setEnabled(False)
        acknowledge_btn = MenuButton("Acknowledgements")
        acknowledge_btn.clicked.connect(self.show_acknowledgements_dialog)

        # --- Middle Buttons ---
        
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

        # --- Right Links ---
        discord_link = ClickableSvgWidget(DISCORD_LOGO, "https://discord.com/")
        github_link = ClickableSvgWidget(GITHUB_LOGO, "https://github.com/PornMogulDev/Porn-Studio-Mogul")
        reddit_link = ClickableSvgWidget(REDDIT_LOGO, "https://reddit.com/")

        menu_layout.addWidget(settings_btn, 1, 0)
        menu_layout.addWidget(editor_btn, 2, 0)
        menu_layout.addWidget(acknowledge_btn, 3, 0)

        menu_layout.addWidget(self.continue_game_btn, 0, 1)
        menu_layout.addWidget(self.load_game_btn, 1, 1)
        menu_layout.addWidget(new_game_btn, 2, 1)
        menu_layout.addWidget(quit_game_btn, 3, 1)

        menu_layout.addWidget(discord_link, 0, 2)
        menu_layout.addWidget(github_link, 1, 2)
        menu_layout.addWidget(reddit_link, 2, 2)

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

    def show_acknowledgements_dialog(self):
        """Creates and shows the acknowledgements dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Acknowledgements")
        dialog.setMinimumSize(600,400)

        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit(dialog)
        text_edit.setReadOnly(True)
        try:
            with open(ACKNOWLEDGEMENTS_FILE, 'r', encoding='utf-8') as f:
                content = f.read()

            text_edit.setMarkdown(content)
            layout.addWidget(text_edit)

            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            button_box.accepted.connect(dialog.accept)
            layout.addWidget(button_box)

            dialog.exec()
        except FileNotFoundError:
            logger.error(f"The acknowledgements file could not be found at:<br>{ACKNOWLEDGEMENTS_FILE}")