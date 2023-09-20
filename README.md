# QollabEO
## 1. Installation
Before installing QollabEO from the QGIS plugin repository it is necessary to 
install additional packages. Open your OSGeo4W Shell which is located in your
QGIS installation directory, From this OSGeo4W Shell the additional python packages can
be installed using the python package-managment system pip:

``` 
pip install python-socketio[client]
``` 

After sucessfully installing python-socketio you can restart QGIS and install the plugin
from the plugin repository. If no errors occur a new symbol should appear in the toolbar.
Alternatively you can also launch the plugin from Web --> QollabEO --> QollabEO.

Before your ready to use the plugin it is necessary to set additional user metadata. In the installation directory of the plugin there is a config.txt file. Within this file you need to set the two values "MAIL" and "USER". Now your really ready to go.

## 2. Usage

The plugin basically consists of two GUI elements: The main dialog which which consists of three tabs for scheduling, starting and joining a QollabEO session. Additionally there is the meeting dialog which is the interface you will interact with when your within an meeting.

![Alt text](docs/gfx/qollabeo_main_dialog.PNG?raw=true "Title")


### 2.1 Scheduling a meeting
The first tab of the meeting dialog can be used for scheduling meetings. Besides setting the date and time it is also necessary to prodivde an valid email adress; If you added the config.txt in the plugin directory your provided E-Mail is already used. Currently we only need the email for verification. After you set all required parameters you can schedule the meeting by clicking "Schedule". If the session was sucessfully created an URL will appaer in the text field below the button. This is the invitation link: Send this Link to every user who shall participate in the meeting.

### 2.2 Starting a meeting
All future scheduled meetings are displayed in the table in the "Start Session"-Tab. Select the meeting you want to start and click "Start". This will start the meeting. If this was sucessfull, the main dialog is disabled and the meeting dialog is shown. The button in the last column of the table can be used to recreate the invitiation url which you can sent to users who shall participate. Your now ready and can wait for other users to join. 

### 2.3 Joining a meeting
Paste the QollabEO URL which you received from the host into the text field in the
"Join Meeting"-Tab. After clicking "Join" a connection to the server will be established and the meeting gui will be launched. You are now within a session with the host and other users who were invited.

### 3. Functionality
Currently the following functionalities are implemented:

**Synchronisation of WMS layers:**
On starting or joining a meeting a special layer Group called "QollabEO" is created. All **WMS** layers added to this group by the meeting **HOST** will be automatically added to all joined users. The same is true if the **HOST** changes the **visibility** of a layer: This will change the visibility of this layer for all joined users. Limitation: Changing the layer order is currently not automcailly synchronised. If possible this will be added in the future.


**Synchronisation of canvas change:**
If the HOST pans or zooms the map canvas this change is automatically synchronised with all users. Hence, all participants in a meeting see the same map extent (up to a different screen size). Currently this can't be deavtivated which might be obstructive in some situations. See ToDos. 

**Setting and changing the project CRS:**
If the HOST changes hist project CRS, this change is also synhronised with all users. Nevertheless, it is highly recommended that the HOST sets the appropriate project CRS before starting the metting. The CRS of the automatically created "notes" layer in the "QollabEO" layer group is set set to the project CRS when starting a meeting. Hence, if the HOST changes the CRS afterwars there is a mismatch. Furthermore, switching the CRS sometimes appaers to be buggy on the user side.

**Adding features for highlight specific regions:**
As described previously, on starting or joining a meeting a "notes" layer is automatically added to the QollabEO group. Using the "Add rectangle" tool from the meeting dialog each user can draw Rectangles which are automaticalla added to the notes layer. If any user adds a rectangle to this layer is syncrhonised with all users. As long as the button is checked one can create rectangles to highlight certain areas which you find interesting or want to talk about. To deactivate the tool just uncheck the button by clicking it again. A default layer style is used to show only the outlines as well as the name of the user who created the rectangles. There are currently three caveats: i. Only rectangles created after a user has joined the meeting are synchronised. Hence, a user joining later to the meeting will not see any features which have been created before. ii. Features can't be deleted. iii. All rectangles have the same color. All three limitations will be adressed in future releases.

### 4. ToDos

- [ ] Delete features from notes layer
- [ ] Synchronise features which have been created previoulsy before a user joins
- [ ] Fix/improve handling CRS
- [ ] Add possibility to deactivate synchronisation of canvas change events.
- [ ] Zoom to selected feature: If the host/user selects a feature send en event to all users to set the extent to the selected feature.
- [ ] Assign unique colors to each user for feature creation; show the color next to the name in the user list.
- [ ] Remove users from list (HOST)
- [ ] Synchronisation of additional layers beyond WMS.
- [ ] Synchronisation of local layers from an QGIS project

### 5. General remarks
Currently we are using a small development server for running the server part of the QollabEO plugin. Hence, this might lead to problems regarding the scalability to more users. We will monitor the usage of the plugin with respect to our ressources. We might switch (hopefully, as this would mean that the plugin is increasingly used) to more dedicated ressources.

### 6. Funding
This plugin was developed with the SEHAG research project funded by the DFG and FWF. 
