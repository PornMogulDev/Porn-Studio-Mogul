from PyQt6.QtCore import Qt, QPropertyAnimation, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel

class NotificationManager:
    def __init__(self, parent):
        self.parent = parent
        self.notifications = []
        self.bottom_margin = 20
        self.spacing = 10
        
        
    def show_notification(self, text):
        notification = FadingNotification(text, self.parent)
        
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
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            background-color: rgba(51, 51, 51, 220);
            color: white;
            padding: 8px;
            border-radius: 4px;
            font-size: 12px;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Remove the problematic window flags - just use the parent
        self.setParent(parent)
        self.adjustSize()
        
        # Start fade out after 3 seconds
        QTimer.singleShot(3000, self.fade_out)
    
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