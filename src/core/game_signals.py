from PyQt6.QtCore import QObject, pyqtSignal

class GameSignals(QObject):
    """A central collection of signals for the entire application."""
    
    show_start_screen_requested = pyqtSignal()
    show_main_window_requested = pyqtSignal()
    money_changed = pyqtSignal(int)
    time_changed = pyqtSignal(int, int)
    roster_changed = pyqtSignal()
    scenes_changed = pyqtSignal()
    talent_pool_changed = pyqtSignal()
    talent_generated = pyqtSignal(list)
    notification_posted = pyqtSignal(str)
    interactive_event_triggered = pyqtSignal(dict, int, int)
    new_game_started = pyqtSignal()
    saves_changed = pyqtSignal()
    go_to_list_changed = pyqtSignal()
    go_to_categories_changed = pyqtSignal()
    emails_changed = pyqtSignal()
    game_over_triggered = pyqtSignal(str)
    quit_game_requested = pyqtSignal()
    market_changed = pyqtSignal()
    favorites_changed = pyqtSignal()
    incomplete_scene_check_requested = pyqtSignal(list)
    show_help_requested = pyqtSignal(str)