<span style="color:grey"><i>Written on version ???. Updated on version 0.6.0</i></span>  

---

The Shooting Block is meant to simulate the fact that studios usually hire a crew, a location, equipment, etc to shoot a bunch of scenes. Realistically, also performers.

It has been heavily reworked from a tiered system, with fixed price and quality bonus/malus to the current one about budget allocation and effectiveness curves in this last cycle.   

Right now, there is no maximum number of shooting blocs that the player can book for any given week. There should probably be, once I figure out how the player avatar will function. I am leaning towards individual producer with some unique fatigue or stress system. Perhaps, once the AI studio implementation is more complex, it could also be possible for the player to hire other producers, give them a rough outline of what they want, and the AI creating a scene following those, with a logic similar to that of the AI studios.  

Production departments take money and get a quality, affected by their effectiveness curves and soft caps, which are further refined depending on the visual style.  

The crew positions are still placeholders, since I haven't introduced the required skills or talent roles for it yet. All talent should have every skill, to represent the fluid nature of the porn industry when it comes to different people performing several roles at any point and over their careers.  
The current implementation, where the crew follows the production department budget allocation system, should probably stay, in case the player doesn't want to hire a particular character for it.  

All these qualities have different weights, default and depending on visual style (and per scene, depending on thematic tags) to determine the final production quality, which affects the physical and action tag qualities of every scene in the block.  

The number of cameras has an extra function, as it interacts with the editing in post-production: many cameras and poor editing give a malus, many cameras and good editing give a big bonus, etc. Down the line, once all the 'camera types' are properly implemented and the post-production and release processes are revamped, I intend there to be a way for the player to be able to release different 'camera angle' versions of scenes.  

Picture Set is going to affect the marketing quality, once that is implemented. But at the moment it is a plain malus, as an active setting (i.e. not Video Grabs) reduces Set Momentum and increases Stress.  

Set Momentum is a new mechanic, meant to represent how 'focused' everyone is in their task. It gives fluffers a purpose, as scenes with many performers but a low Set Support budget will tank momentum, while scenes with few performers should have a base high momentum but won't benefit much from having a fluffer budget. Stopping the shot for dedicated pictures is going to lower momentum, and more stuff I can't think of at the moment. These interactions aren't implemented yet, but that's the idea.  
Similarly, Stress is the mental counterpart to the Stamina system. Working different crew positions and performing will increase stress, performing a task that they aren't very good at will increase it, departments like catering and health, safety, and security will lower it, etc.  

Many departments (catering, wardrobe, and makeup...) should realistically take into account the number of performers, which should be doable without much pain, since their effectiveness is re-calculated per scene. So simply informing the player here that the quality of those will vary depending on the total number of performers should be enough.  