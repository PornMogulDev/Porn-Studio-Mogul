<span style="color:grey"><i>Written on version ???. Updated on version 0.6.0</i></span>  

---

Typical inbox with typical inbox behaviour.  

This is the only view in the game that uses the `revert_geometry_button`. The button was implemented early in development, when the UI was intended to rely heavily on modeless dialogs. At the time, the idea was to use the OS window snapping features (at least in Windows 11) to approximate a splitter-style layout by arranging multiple dialogs side by side.  
In practice, this approach did not work as expected. Non-main application windows are significantly more restricted, and the OS cannot meaningfully manage or snap elements of the same window against each other. So it will most likely be abandoned if that overall UI idea is as well.  

Right now, there is the `Welcome!` email, originally created with the inbox to see if the system was working properly. I think would be a nice little tutorial in the end, probably would need to add a setting to disable it, just so non-first-time players don't have to delete it every time they start a new game.  

And there are also the market discovery and Talent in Go-To List Tour ones. These make use of Jinja2, since they make use of variables and conditionals that would require complex string concatenation otherwise.  
Later, we could add a setting (similar to Paradox's games), where it is possible to right-click certain notifications and emails and change their 'importance', changing the mode in which they are received. As well as a tab in the settings dialog to modify everything related with this.  
The Tour email, since it mentions a Talent, supports the tooltip plus ALT+Lef-Click behaviour to open the Talent's Profile. This should be expanded to Viewer Groups and AI Studios (when they can sponsor tours themselves) as well at some point. 