## **Devlog 4 — November 15, 2025. Locations, Expanded Ethnicities, and Hiring System**  

The more features I add, the more I realize I'm basically copying TEW and adapting it to porn.  

This week was fairly eclectic. Beyond fixing issues from the latest test build, I made improvements to the talent filter. You can now hide each category individually, including the new Location and Nationality filters. I also reworked the cup-size selector to match the dick-size one, using a custom spin box and range slider that map an index to the appropriate cup value. This does remove the ability to filter by non-consecutive sizes, but realistically I don't think many players would use that, and it should be fast enough to instead do a couple of searches. The slider excels at the use case people do care about, takes significantly less space, and looks more consistent, so I consider it a positive change.  

---

### **Locations, Nationalities, and Expanded Ethnicities**  

I've added talent Nationalities and Locations, and expanded the ethnicity system. Previously, ethnicity lumped together both nationalities and ethnic groups because it was originally meant only as a viewer-preference tool. That worked fine, but I've realized that having a more realistic and differentiated system is important for this type of game, or at least it's important to me as an enjoyer of this type of game.  
The implementation is minimal for now: I added the nationalities most common in the global porn industry and expanded the ethnicity categories from the 'big four' (White/Caucasian, Latin, Black, Asian) into a more granular custom structure. The goal is to capture the groups that are typically fetishized, how they contrast with one another, and how they relate to the nationalities currently implemented.  

Locations should also help with plausibility and world-building. Talents will move around; going on tours, relocating (eventually, based on work availability and relationships), and giving the player more to consider during the hiring process.  
The whole system is expandable. More nationalities and ethnicity sub-groups can be added easily, and locations may eventually drill down from countries to cities or regions (as is already the case with the US).  

Both locations and ethnicities now have a hierarchy; Parents: regions or main ethnicities; Children: specific locations or sub-groups.  
Regions always contain locations (since they aren't locations themselves). Most main ethnicities do not have sub-groups; those that do act purely as buckets (i.e. there are no talents marked simply 'Asian', each belongs to a specific sub-group). The ethnicity picker for performers in the Scene Planner supports selecting either main or sub-groups and handles the bucket logic automatically.  

Talent generation now works as follows: Choose Gender and Nationality (global weights) → Choose Location (based on Nationality) → Choose Ethnicity (based on Nationality) → Choose Alias (based on Nationality and Ethnicity).  

This was the core work planned for the week, and I finished it faster than expected. Most of the effort went into building the data structures for the new variables and updating affected UI views, including the filters. After that, I began work on the expanded hiring system (scheduled for this upcoming week) and started prototyping the dashboard design Heniss suggested.  

---

### **Expanded Hiring System**  

The new location system requires a more complex hiring system, and that's coming along well. I'd estimate I'm about halfway done.  

I created a travel matrix, assigning money and fatigue costs for each region-to-region trip.  
I also reworked the fatigue system. Previously, recovery time per fatigue point was fixed (and set to 0, so it didn't matter). Now fatigue functions as a pool. Gains per scene are still based on stamina-pool overdraw, and now travel adds its own fatigue cost. Fatigue decays through two conditions; Passive recovery: low, ticks first on turn advancement; Active recovery: high, requires the talent not to work that week.  
Both rates are modified by the talent's stamina level. This gives the player another variable to consider when hiring.  

Talents themselves now also 'understand' their schedules and fatigue levels. They will refuse bookings if it would push them past a scene-per-week threshold or exceed their fatigue tolerance. These thresholds are currently affected by Ambition, but I plan to introduce either a trait system or an expanded personality-archetype system. This would govern things like how much they like traveling, their willingness to move to certain regions, and how many scenes they'll accept over a given timespan.  

Still to come: actual touring mechanics and exclusive contracts.  

Touring should be simple for now: talents may initiate a tour on their own (players with them shortlisted get an email), or the player can 'sponsor' a tour by offering several scene contracts over 1–4 weeks, with an appropriate discount.  
Exclusive contracts existed briefly in an early version of the game, but I removed them when I reworked scene planning and preference systems. With the new complexity, contracts will need more robust logic: checking and setting limits, expected scene content, number of scenes, weekly salary, and duration.  

Hopefully I'll finish this next week and start on the User Avatar.  

---

### **Dashboard Views**

I'm building a hiring dashboard based on Heniss' proposal. If I didn't care about proper architecture and just dumped everything into a single file, it would already be done — but that defeats the purpose of prototyping correctly. Each widget needs its own logic and view, and there also needs to be a connector that coordinates interactions between components (e.g., the talent filter and talent table).  

The plan is to recycle and adapt as much existing code as possible, so hope I'll have something to show soon.  