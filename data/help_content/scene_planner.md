<span style="color:grey"><i>Written on version ???. Updated on version 0.6.0</i></span>  

---

The Scene Planner is where the player designs the content they will shoot.

### The Details  

The number of performers that will appear in a scene, as well as some of their attributes, which will determine their eligibility for Physical tags and Action Segments' roles. Their Disposition selection is only relevant (and available) when the scene has a Dom/sub dynamic at play, and will make the Talent's Dom (if in a Dominant disposition), Sub (if in a Submissive disposition), or both (if in a Switch disposition) skills contribute to the Action tags quality. 

'Performer 1', 2, etc, are the default, but they are customizable to make it easier to remember who is who, and I guess for immersion's sake.  
Why aren't we hiring/assigning the talent first, and then creating the scene with them directly involved? I feel like if we want different demands, hard limits, etc, this way it's more robust and simpler in the end.   

Protagonist gives the performer a highest weight in the tag quality calculation relative to non-protagonists (so if everyone is a Protagonist, it will cancel out). I plan to expand this by potentially giving Protagonists a boost or penalty to their overall performance depending on their personality, to simulate some kind of 'spotlight pressure'. And also by adding extra related roles, like 'Background', 'Cameo', etc.  

### The Tags

Both Physical and Action tags have an Appeal Weight (hidden, but hopefully intuitive). This determines their importance when it comes to calculating the Scene Appeal for a Viewer Group. They could instead use a value chosen by the player, but I believe that it makes more sense like this; for example, something involving 'extreme' acts (watersports, scat, blood, etc), will have a large impact on the viewer's perception of and willingness to engage with a scene, no matter how little of the total runtime of a scene it might take up. While the fact that a scene has vaginal penetration won't matter much to most viewers.  

**• Action Tags**  
The quality of Action Segments is in principle determined by the performers' Performance and Acting skills (in a 70/30 split). Although this can be changed by Thematic tags.  

Unlike the other two types, the player can add the same Action Tag to a scene as many times as they like. Although the difference between most tags being added a couple of times or simply having every performer that will take part in it in the same segment is null, as long as the runtime percentages are the same in the end. I.e. if you want two pairs of male/female talent performing a Vaginal tag, the end result will be the same by having two different Segments with each pair at 10% each, than having one segment with 2 Receivers and 2 Givers at 20%. Only when the tag has the 'concurrently' category does it make a difference at the moment, as it is meant to simulate a Double/Triple penetration.

Now, does it make sense that one pair going at it for 5 minutes, and then a different pair doing the same to be considered the same as both doing it at the same time for 10 minutes? No, it doesn't. But this is what I have at the moment.  

Many of the tags are built at runtime for the different orientations that it should support from a template. For example, Anal is a tag that has receiver and giver roles, both of which are set to 'Any' gender, and it's given the Straight, Gay, Lesbian, and Bi orientations. The builder then builds one instance of the tag for each orientation, making sure that the Gay one has 'Male' as the gender requirement for both roles, the Lesbian one does the same with 'Female', the Bi one doesn't care either way, and the same for the Straight one, which is then checked by the actual Planner depending on the first assigned role.  

**• Physical Tags**  

Physical tags will be added automatically to a scene ('Auto') if they aren't chosen by the player ('Focused'), and have a lower weight in this Auto mode. Instead of calculating its quality (which for most Physical tags consists of checking the talent's physical affinity for that tag and a smaller part testing their Acting skill), it defaults to a fixed 100. Instead of this, I think it should work by simply taking into account the physical affinity relevant for the tag, and also checking how many tags of the same type there are present in the scene, and doing something with that. For example, a scene with two female performers with a 75 affinity for MILF and no other 'competing' tag (like Teen (Female)) would have a higher appeal than one with the same two performers but also 3 Teen (Female) affinities. But what if the Viewer Group also likes them? I don't know. That's why I have left that placeholder quality.

The Focused mode, on the other hand, will have a higher weight and will take into account the Acting skill to simulate how the scene is 'playing up' everything associated with the tag, as opposed to being simply a physical trait that the viewers will notice.  

The ethnic tags, either individual and pair ones, also use a runtime builder. The amount of ethnicities and possible combinations has made the number of tags explode, which has necessitated the implementation of collapsible category headers, for now only used in the Physical tags list, but which will probably be extended to the other two.  
As an alternative to the many tags, we could simply have one for individual ethnicities and one for pairs, this one getting a UI similar to the one for Action Segments where several groupings can be made and which the game automatically determines and shows what type of pair it is.  

**• Thematic Tags**  

Thematic tags are special, as they don't have a quality of their own, but will instead have scene-wide modifiers. They might make the Dom/sub dynamic more important, give a higher weight to Performance or Acting in the calculation splits, make some Production Setting more important for the quality calculation, etc.

For example, selecting the 'Fishnets' tags doesn't just mean that some Performer is wearing fishnets (that's why it isn't a Physical Tag), maybe at some point there will be a more detailed wardrobe system where the player choose what everyone is wearing for the scene, but for the moment, the 'Fishnets' tag implies that fishnets are a focal point of the scene; the camera lingers on them, Performers caress them, they stick their dick thru the holes, etc. Or, mechanically, they add 5% to the Acting weight and make the malus or bonus (assuming there is one) to quality from the Wardrobe setting 20% stronger.  

So what is the difference between 'Raceplay' and 'Interracial (x/x)', or between 'Dick Worship' and 'x Dick'? I would say that Thematic Tags are all-encompassing, where everything happening in the scene is filtered thru its lens, while Physical ones simply feature more prominently a physical aspect. In a Dick Worship scene, the camera will shoot it from below, the performers will act differently around it, and more that I can't come up with at the moment, while a scene with Big Dick (Male), will have a bit with the girl measuring it against her forearm and the camera will try to get the best angles to make it look big. I don't know, maybe it doesn't make sense to have this separation.

At this moment, this leads to Physical Tags potentially having a higher impact in the scene than Thematic ones, specially when the scene has very few tags. Which I don't know how to feel about.