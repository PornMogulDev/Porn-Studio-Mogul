from PyQt6.QtCore import QObject

class GameMenuPresenter(QObject):
    def __init__(self, view, ui_manager, parent=None):
        super().__init__(parent)
        self.view = view
        self.ui_manager = ui_manager
        
        # Connect View Signals to Manager Actions
        self.view.save_clicked.connect(self._on_save)
        self.view.load_clicked.connect(self._on_load)
        self.view.settings_clicked.connect(self.ui_manager.show_settings_dialog)
        self.view.return_to_menu_clicked.connect(self.ui_manager.show_exit_dialog)
        self.view.quit_clicked.connect(self.ui_manager.show_quit_dialog)

    def _on_save(self):
        self.ui_manager.show_save_load('save')

    def _on_load(self):
        self.ui_manager.show_save_load('load')