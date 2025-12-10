src/
  app/                
    application.py          
    main_window.py
    start_screen.py      
  core/               # Core game logic and orchestration
    game_controller.py   # Central game state mediator
    game_signals.py      # Global application event signals
    interfaces.py        # Controller interface definition
    notifications_manager.py # Manages on-screen notifications
    service_container.py # Handles service layer DI
    talent_generator.py  # Procedurally creates new talent
  data/
    data_manager.py     
    game_state.py
    save_manager.py
    settings_manager.py
  database/
    db_manager.py
    db_models.py
  services/
    builders/
    calculation/
      bloc_cost_calculator.py      # Calculates cost of shooting blocs
      bloc_simulation_calculator.py # Calculates initial conditions and post-shoot deltas for bloc simulation
      bulk_booking_validator.py    # Gatekeeper for hiring in bulk
      crew_skill_calculator.py     # Rolls quality/skill for bloc resources and crew
      market_group_resolver.py     # Resolves market group inheritance
      post_production_calculator.py # Applies post-production quality effects
      revenue_calculator.py        # Calculates final scene revenue
      role_performance_calculator.py # Calculates role-based performance modifiers
      scene_quality_calculator.py  # Final arbiter for scene quality
      shoot_results_calculator.py  # Calculates talent outcomes after shoot
      tag_validation_checker.py    # Validates and discovers physical tags
      talent_affinity_calculator.py # Recalculates talent age affinities
      talent_availability_checker.py # Checks if talent will do a role
      talent_demand_calculator.py  # Calculates talent hiring costs
      upfront_tour_cost_calculator.py # Calculates upfront tour costs
    events/
    models/
    query/
    game_session_service.py      # Manages game save/load lifecycle
    market_service.py            # Handles market saturation/discovery
    player_settings_service.py   # Manages player-specific settings
    time_service.py              # Orchestrates weekly game progression
    tour_feasibility_service.py  # Checks if a tour is possible
    tour_sponsorship_preview_service.py # Gathers data for tour preview
   tests/
   ui/
     builders/
     dialogs/
     mixins/
     models/
     presenters/
     tabs/
     widgets/
     windows/
     theme_manager.py
     ui_manager.py
     view_models.py
   utils/
     formatters.py
     logger_setup.py
     paths.py
   debugger.py
   main.py
        
       
