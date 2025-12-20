from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, 
    QDialog, QTextEdit, QDialogButtonBox
)

from ui.widgets.clickable_svg_widget import ClickableSvgWidget
from ui.widgets.buttons.menu_button import MenuButton
from utils.paths import DISCORD_LOGO, GITHUB_LOGO, REDDIT_LOGO, F95_LOGO

class StartScreenView(QWidget):
    # Define signals for user interactions
    continue_clicked = pyqtSignal()
    load_clicked = pyqtSignal()
    new_game_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    editor_clicked = pyqtSignal()
    acknowledgements_clicked = pyqtSignal()
    quit_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        # --- Main Layout ---
        main_layout = QVBoxLayout(self)

        # Create containers
        top_container = QWidget()
        menu_container = QWidget()

        # Add containers with stretch factors
        main_layout.addWidget(top_container, 3)
        main_layout.addWidget(menu_container, 7)

        # --- Top Section ---
        top_layout = QVBoxLayout(top_container)
        
        title_label = QLabel("Porn Studio Mogul\n(Maybe this will be a title card one day)")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 30pt; font-weight: bold;")
        
        version_label = QLabel("0.6.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignBottom)
        version_label.setStyleSheet("font-size: 12pt;")

        top_layout.addWidget(title_label, 9)
        top_layout.addWidget(version_label, 1)
    
        # --- Menu Section ---
        menu_layout = QGridLayout(menu_container)
        menu_layout.setColumnStretch(0, 4)
        menu_layout.setColumnStretch(1, 8)
        menu_layout.setColumnStretch(2, 1)
        menu_layout.setHorizontalSpacing(100)

        # --- Left Buttons ---
        settings_btn = MenuButton("Settings")
        settings_btn.clicked.connect(self.settings_clicked.emit)
        
        editor_btn = MenuButton("Editor")
        editor_btn.setEnabled(False)
        editor_btn.clicked.connect(self.editor_clicked.emit)
        
        acknowledge_btn = MenuButton("Acknowledgements")
        acknowledge_btn.clicked.connect(self.acknowledgements_clicked.emit)

        # --- Middle Buttons ---
        self.continue_game_btn = MenuButton("Continue")
        self.continue_game_btn.clicked.connect(self.continue_clicked.emit)
        
        self.load_game_btn = MenuButton("Load Game")
        self.load_game_btn.clicked.connect(self.load_clicked.emit)
        
        new_game_btn = MenuButton("New Game")
        new_game_btn.clicked.connect(self.new_game_clicked.emit)
        
        quit_game_btn = MenuButton("Quit Game")
        quit_game_btn.clicked.connect(self.quit_clicked.emit)

        # --- Right Links ---
        # Note: ClickableSvgWidget handles its own opening of URLs, so no signals needed here
        discord_link = ClickableSvgWidget(DISCORD_LOGO, "https://discord.com/")
        github_link = ClickableSvgWidget(GITHUB_LOGO, "https://github.com/PornMogulDev/Porn-Studio-Mogul")
        reddit_link = ClickableSvgWidget(REDDIT_LOGO, "https://old.reddit.com/")
        f95_link = ClickableSvgWidget(F95_LOGO, "https://f95zone.to")

        # Layout placement
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
        menu_layout.addWidget(f95_link, 3, 2)

        # Set initial disabled state
        self.set_continue_enabled(False)
        self.set_load_enabled(False)

    def set_continue_enabled(self, enabled: bool):
        self.continue_game_btn.setEnabled(enabled)

    def set_load_enabled(self, enabled: bool):
        self.load_game_btn.setEnabled(enabled)

    def show_acknowledgements_dialog(self, text_content: str):
        """Displays the acknowledgements text in a modal dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Acknowledgements")
        dialog.setMinimumSize(600, 400)

        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit(dialog)
        text_edit.setReadOnly(True)
        text_edit.setMarkdown(text_content)
        layout.addWidget(text_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        dialog.exec()