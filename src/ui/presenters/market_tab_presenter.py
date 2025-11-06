from typing import Dict, List, Set

from PyQt6.QtCore import QObject, pyqtSlot, QTimer

from core.interfaces import IGameController
from ui.view_models import MarketGroupViewModel, SentimentViewModel
from ui.theme_manager import Theme

class MarketTabPresenter(QObject):
    """
    Presenter for the MarketTab. Handles all logic for fetching, processing,
    and preparing market data for display in the view.
    """
    def __init__(self, controller: IGameController, view, parent=None):
        """
        Initializes the presenter.
            
        Args:
            controller (IGameController): The main game controller for data access.
            view: The MarketTab view this presenter manages.
            parent (QObject, optional): The parent object in the Qt hierarchy.
                                        Crucially, this should be the view instance
                                        to tie their lifecycles together.
        """
        super().__init__(parent)
        self.controller = controller
        self.view = view

        # --- Signal Connections ---
        # When the underlying market data changes, refresh the whole tab.
        self.controller.signals.market_changed.connect(self.load_initial_data)
        
        # When the user selects a different group in the view's dropdown.
        self.view.group_selected.connect(self.on_group_selected)
        self.view.help_requested.connect(self.on_help_requested)

    @pyqtSlot()
    def load_initial_data(self):
        """
        Loads the initial list of market groups into the view's selector.
        This is the main entry point for refreshing the tab's content.
        """
        group_data = self.controller.market_data.get('viewer_groups', [])
        group_names = [g.get('name') for g in group_data if g.get('name')]
        
        self.view.update_group_selector(group_names)
        
        # The view's update_group_selector will trigger the currentTextChanged signal
        # if items are present, which in turn emits group_selected, calling
        # on_group_selected automatically. If no items, we explicitly clear the view.
        if not group_names:
            self.on_group_selected(None)

    @pyqtSlot(str)
    def on_group_selected(self, group_name: str):
        """
        Fetches detailed data for the selected group, processes it into a
        view model, and tells the view to display it.
        """
        if not group_name:
            # If no group is selected, create a non-visible view model to clear the view.
            self.view.display_group_details(MarketGroupViewModel(is_visible=False))
            return

        # --- Data Fetching ---
        original_group_data = next((g for g in self.controller.market_data.get('viewer_groups', []) if g.get('name') == group_name), {})
        resolved_data = self.controller.get_resolved_group_data(group_name)
        dynamic_state = self.controller.get_all_market_states().get(group_name)
        current_theme = self.controller.get_current_theme()
        
        if not resolved_data or not dynamic_state:
            self.view.display_group_details(MarketGroupViewModel(is_visible=False, title=f"Error: Data not found for {group_name}"))
            return

        # --- View Model Creation ---
        vm = MarketGroupViewModel()

        # Title
        vm.title = resolved_data.get('name', 'Unknown Group')
        if inherits_from := original_group_data.get('inherits_from'):
            vm.title += f" (inherits from {inherits_from})"
        
        # Attributes
        vm.attributes.append(("Market Share:", f"{resolved_data.get('market_share_percent', 0):.1f}%"))
        vm.attributes.append(("Spending Power:", f"{resolved_data.get('spending_power', 1.0):.2f}x"))
        vm.attributes.append(("Focus Bonus:", f"{resolved_data.get('focus_bonus', 1.0):.2f}x"))
        vm.attributes.append(("Spending Willingness:", f"{(dynamic_state.current_saturation * 100):.2f}%"))
        
        prefs_data = resolved_data.get('preferences', {})
        discovered_sentiments = dynamic_state.discovered_sentiments
        
        # Sentiments
        vm.orientation_sentiments = self._create_sentiment_view_models(
            prefs_data.get('orientation_sentiments', {}),
            discovered_sentiments.get('orientation_sentiments', []),
            current_theme
        )
        vm.dom_sub_sentiments = self._create_sentiment_view_models(
            prefs_data.get('dom_sub_sentiments', {}),
            discovered_sentiments.get('dom_sub_sentiments', []),
            current_theme
        )
        vm.thematic_sentiments = self._create_sentiment_view_models(
            prefs_data.get('thematic_sentiments', {}),
            discovered_sentiments.get('thematic_sentiments', []),
            current_theme,
            is_additive=True
        )
        vm.physical_sentiments = self._create_sentiment_view_models(
            prefs_data.get('physical_sentiments', {}),
            discovered_sentiments.get('physical_sentiments', []),
            current_theme
        )
        vm.action_sentiments = self._create_sentiment_view_models(
            prefs_data.get('action_sentiments', {}),
            discovered_sentiments.get('action_sentiments', []),
            current_theme
        )

        # Spillover
        spillover_data = resolved_data.get('popularity_spillover', {})
        for target, rate in spillover_data.items():
            vm.spillover_details.append((f"To {target}:", f"{rate*100:.0f}%"))

        # --- Update View ---
        self.view.display_group_details(vm)

    def _create_sentiment_view_models(
        self,
        data_dict: Dict[str, float],
        discovered_tags: List[str],
        theme: Theme,
        is_additive: bool = False
    ) -> List[SentimentViewModel]:
        """
        Helper function to process a dictionary of sentiment data into a
        list of SentimentViewModel objects, ready for display.
        """
        if not data_dict:
            return []
            
        view_models = []
        discovered_set = set(discovered_tags)
        
        # Sort by value, highest first, to display most impactful sentiments at the top.
        sorted_items = sorted(data_dict.items(), key=lambda item: item[1], reverse=True)

        for key, sentiment in sorted_items:
            if key not in discovered_set:
                view_models.append(SentimentViewModel(label="???", value_str="", color=None))
                continue

            color = None
            if is_additive:
                value_str = f"{sentiment:+.2f}"
                if sentiment > 0: color = theme.color_good
                elif sentiment < 0: color = theme.color_bad
            else: # Multiplicative
                value_str = f"{sentiment:.2f}x"
                if sentiment > 1.0: color = theme.color_good
                elif sentiment < 1.0: color = theme.color_bad
            
            view_models.append(SentimentViewModel(label=key, value_str=value_str, color=color))
            
        return view_models
    
    @pyqtSlot(str)
    def on_help_requested(self, topic_key: str):
        self.controller.signals.show_help_requested.emit(topic_key)