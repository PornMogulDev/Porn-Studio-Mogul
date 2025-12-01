from PyQt6.QtWidgets import QStyledItemDelegate, QStyle
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect, QPointF
from PyQt6.QtGui import QTextDocument, QAbstractTextDocumentLayout, QPalette

class LinkHoverDelegate(QStyledItemDelegate):
    """
    A delegate that renders HTML content and detects hovers/clicks on <a> tags.
    Used for the 'Cast' column to make individual names interactive.
    """
    # Emits the ID (from href) and the global mouse position
    link_hover_entered = pyqtSignal(int, QPoint)
    link_hover_left = pyqtSignal()
    link_alt_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_hovered_link = None
        self._last_hit_test_pos = None

    def paint(self, painter, option, index):
        options = option
        self.initStyleOption(options, index)

        painter.save()

        # Setup Text Document for HTML rendering
        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(options.rect.width())
        doc.setDefaultFont(options.font)

        # Handle Selection Highlighting manually since we are drawing custom text
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(options.rect, option.palette.highlight())
            # Force text color to highlighted text color
            ctx = QAbstractTextDocumentLayout.PaintContext()
            ctx.palette.setColor(QPalette.ColorRole.Text, option.palette.color(QPalette.ColorRole.HighlightedText))
        else:
            ctx = QAbstractTextDocumentLayout.PaintContext()

        # Center vertically
        height = doc.size().height()
        y_offset = (options.rect.height() - height) / 2
        
        painter.translate(options.rect.left(), options.rect.top() + y_offset)
        doc.documentLayout().draw(painter, ctx)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """
        Handle mouse events to detect link interaction.
        Note: The View must have setMouseTracking(True) for MouseMove to trigger this.
        """
        if event.type() == event.Type.MouseMove:
            # OPTIMIZATION: Don't recalculate layout if mouse hasn't moved significantly
            # or if the event position isn't strictly within the visual rect (handled by View, but safe to check)
            if self._last_hit_test_pos and (event.pos() - self._last_hit_test_pos).manhattanLength() < 3:
                return False
            
            self._last_hit_test_pos = event.pos()
            anchor = self._get_anchor_at(event.pos(), option, index)
            
            if anchor:
                if anchor != self._last_hovered_link:
                    self._last_hovered_link = anchor
                    try:
                        talent_id = int(anchor)
                        # We need global pos for the tooltip
                        self.link_hover_entered.emit(talent_id, event.globalPosition().toPoint())
                    except ValueError:
                        pass
            else:
                if self._last_hovered_link:
                    self.link_hover_left.emit()
                    self._last_hovered_link = None
            
            # Return False so we don't consume the event (allow row selection hover effects)
            return False

        elif event.type() == event.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
                anchor = self._get_anchor_at(event.pos(), option, index)
                if anchor:
                    try:
                        self.link_alt_clicked.emit(int(anchor))
                        return True
                    except ValueError:
                        pass

        return super().editorEvent(event, model, option, index)

    def _get_anchor_at(self, pos: QPoint, option, index) -> str:
        """Hit-test the HTML document to find an anchor."""
        doc = QTextDocument()
        doc.setHtml(index.data())
        doc.setTextWidth(option.rect.width())
        doc.setDefaultFont(option.font)

        # Re-calculate vertical offset used in paint
        height = doc.size().height()
        y_offset = (option.rect.height() - height) / 2

        # Translate mouse pos to document coordinates
        local_x = pos.x() - option.rect.left()
        local_y = pos.y() - option.rect.top() - y_offset

        # CHANGED: Use QPointF for Qt6 compatibility
        return doc.documentLayout().anchorAt(QPointF(local_x, local_y))