from PyQt6.QtWidgets import QGroupBox, QWidget

class CollapsibleGroupBox(QGroupBox):
    """
    A custom QGroupBox that can be collapsed and expanded by clicking its title checkbox.
    
    The initial state should be set by calling `set_collapsed()` *after* all child
    widgets and a layout have been added to the group box.
    """
    def __init__(self, title: str, parent: QWidget = None):
        """
        Initializes the CollapsibleGroupBox.

        :param title: The title to display on the group box.
        :param parent: The parent widget.
        """
        super().__init__(title, parent)

        # Make the group box checkable, which adds a checkbox to the title.
        self.setCheckable(True)
        # By default, the group box starts expanded (checked).
        self.setChecked(True)

        self._stretch_factor_stored = False
        self._original_stretch_factor = 0

        # Connect the toggled signal (emitted when the checkbox is clicked)
        # to our internal method that shows/hides the contents.
        self.toggled.connect(self._toggle_contents)

    def _toggle_contents(self, checked: bool):
        """
        Internal slot that is called when the group box's checkbox is toggled.
        This method iterates through all child widgets managed by the layout and sets
        their visibility according to the checkbox state.
        """
        # A QGroupBox's children are managed by its layout. If there's no layout,
        # there's nothing to toggle.
        if self.layout() is None:
            return

        # Iterate over all items in the layout.
        for i in range(self.layout().count()):
            item = self.layout().itemAt(i)
            if item and item.widget():
                # Set the visibility of the widget associated with the layout item.
                item.widget().setVisible(checked)

        # Dynamically adjust the stretch factor in the parent layout to allow
        # the group box to shrink completely.
        parent = self.parentWidget()
        if not (parent and parent.layout()):
            return

        parent_layout = parent.layout()
        # Find this widget in its parent's layout's list of items.
        for i in range(parent_layout.count()):
            item = parent_layout.itemAt(i)
            if item and item.widget() == self:
                # On the first toggle, capture the original stretch factor.
                if not self._stretch_factor_stored:
                    self._original_stretch_factor = parent_layout.stretch(i)
                    self._stretch_factor_stored = True

                if checked:  # Expanding
                    parent_layout.setStretch(i, self._original_stretch_factor)
                else:  # Collapsing
                    parent_layout.setStretch(i, 0)
                break

    def set_collapsed(self, collapsed: bool):
        """
        Programmatically sets the collapsed state of the group box. This should be
        called *after* the group box has been populated with a layout and widgets
        to ensure the initial state is set correctly.

        :param collapsed: True to collapse the group box, False to expand it.
        """
        # Setting the 'checked' state will automatically trigger the `toggled` signal,
        # which in turn calls our _toggle_contents method to update the UI.
        self.setChecked(not collapsed)

    def is_collapsed(self) -> bool:
        """
        Returns the current collapsed state of the group box.

        :return: True if the group box is collapsed, False otherwise.
        """
        return not self.isChecked()