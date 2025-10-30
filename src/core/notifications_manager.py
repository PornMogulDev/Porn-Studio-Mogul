from PyQt6.QtCore import Qt, QPropertyAnimation, QTimer, QPoint, pyqtSignal
from PyQt6.QtWidgets import QLabel

from core.interfaces import IGameController
from ui.theme_manager import Theme

class NotificationManager:
    def __init__(self, parent, controller: IGameController):
        self.parent = parent
        self.controller = controller
        self.notifications = []
        self.bottom_margin = 20
        self.spacing = 10
        
        
    def show_notification(self, text):
        # Fetch current theme and font settings from the controller
        theme = self.controller.get_current_theme()
        font_family = self.controller.settings_manager.font_family
        font_size = self.controller.settings_manager.font_size
        
        # Create the notification with the theme data
        notification = FadingNotification(text, self.parent, theme, font_family, font_size)
        
        # Calculate position (bottom left with stacking)
        y_pos = self.parent.height() - notification.height() - self.bottom_margin
        for n in self.notifications:
            y_pos -= n.height() + self.spacing
            
        notification.move(20, y_pos)
        notification.show()
        
        self.notifications.append(notification)
        
        # Connect removal when notification closes
        notification.closed.connect(lambda: self.remove_notification(notification))
    
    def remove_notification(self, notification):
        if notification in self.notifications:
            self.notifications.remove(notification)
            self.reposition_notifications()
    
    def reposition_notifications(self):
        y_pos = self.parent.height() - self.bottom_margin
        for notification in reversed(self.notifications):
            y_pos -= notification.height() + self.spacing
            notification.move(20, y_pos)

class FadingNotification(QLabel):
    closed = pyqtSignal()
    
    def __init__(self, text: str, parent=None, theme: Theme = None, font_family: str = "Roboto", font_size: int = 12):
        super().__init__(text, parent)
        # Use theme colors if available, otherwise use sensible defaults.
        bg_color = theme.notification_background if theme else "rgba(51, 51, 51, 220)"
        text_color = theme.notification_text if theme else "white"
        # Use a slightly smaller font for notifications for a cleaner look
        notification_font_size = max(8, font_size - 2)

        self.setStyleSheet(f"""
            background-color: {bg_color};
            color: {text_color};
            padding: 8px;
            border-radius: 4px;
            font-size: 12px;
            font-family: "{font_family}";
            font-size: {notification_font_size}pt;
         """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Remove the problematic window flags - just use the parent
        self.setParent(parent)
        self.adjustSize()
        
        # Start fade out after 5 seconds
        QTimer.singleShot(5000, self.fade_out)
    
    def fade_out(self):
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(1000)  # 1 second fade
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.finished.connect(self.close_notification)
        self.animation.start()
    
    def close_notification(self):
        self.closed.emit()
        self.deleteLater()  # Use deleteLater instead of close() for proper cleanup