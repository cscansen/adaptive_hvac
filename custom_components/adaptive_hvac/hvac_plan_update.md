Adaptive HVAC needs a rethink. 

##components:
System

What goes into system: global controllable options, think heat/ac options. 
season: summer/winter
seasoal temp targets:
summer cool target: deg f
winter heat target: deg f
exterior temp target (
    cut off for AC in summer: deg f (if exterior temp is say  less than <configurable temp>, AC can turn off)
    cut off for heat in summer: deg f (if exterior temp is greater than <configuratable temp>)

Windows open: a single entity or group (helper) where if any window is open system is off (this protects against i want the windows open because its a nice (50 degree winter day, we might air the house out), or its nice and cool this evening, the windows are open.

Exterior temp (optional entity)
Exterior weather (current weather) optional



If a user changes the thermostat by the control on the faceplate OR the app, THAT is your new automation / threshold target (allow the panel to update the target temp.


Zones: 
Name: eg: upstairs
Available cooling devices (allow for/account for window aC units if applicable)
Target room temp: deg f slider
Window sensors (if applicable)



If summer and over target temp use passive cooling
if winter and under target use passive cooling 


QUESTIONS/HELP: how do we avoid race conditions if multiple zones are outside (up or down) the target threshold? Can zones impact cooling or cooling decisions or do we leave that exclusively to the "system" area? If a single zone home (like mine) i dont want to heat downstairs to <temp> and freeze out upstairs...reverse that in summer where i cool the downstairs and upstairs is still sweltering. 

What am i forgetting/not asking? 