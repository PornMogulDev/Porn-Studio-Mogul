This is a text-based management game (aka spreadsheet simulator) about the porn industry. Produce scenes, from pre-production to distribution, handle and interact with talent.

The core game loop consist of setting up a shooting bloc, which contains several scenes, design the content of said scenes, hire the talent for them, shoot, release, repeat.

Both the market and the talent are dynamic and evolve with time and the actions of the player and the AI.

It will hopefully interest both usual players of management games and of porn games (although the game won't feature anything more 'titillating' than numbers going  up).

I love management games and playing TEW 2016 and being unable to run a full 'risqué' company made me really want to play something like this. The many abandoned games like this one over the years and the new possibility of making this without actually knowing how to code has pushed me to finally try.

Mainly, I'm taking inspiration from TEW, FM, Hollywood Mogul, and Free Cities.





The game uses two main tools; PyQt6 for the UI and SQLAlchemy for database. UI, data, persistence, gameplay.

Player interacts with UI -> UI sends signals to presenters -> presenters call controller façade methods -> controller passes the request to the services -> services perform data queries -> data layer provides the data -> services perform calculations on said data -> results travel the opposite way.



Scene Planner



