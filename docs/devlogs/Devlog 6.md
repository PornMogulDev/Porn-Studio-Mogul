## **Devlog 6 - December 6, 2025. Indecisions**

I skipped last week's devlog because I only did a couple of things: new trait system and revamped production settings.  

### **Traits**

The talent generation depends on Archetypes, these provide a minimum and maximum range for personality stats (for now only Professionalism and Ambition), scene partners, and concurrency limits (for Action Tags that are concurrent, just Anal and Vaginal at this point). Additionally, they used to provide every preference and hard limit. Now preferences, and other things, like Stress  generation  (more on that later), are determined via traits. The archetype now provides a weight for how likely a certain trait is. For example, it's less likely for a 'kink explorer' to be an 'introvert', than it is for a 'reluctant participant' to be one.  
These traits, along with the main archetype, are now shown on the talent profile view.

Instead of hardcoding the trait name for logic calculations (i.e. 'if talent.trait == "introvert": ...'), I've introduced a 'trait modifier resolver', which unpacks the modifiers listed in the trait data structure so they can be used. I don't know if this will be a sound decision going forward, but it sounds better at this point.  

### **Production Settings**

Production Settings had a couple of issues: their tiered format meant that I had to come up with a price, a quality mod, and a description for every tier of every category; and more importantly, the production modifier for the final quality was very simple and lame: every quality mod of every setting multiplied by each other (sometimes modified by a Thematic Tag), and that final modifier used in the final tag quality calculation.  
The new system is about budget allocation instead. I've introduced Visual Styles (Gonzo, Glossy, Cinematic(?) and hopefully more to come), each having a different budget efficiency, soft cap, weight, and optimum range for each production department, whose quality depends on these. A Gonzo scene, for example, will cap its Set Design quality much earlier than a different visual style, and overspending might incur a penalty instead.   
These will still be then multiplied by each other to get a final production modifier, but I couldn't come up with something more dynamic. Maybe on the next rework, as this implementation had already taken quite a bit of trial and error.

Aside from the production departments, we now also have a crew, aka production jobs: director, producer, cameramen, etc. These are placeholders for now, as we don't have the skills for those positions yet. So it uses the same budget allocation to generate a weighted (depending on the money allocated for their 'salary') random number that also influences the production quality.  
Once actual producers and the like are added, that will be an option alongside hiring an actual character, which will have its relevant skill. We can also add extra modifiers, like the producer skill making it cheaper to hire, or having different affinities for different visual styles.  
I also intend to rework the post-production options to follow this budget allocation system, as well as to include a couple of options in it that directly modify aspects of production (color grading, audio, picture sets, different cuts available depending on number of cameras used, etc), instead of simply having one post-production modifier, but I didn't have time to do it this week, and so I decided to postpone it for whenever I have time, as I wanted to focus on AI studios next.  

### **AI Studios**

I've started very basic: each studio produces four scenes per month (more on that later), with a random quality, directly tied to how much market saturation it generates for the particular viewer group it has focused on. No production settings, no hired talent, no tags.  
As the next step, it should be relatively simple to at least add random (or dependant on a studio archetype) tags with a random quality that then get the full revenue calculation for each viewer group. Which would also help with game balance, seeing how the market functions more long-term without having to manually go all the way.  

I did stop here for now because I wanted to figure out how to implement the 'monthly' checks. They will be useful in the backed, since they will help with breaking up updates to talent and studios consistently. But I think they should also be implemented with a player-facing side. For example, the exclusive contract at the moment has a weekly maximum for scenes, which feels too constricting, as you'd have to be using them every week as to not lose money, but not be able to use them in too many scenes in the same week (maybe not even for a full shooting block). So a monthly limit just seems better.  

The issue is that we have years of 52 weeks at the moment, which would mean 13 months, or we have to bring the number of weeks down to 48 to have the 'normal' 12 months. Whatever I decide, it should be pretty simple to implement with our new absolute week and time formatter. And it should also be simple enough to switch to a different format if that one doesn't feel right.  
I just didn't feel like deciding at that point, so I did something else.  

### **Ethnic Tags**

Something I also didn't end up implementing due to not wanting to decide on it at the moment was a similar builder to the one I created for action tags, this time for 'race-related' ones: individual ethnic ones and interracial.  
I wanted them to take all ethnicities loaded to the database at any time, as well as the genders, and simply create tags with them. This is simple enough for the individual ones: one tag per ethnicity and gender. Maybe we can give some a 'custom' name (like the Ebony or Latina ones), while others remain 'generic' (for example, Western European (Male)).  
The interracial ones are a tad more complicated. First, simply by the cheer number of them: 12 ethnicities (counting both main and sub-groups) and 2 genders mean 300 pairs in total (if we allow pairs of the same ethnicity, which while not technically 'interracial', they are something that makes sense including).  
That would completely overwhelm the Physical Tags UI. We would need at least to create collapsible headers for each category.  

An alternative would be to only have one tag for individual ethnic and interracial, with the game still being able to build all possible combinations, and the player adding whatever performers they want to those generic tags.    
Again, that's simple enough for the individual tag: for each performer in the tag, it adds its appropriate ethnic tag to the scene (averaging the repeated ones). But the interracial one creates issues: at the moment, as opposed to Action Segments, only one instance of a tag can be added in the Physical side. We would need to create a new tab for Interracial or change how the Physical tags are handled entirely to allow for more instances. Or the tag, once added, could have its own UI, similar to the Action Segments ones, where the player creates different 'groupings' of performers that the game will then try to make sense of. We could give visual feedback here: *This grouping will create a Black Male / White Female tag for this scene.*; or *This grouping doesn't fit any possible Interracial combination.*, etc.  

Again, I didn't feel like setting on anything. Adding collapsible headers for the tags seems like a good idea in any case, and the builder will have to be made anyway because the game will need to know what tags are available, whether the player can directly choose them or not. So I will be adding them soon enough.  

### **UI/UX Improvements**

I did implement several things this last week.  
I created a sort of hyperlink system, in which everywhere a Talent alias is visible (except for the Scene Planner cast side), it can be ALT-clicked to bring up that Talent's profile view. The system also includes a tooltip side, which for the moment simply wraps the details widget side of the Talent profile view, but which can be further refined down the line.  

I've also introduced an icon manager and added several custom (as in not Qt-default, but not created by me) icons.  
Flag icons have been added everywhere the Talent's nationality is displayed, and game icons have replaced the Qt-default ones pretty much everywhere. These new custom icons resize according to the font size selected, and in the case of the game icons (i.e. not the flags), they follow the theme's colors.  
The social media icons in the Start Screen still follow their previous behaviour, since they have custom logic for resizing and for having embedded links, but I might make them work via the icon manager in the future as well.  

Additionally, the introduction of icons made me go back to the licensing flow I had set, which was too involved for my liking, and created a couple of scripts to further automate it.  
I've also been going over each game file individually, improving its documentation and creating test units where appropriate. Still a long way to go here, and by the time I've completed a few, some I had already had a pass at will have been modified, but it is a worthwhile effort, if simply to actually know the codebase.  

So this week I'll expand on the AI Studios and create the ethnic tag builders while keeping the codebase review going. I'm thinking about releasing the next build around the 20th-23rd.