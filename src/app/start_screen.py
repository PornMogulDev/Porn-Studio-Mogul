import logging
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import ( QDialog, QLabel, QPushButton, QSizePolicy, 
                             QVBoxLayout, QWidget, QTextEdit, QGridLayout,
                              QDialogButtonBox )

from utils.paths import DISCORD_LOGO, GITHUB_LOGO, REDDIT_LOGO, F95_LOGO, ACKNOWLEDGEMENTS_FILE
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

class MenuScreen(QWidget):
    def __init__(self, controller, ui_manager):
        super().__init__()
        self.controller = controller
        self.ui_manager = ui_manager

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
        
        version_label = QLabel("0.5.7b (presenters refactor)")
        version_label.setAlignment(Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignBottom)
        version_label.setStyleSheet("font-size: 12pt;") # And for version

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
        settings_btn.clicked.connect(self.ui_manager.show_settings_dialog) 
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
        f95_link = ClickableSvgWidget(F95_LOGO, "https://f95zone.to")

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

        self.refresh_button_states()

    def refresh_button_states(self):
        has_saves = self.controller.check_for_saves()
        
        self.continue_game_btn.setEnabled(has_saves)
        self.load_game_btn.setEnabled(has_saves)

    def show_load_dialog(self):
        self.ui_manager.show_save_load('load')
    
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