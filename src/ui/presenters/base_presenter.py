import logging
from typing import List, Tuple, Callable, Any
from PyQt6.QtCore import QObject

logger = logging.getLogger(__name__)

class BasePresenter(QObject):
    """
    Base class for presenters that connect to controller signals.
    Ensures proper lifecycle management and signal cleanup.
    
    Subclasses should:
    1. Call super().__init__(...)
    2. Use self.connect_signal() instead of direct signal.connect() for controller signals
    3. Override cleanup() if custom cleanup logic is needed (but call super().cleanup())
    """
    def __init__(self, controller, view, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self._signal_connections: List[Tuple[Any, Callable]] = []
        
        # Auto-cleanup on view destruction as a safety net
        # Ideally, cleanup() is called explicitly by UIManager before closing
        if hasattr(view, 'destroyed'):
            view.destroyed.connect(self.cleanup)
            
    def connect_signal(self, signal, slot):
        """
        Helper to track signal connections for automatic cleanup.
        Use this specifically for long-lived signals (like from GameController)
        that need to be disconnected when this presenter/view is destroyed.
        """
        try:
            signal.connect(slot)
            self._signal_connections.append((signal, slot))
        except Exception as e:
            logger.error(f"Failed to connect signal {signal} to slot {slot}: {e}")
    
    def cleanup(self):
        """
        Disconnects all tracked signal connections to prevent stale presenters.
        This should be called before the view is closed.
        """
        if not self._signal_connections:
            return
            
        logger.debug(f"[{self.__class__.__name__}] cleanup() called. Disconnecting {len(self._signal_connections)} signals.")
        
        for signal, slot in self._signal_connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError) as e:
                # Signal might already be disconnected or object deleted
                pass
            except Exception as e:
                logger.warning(f"Error disconnecting signal in {self.__class__.__name__}: {e}")
                
        self._signal_connections.clear()