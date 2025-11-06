from typing import TYPE_CHECKING

from core.interfaces import IGameController

if TYPE_CHECKING:
    # This avoids a circular import at runtime but allows for type hinting
    from ui.dialogs.shooting_bloc_dialog import ShootingBlocDialog

class ShootingBlocPresenter:
    """
    Handles the logic for the ShootingBlocDialog, acting as an intermediary
    between the view and the game controller/services.
    """
    def __init__(self, controller: IGameController, view: 'ShootingBlocDialog'):
        """
        Initializes the presenter.

        Args:
            controller: The main game controller, providing access to services.
            view: The dialog instance that this presenter will manage.
        """
        self.controller = controller
        self.view = view

    def load_initial_data(self):
        """
        Performs the initial setup of the view by loading default settings
        from the last session and calculating the initial cost display.
        This should be called from the view's __init__ after UI setup.
        """
        self._load_and_apply_defaults()
        self.request_cost_update()

    def _load_and_apply_defaults(self):
        """Loads the last used settings from the settings manager and tells the view to apply them."""
        last_settings = self.controller.settings_manager.get_setting("last_shooting_bloc_settings", {})
        if last_settings:
            # The view is responsible for knowing how to apply these settings to its widgets.
            self.view.apply_defaults(last_settings)

    def request_cost_update(self):
        """
        Gathers current selections from the view, requests a cost calculation
        from the controller, and tells the view to update its display. This method
        is connected to all the view's value-changed signals.
        """
        selections = self.view.get_current_selections()
        
        # Unpack the dictionary from the view into the arguments the controller expects
        num_scenes = selections.get('num_scenes', 1)
        prod_settings = selections.get('production_settings', {})
        policies = selections.get('policies', [])
        
        calculated_cost = self.controller.calculate_shooting_bloc_cost(num_scenes, prod_settings, policies)
        self.view.set_total_cost_display(calculated_cost)

    def confirm_plan(self):
        """
        Gets the final selections, saves them for next time, and tells the controller
        to create the shooting bloc. If creation is successful, it closes the dialog.
        This method is connected to the view's 'accept' button.
        """
        # 1. Get final selections from the view.
        selections = self.view.get_current_selections()
        
        # 2. Save the relevant settings for the next time the dialog is opened.
        settings_to_save = {
            "production_settings": selections.get("production_settings", {}),
            "policies": selections.get("policies", [])
        }
        self.controller.settings_manager.set_setting("last_shooting_bloc_settings", settings_to_save)
        
        # 3. Extract arguments and call the controller's creation method.
        week = selections.get('week')
        year = selections.get('year')
        num_scenes = selections.get('num_scenes')
        name = selections.get('name')
        prod_settings = selections.get('production_settings')
        policies = selections.get('policies')

        # Basic validation (as a safeguard)
        if not all([week, year, num_scenes, prod_settings is not None, policies is not None]):
            self.controller.signals.notification_posted.emit("Error: Missing data for shooting bloc creation.")
            return

        success = self.controller.create_shooting_bloc(
            week=week,
            year=year,
            num_scenes=num_scenes,
            settings=prod_settings,
            name=name,
            policies=policies
        )
        
        # 4. If the creation was successful, the presenter tells the view to accept and close.
        if success:
            self.view.commit_and_close()
        # If not successful, the dialog stays open. The controller/service is responsible for
        # posting a notification to inform the user what went wrong.