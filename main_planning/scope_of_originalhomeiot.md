The main scope of this project  OriginalHomeIOT platform:
1. It has to be an IOT platform suitable for home use
2. It has a component that can be installed on a local gateway (Rpi / Olinuxino supported at the beginning)
3. It has a component that can run in the cloud on a bigger server
4. It has the ability to only run locally.
5. It can be linked to a local database (more limited) or a clud/server database or even both as the client chooses
6. It has a local UI that can be viewed on the local network or via vpn (like tailscale)
7. It also has a cloud UI when the cloud connection is available

The main OriginalHomeMain: OHM
1. Accepts various sensors via mqtt
2. A sensor should be extremely easy to be added: 
    aimed at technical people
    mqtt topic will be manually introduced
    sensor json will be discovered and each field coupled as follows next:
3. The platform defines a range of "virtual sensors" - already premade entities that 
can be linked to real devices: temperature sensor, humidity sensor, CO2 sensor, NOX sensor, Plug_Power_Meter, 
motion sensor, light intensity sensor
4. The platform defines as well a range of "virtual actuators" like: smart switches, ir smart ac controllers, rgb indiviual bulbs, 
rgb strips, 
5. Efforts will be made such that existing physical sensors / actuators products can be integrated in OriginalHomeMain
6. The UI must be able to have a 3D minecraft-like sandbox in which the house can be visually modeled by the owner.
The square precision must be selectable between 1m / 50cm. A general roof will cover the building after all.
7. All the sensors / actuators can be therefore associated to a room modeled in 3D.

One of the most important modules of this platform is the ENERGY MANAGEMENT MODULE:
"Original Energy Management Module" -> OEMM
1. Must be based on Open Energy Management System 
2. A beautiful interface with easy controls of the energy strategies must exist -> can be even OpenEMS UI
3. This module will be basically a wrapper over the OpenEMS.

Another important module is the "Original Camera Security Module": OCSM
1. It should discover and add IP cameras connected via local network
2. Has full management of the cameras: add, edit, remove
3. Has a people movement recognition algorithm for each camera
4. Can be armed or disarmed
5. When armed, if 1, 2 or more cameras detect people movement, a 1 or 2 level alarm must be fired
6. Level 1 alarm will only trigger some basic lights turn on
7. Level 2 alarm can enable more advanced features like sounds or more lights.

Another Module is "Original Data Analysis Module": ODAM:
1. This gathers all the data of the platform
2. It stores decoupled data (data with timestamp) in various tables
3. It can be enhanced by machine learning algorithms 
4. It can offer predictions of the expected behaviours: lights or temperature states based on existing motion and many others.

Another Module is "Original Intelligent Assistant":
1. Can communicate to the other modules of course
2. Can organize scenarios
3. Can communicate by voice to the user
4. Can execute commands like: make the room warmer, is it warm enough at home, etc...


Very important!!!!
All modules are decoupled and exchange information via mqtt.
They expose endpoints for setting / getting data and status.