# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QDateTime, Qt, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QHeaderView, QTableWidgetItem, QApplication, QPushButton, QMessageBox

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .qollabeo_dialog import QollabEODialog
from .qollabeo_meeting_dialog import MeetingDialog
from .tools.rectangle_tool import RectangleMapTool
import os.path
from .util import create_quarter_strings, get_current_from_to
from datetime import datetime, timedelta
import sqlite3

from qgis.core import QgsPointXY, QgsCoordinateReferenceSystem, QgsProject, QgsCoordinateTransform, QgsRasterLayer, QgsVectorLayer, QgsField, QgsFeature, QgsGeometry
from qgis.gui import QgsMapToolPan

#users might not have installed socketio prior to qollab; While we can't avoid an error due to the missing import
#we can provide a customized error message in order to show that we are aware of this problem;
try:
    import socketio
except ImportError:
    err_msg = "Socket.io not found. Please install socket.io before installing QollabEO: pip install python-socketiot[client]\nFor more help visit https://github.com/smfloery/qollab"   
    print(err_msg)
    raise ImportError(err_msg)

class QollabEO:
    """QGIS Plugin Implementation."""
    
    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """        
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        
        self.sid_db_path = os.path.join(self.plugin_dir, "sid.db")
        sid_db = sqlite3.connect(self.sid_db_path)
        db_cur = sid_db.cursor()
        db_cur.execute("CREATE TABLE IF NOT EXISTS sessions (mail text NOT NULL, title text NOT NULL, rid text NOT NULL, pwd test NOT NULL, from_time timestamp, to_time timestamp);")

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&QollabEO')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        
        #these events appaer to run on a different thread; hence, they can't
        #directly interfere with QT; Propper solution would be to use QThreads and Workers?
        #for the moment we define additional pyqt signals which are emited when the 
        #socketio signals are emitted: .\qollabeo_client_dialog.py before init
        self.sio = socketio.Client(ssl_verify=False, reconnection=True, reconnection_attempts=3)
        
        self.sio.on("connect", self._on_connect, namespace="/schedule")
        self.sio.on("disconnect", self._on_disconnect, namespace="/schedule")
        self.sio.on("connect_error", self._on_connect_error, namespace="/schedule")
        self.sio.on("session_created", self._on_session_created, namespace="/schedule")
        
        self.sio.on("connect", self._on_connect, namespace="/start")
        self.sio.on("disconnect", self._on_disconnect, namespace="/start")
        self.sio.on("connect_error", self._on_connect_error, namespace="/start")
        self.sio.on("session_started", self._on_session_started, namespace="/start")
        self.sio.on("start_failed", self._on_start_failed, namespace="/start")
        self.sio.on("room_entered", self._on_room_entered, namespace="/start")
        self.sio.on("room_left", self._on_room_left, namespace="/start")
        self.sio.on("feat_added", self._on_feat_added, namespace="/start")
        
        self.sio.on("connect", self._on_connect, namespace="/join")
        self.sio.on("disconnect", self._on_disconnect, namespace="/join")
        self.sio.on("connect_error", self._on_connect_error, namespace="/join")
        self.sio.on("session_joined", self._on_session_joined, namespace="/join")
        self.sio.on("join_failed", self._on_join_failed, namespace="/join")
        self.sio.on("user_list", self._on_user_list, namespace="/join")
        self.sio.on("room_closed", self._on_room_closed, namespace="/join")
        self.sio.on("room_left", self._on_room_left, namespace="/join")
        
        self.sio.on("extent_changed", self._on_extent_changed, namespace="/join")
        self.sio.on("crs_changed", self._on_crs_changed, namespace="/join")
        self.sio.on("vis_changed", self._on_vis_changed, namespace="/join")
        self.sio.on("lyr_added", self._on_lyr_added, namespace="/join")
        self.sio.on("lyr_removed", self._on_lyr_removed, namespace="/join")
        self.sio.on("feat_added", self._on_feat_added, namespace="/join")
        
        config_dict = {}
        with open(os.path.join(self.plugin_dir, "config.txt"), "r") as config_file:
            for line in config_file:
                k,v = line.rstrip("\n").split("=", 1)
                config_dict[k] = v

    
        self.url = config_dict["URL"]
        self.sio_path = config_dict["SIO_PATH"] 
        self.email = config_dict["MAIL"]
        self.name = config_dict["USER"]
        self.role = None
        
        self.pan_tool = QgsMapToolPan(self.iface.mapCanvas())
        self.rect_tool = RectangleMapTool(self.iface.mapCanvas(), self.name)
        
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('QollabEO', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToWebMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/QollabEO/gfx/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'QollabEO'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginWebMenu(
                self.tr(u'&QollabEO'),
                action)
            self.iface.removeToolBarIcon(action)

    def emit_msg_to_server(self, msg_type=None, msg_data=None, nspace="/"):
        self.sio.emit(msg_type, msg_data, namespace=nspace)
    
    def canvas_changed(self):
        
        zoom = self.canvas.scale()      #float
        cx_pnt = self.canvas.center()   #QgsPointXY
        
        change_msg = {"zoom":zoom,
                      "cx": cx_pnt.x(),
                      "cy": cx_pnt.y()}
        
        self.emit_msg_to_server(msg_type="set_extent", msg_data=change_msg, nspace="/start")
            
    def crs_changed(self):
        crs = self.canvas.mapSettings().destinationCrs()
        crs_wkt = crs.toWkt()
        
        change_msg = {"crs":crs_wkt}
        
        self.emit_msg_to_server(msg_type="set_crs", msg_data=change_msg, nspace="/start")
        
    def remove_host_handlers(self):
        #necesary as otherwise error is thrown when dlg closed multiple times after another;
        #with try:except everything appaers to be working
        try:
            self.canvas.extentsChanged.disconnect(self.canvas_signal_extent)
            self.canvas.destinationCrsChanged.disconnect(self.canvas_signal_crs)
            
            self.lyr_grp.willAddChildren.disconnect(self.grp_pre_add_event)
            self.lyr_grp.addedChildren.disconnect(self.grp_add_event)
            self.lyr_grp.visibilityChanged.disconnect(self.grp_vis_event)
            self.lyr_grp.willRemoveChildren.disconnect(self.grp_pre_rem_event)
            self.lyr_grp.removedChildren.disconnect(self.grp_rem_event)
        except:
            pass
    
    def dlg_closed(self):
        self.disconnect_from_server()
        self.remove_host_handlers()

    def _on_vis_changed(self, data):
        self.dlg.qtsig_vis_changed.emit(data)
        #currently its not possible to emit a signal if one layer was moved withn the group;
        
    def vis_remote_lyr(self, data):
        lyr = self.qgis_project.mapLayersByName(data["name"])
        if len(lyr) == 1:
            #necessary as mapLayersByName returns QgsRasterLayers which does not have th setItemVisibilityCheked attribute
            self.lyr_grp.findLayer(lyr[0].id()).setItemVisibilityChecked(data["is_visible"])
            
    def _on_lyr_added(self, data):
        self.dlg.qtsig_lyr_added.emit(data)
    
    def add_remote_lyr(self, data):
        lyr = QgsRasterLayer(data["source"], data["name"], 'wms')
        self.lyr_grp.insertLayer(int(data["tix"]), lyr)
        self.qgis_project.addMapLayer(lyr, False)
    
    def _on_lyr_removed(self, data):
        self.dlg.qtsig_lyr_removed.emit(data)
    
    def remove_remote_lyr(self, data):
        lyr = self.qgis_project.mapLayersByName(data["name"])
        if len(lyr) == 1:
            self.qgis_project.removeMapLayer(lyr[0].id())

    def _on_session_created(self, data):
        
        #store created session also locally in sqlite3 database;
        sid_db = sqlite3.connect(self.sid_db_path)
        db_cur = sid_db.cursor()        
        db_cur.execute("""INSERT INTO sessions(mail, title, rid, pwd, from_time, to_time) VALUES (?,?,?,?,?,?);""", (data["mail"], data["title"], data["rid"], data["pwd"], data["from_time"], data["to_time"]))
        sid_db.commit()
        
        self.dlg.qtsig_created.emit(data)
        self.disconnect_from_server()

    def add_session_info_to_gui(self, data):
        self.dlg.input_url.clear()
        url_str = self.url + self.sio_path + "?%s?%s" % (data["rid"], data["pwd"])
        self.dlg.input_url.setText(url_str)
        self.show_message("Sucessfully created session.", level="success")
        
    def copy_to_clipboard(self, copy_str=None):
        cb = QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        
        if copy_str is None:
            cb.setText(self.dlg.input_url.toPlainText(), mode=cb.Clipboard)
        else:
            cb.setText(copy_str, mode=cb.Clipboard)
            
        self.show_message("Url copied to clipboard.")
        
    def _on_session_started(self, data):
        print("Connected to room %s." % data["rid"])
        self.role = "HOST"
        self.dlg.qtsig_started.emit(data)
    
    def _on_session_joined(self, data):
        print("Connected to room %s." % data["rid"])
        self.role = "USER"
        self.dlg.qtsig_joined.emit(data)
    
    def _on_room_entered(self, data):
        self.dlg.qtsig_entered.emit(data)
    
    def _on_extent_changed(self, data):
        self.dlg.qtsig_extent.emit(data)
    
    def set_extent_from_remote(self, data):
        self.canvas.setCenter(QgsPointXY(data["cx"], data["cy"]))
        self.canvas.zoomScale(scale=data["zoom"])
        self.canvas.refreshAllLayers() 
                    
    def _on_crs_changed(self, data):
        self.dlg.qtsig_crs.emit(data)
    
    def set_crs_from_remote(self, data):
        
        curr_cntr = self.canvas.center() 
        
        old_crs = self.canvas.mapSettings().destinationCrs()
        old_crs_wkt = old_crs.toWkt()
        
        new_crs_wkt = data["crs"]
        
        if old_crs_wkt != new_crs_wkt:
            choice = QMessageBox.question(self.meeting_dlg, 'Change CRS?',
                            "The host asks you to change your CRS.",
                            QMessageBox.Ok)
            
            if choice == QMessageBox.Ok:    
                new_crs = QgsCoordinateReferenceSystem()
                new_crs.createFromWkt(new_crs_wkt)
                self.qgis_project.setCrs(new_crs)
                
                #necessary as otherwise the somethings wrong with the new center
                #on the client side, hence, we manually set the center;
                tr = QgsCoordinateTransform(old_crs, new_crs, self.qgis_project)
                tr.transform(curr_cntr)
                self.canvas.setCenter(curr_cntr)
        
        #add memory layer for storing "notes" when user is NOT host; this is done after
        #the user was asked to change his CRS to make sure its the same as the HOST
        mem_lyr = QgsVectorLayer("Polygon?crs=%s" % (self.qgis_project.crs().toWkt()), "notes", "memory")
        mem_lyr.loadNamedStyle(os.path.join(self.plugin_dir, "qml", "notes_lyr_style.qml"))
        mem_lyr_pro = mem_lyr.dataProvider()
        mem_lyr_pro.addAttributes([QgsField("user", QVariant.String)])
        mem_lyr_pro.addAttributes([QgsField("uid", QVariant.String)])
        mem_lyr.updateFields()
        self.mem_lyr = mem_lyr
        
        self.lyr_grp.insertLayer(0, mem_lyr)
        self.qgis_project.addMapLayer(mem_lyr, False)
        self.rect_tool.set_lyr(mem_lyr)
        self.rect_tool.set_dlg(self.meeting_dlg)
     
    def add_user(self, data):
        print("%s entered the room." % (data["user"]))
        self.meeting_dlg.add_user(name=data["user"], sid=data["sid"])
        
        data = {"rid":self.meeting_dlg.rid, 
                "users":self.meeting_dlg.get_all_users()}
        
        self.emit_msg_to_server("user_list", msg_data=data, nspace="/start")
        #send the current crs when a new user joins the meeting; hence
        #his/her crs is automatically adjusted to the one of the host
        #on startup
        self.crs_changed()
    
    def add_user_from_list(self, data):
        self.meeting_dlg.add_user_from_list(data)
    
    def _on_user_list(self, data):
        self.dlg.qtsig_user_list.emit(data)
     
    def launch_dlg_closed(self):
        self.role = None
        self.remove_host_handlers()
        
        self.disconnect_from_server()
        self.dlg.setEnabled(True)
        self.dlg.showNormal()
    
    def launch_room_dlg(self, data):
        
        self.meeting_dlg = MeetingDialog()
        self.meeting_dlg.closed.connect(self.launch_dlg_closed)
        self.meeting_dlg.qtsig_local_feat_added.connect(self.local_feat_added)

        self.meeting_dlg.rid = data["rid"]
        
        self.meeting_dlg.setWindowTitle(data["title"])        
        self.meeting_dlg.add_user(name=data["user"], sid=data["sid"])
        
        self.meeting_dlg.add_rect_button.clicked.connect(self.set_rect_tool)
        
        self.meeting_dlg.show()
        
        root = self.qgis_project.layerTreeRoot()
        lyr_grp = root.findGroup("QollabEO")
        
        if lyr_grp is None:
            self.lyr_grp = root.insertGroup(0, "QollabEO")
        else:
            self.lyr_grp = lyr_grp
                                
        if self.role == "HOST":
            self.canvas_signal_extent = self.canvas.extentsChanged.connect(self.canvas_changed)
            self.canvas_signal_crs = self.canvas.destinationCrsChanged.connect(self.crs_changed)

            self.grp_pre_add_event = self.lyr_grp.willAddChildren.connect(self.pre_lyr_added)
            self.grp_add_event = self.lyr_grp.addedChildren.connect(self.lyr_added)
            self.grp_vis_event = self.lyr_grp.visibilityChanged.connect(self.lyr_vis_changed)
            
            self.grp_pre_rem_event = self.lyr_grp.willRemoveChildren.connect(self.pre_lyr_removed)
            self.grp_rem_event = self.lyr_grp.removedChildren.connect(self.lyr_removed)
            
            #add memory layer for storing "notes" when user is host
            mem_lyr = QgsVectorLayer("Polygon?crs=%s" % (self.qgis_project.crs().toWkt()), "notes", "memory")
            mem_lyr.loadNamedStyle(os.path.join(self.plugin_dir, "qmls", "notes_lyr_style.qml"))
            mem_lyr_pro = mem_lyr.dataProvider()
            mem_lyr_pro.addAttributes([QgsField("user", QVariant.String)])
            mem_lyr_pro.addAttributes([QgsField("uid", QVariant.String)])
            mem_lyr.updateFields()
            self.mem_lyr = mem_lyr
            # mem_lyr.featureAdded.connect(self.feat_added)

            self.lyr_grp.insertLayer(0, mem_lyr)
            self.qgis_project.addMapLayer(mem_lyr, False)
            self.rect_tool.set_lyr(mem_lyr)
            self.rect_tool.set_dlg(self.meeting_dlg)
            
        self.dlg.setEnabled(False)
        self.dlg.showMinimized()

    def local_feat_added(self, data):
        if self.role == "HOST":
            self.emit_msg_to_server("feat_added", msg_data=data, nspace="/start")
        else:
            self.emit_msg_to_server("feat_added", msg_data=data, nspace="/join")
    
    def _on_feat_added(self, data):
        self.dlg.qtsig_feat_added.emit(data)
    
    def add_remote_feat(self, data):
        feat = QgsFeature(self.mem_lyr.fields())
        feat.setAttribute('user', data["user"])
        feat.setAttribute('uid', data["uid"])
        feat.setGeometry(QgsGeometry.fromWkt(data["geom"]))
        (res, outFeats) = self.mem_lyr.dataProvider().addFeatures([feat])
        self.mem_lyr.reload()
    
    def lyr_vis_changed(self, lyr):
        
        is_visible = lyr.itemVisibilityChecked()
        lyr = lyr.layer()
        lyr_prov = lyr.providerType()
        send_data = {"name":lyr.name(), "is_visible":is_visible}
        
        if lyr_prov == "wms":
            self.emit_msg_to_server("lyr_vis_changed", msg_data=send_data, nspace="/start")

    def pre_lyr_added(self, lyr_grp):
        lyrs_in_grp = lyr_grp.findLayers()
        lid_in_grp = [lyr.layerId() for lyr in lyrs_in_grp if lyr.layer().providerType() == "wms"]
        self.pre_lids = lid_in_grp
        
    def lyr_added(self, lyr_grp):
        lyrs_in_grp = lyr_grp.findLayers()
        lids_in_grp = [lyr.layerId() for lyr in lyrs_in_grp if lyr.layer().providerType() == "wms"]
        added_lid = list(set(lids_in_grp) - set(self.pre_lids))
        
        if len(added_lid) == 1:
        
            lyr_ix = lids_in_grp.index(added_lid[0])
            added_lyr = lyrs_in_grp[lyr_ix].layer()

            send_data = {"name":added_lyr.name(), "source":added_lyr.source(), "tix":lyr_ix}
            
            self.emit_msg_to_server("lyr_added", msg_data=send_data, nspace="/start")
                    
    def pre_lyr_removed(self, lyr_grp):
        lyrs_in_grp = lyr_grp.findLayers()
        lyr_names_in_grp = [lyr.layer().name() for lyr in lyrs_in_grp if lyr.layer().providerType() == "wms"]
        self.pre_lyr_names = lyr_names_in_grp
        
    def lyr_removed(self, lyr_grp):
        lyrs_in_grp = lyr_grp.findLayers()
        curr_lyr_names =  [lyr.layer().name() for lyr in lyrs_in_grp if lyr.layer().providerType() == "wms"]

        rem_lyr_name = list(set(self.pre_lyr_names) - set(curr_lyr_names))
        if len(rem_lyr_name) == 1:
            send_data =  {"name":rem_lyr_name[0]}
            self.emit_msg_to_server("lyr_removed", msg_data=send_data, nspace="/start")
        
    def _on_start_failed(self):
        self.disconnect_from_server()
    
    def _on_join_failed(self):
        self.disconnect_from_server()
    
    def _on_room_left(self, data):
        self.dlg.qtsig_room_left.emit(data)
    
    def _on_room_closed(self):
        self.dlg.qtsig_room_closed.emit()
    
    def remove_user(self, data):
        self.meeting_dlg.remove_user(data)
    
    def leave_session(self):
        self.meeting_dlg.setEnabled(False)
        
        choice = QMessageBox.question(self.meeting_dlg, 'Session ended.',
                            "The host left the meeting.",
                            QMessageBox.Ok)
        if choice == QMessageBox.Ok:
            self.meeting_dlg.close()
            self.launch_dlg_closed()       
        
    def _on_connect(self):
        print("connected to server")

    def _on_disconnect(self):
        print('disconnected from server')
    
    def _on_connect_error(self, data):
        print(data)
        self.disconnect_from_server()
    
    def disconnect_from_server(self):
        self.sio.disconnect()
        self.sio.eio.disconnect(abort=True)
    
    def connect_to_server(self, url=None, sio_path=None, nspaces=None, auth=None, headers=None):
        if url is None:
            url = self.url
        if sio_path is None:
            sio_path = self.sio_path
            
        try:
            self.sio.connect(url, socketio_path=sio_path, wait=True, auth=auth, headers=headers, namespaces=nspaces)
        except:
            self.show_message("No connection to server.", level="critical")

    def schedule_session(self):
        
        # line_email = sself.schedule_tab.findChild(QLineEdit, 'input_email')
        curr_email = self.dlg.input_email.text()
        
        if curr_email == "":
            self.show_message("No E-Mail provided.", level="warning")
            return
        
        curr_title = self.dlg.input_title.text()
        
        if curr_title == "":
            self.show_message("No Title provided.", level="warning")
            return
                
        session_date = self.dlg.date.date().toPyDate()
        session_date = datetime(year=session_date.year, month=session_date.month, day=session_date.day, hour=0, minute=0)
        
        session_from = self.dlg.time_from.currentText()
        session_to = self.dlg.time_to.currentText()
        
        from_time = session_date + timedelta(hours=int(session_from[:2]), minutes=int(session_from[3:]))
        to_time = session_date + timedelta(hours=int(session_to[:2]), minutes=int(session_to[3:]))
            
        if from_time < datetime.now():
            self.show_message("Meeting can't start in the past.", level="warning")
            return
            
        if to_time <= from_time:
            self.show_message("End time must be later than start time.", level="warning")
            return
        
        self.connect_to_server(nspaces="/schedule")
        
        if self.sio.connected:
            self.emit_msg_to_server(msg_type="schedule_session", 
                                    msg_data={"mail":curr_email, "from":from_time.strftime("%Y-%m-%d %H:%M:%S"), "to":to_time.strftime("%Y-%m-%d %H:%M:%S"), "title":curr_title},
                                    nspace="/schedule")
    
    def show_message(self, msg=None, level="info", seconds=3):
        if level == "info":
            level_id = 0
        elif level == "warning":
            level_id = 1
        elif level == "critical":
            level_id = 2
        elif level == "success":
            level_id = 3
        else:
            level_id = 0
            
        self.iface.messageBar().pushMessage("", msg, level=level_id, duration=seconds)

    def fill_table_session(self):
        self.dlg.table_session.setRowCount(0)
                        
        sid_db = sqlite3.connect(self.sid_db_path)
        db_cur = sid_db.cursor()
        
        #only add items to the table which have a to_time less than the current hour;
        db_cur.execute("SELECT * FROM sessions WHERE to_time >= strftime('%Y-%m-%d %H', 'now', '-1 hour')")
        rows = db_cur.fetchall()
        #0:mail;1:title;2:rid;3:pwd;4:from;5:to
        
        for ix, row in enumerate(rows):
            self.dlg.table_session.insertRow(ix)
            self.dlg.table_session.setRowHeight(ix, 25)
            self.dlg.table_session.setItem(ix , 0, QTableWidgetItem(row[1]))   #name
            self.dlg.table_session.setItem(ix , 1, QTableWidgetItem(row[4]))    #from
            self.dlg.table_session.setItem(ix , 2, QTableWidgetItem(row[5]))    #to
            self.dlg.table_session.setItem(ix , 3, QTableWidgetItem(row[0]))    #mail (hidden)
            self.dlg.table_session.setItem(ix , 4, QTableWidgetItem(row[2]))    #rid (hidden)
            self.dlg.table_session.setItem(ix , 5, QTableWidgetItem(row[3]))    #pwd (hidden)
            
            self.btn_copy = QPushButton('')
            self.btn_copy.setIcon(QIcon(os.path.join(self.plugin_dir, "gfx", "icon_copy.png")))
            self.btn_copy.clicked.connect(self.get_clicked_tix)
            
            self.dlg.table_session.setCellWidget(ix,6,self.btn_copy)
    
    def get_clicked_tix(self):
        button = QApplication.focusWidget()
        index = self.dlg.table_session.indexAt(button.pos())
        if index.isValid():
            
            self.get_row_vals(index.row())
            # print(index.row(), index.column())
    
    def get_row_vals(self, tix):
        # sel_title = self.dlg.table_session.item(tix, 0).text()
        # sel_from = self.dlg.table_session.item(tix, 1).text()
        # sel_to = self.dlg.table_session.item(tix, 2).text()
        # sel_mail = self.dlg.table_session.item(tix, 3).text()
        rid = self.dlg.table_session.item(tix, 4).text()
        pwd = self.dlg.table_session.item(tix, 5).text()

        url_str = self.url + self.sio_path + "?%s?%s" % (rid, pwd)
        self.copy_to_clipboard(copy_str=url_str)
        
    def tab_changed(self):
        curr_tix = self.dlg.qollab_menu.currentIndex()
        #if start_tab is selected fetch all created meetings from
        #sqlite database and add them as items to the combobox
        if curr_tix == 1:
            self.fill_table_session()
               
    def start_session(self):
        
        curr_name = self.dlg.input_start_user.text()
        if curr_name == "":
            self.show_message("No username provided.")
            return
        
        sel_six = self.dlg.table_session.selectedIndexes()
        
        if len(sel_six) > 0:
            tix = sel_six[0].row()
                    
            sel_title = self.dlg.table_session.item(tix, 0).text()
            sel_from = self.dlg.table_session.item(tix, 1).text()
            sel_to = self.dlg.table_session.item(tix, 2).text()
            sel_mail = self.dlg.table_session.item(tix, 3).text()
            sel_rid = self.dlg.table_session.item(tix, 4).text()
            sel_pwd = self.dlg.table_session.item(tix, 5).text()
            
            self.connect_to_server(nspaces="/start")
            
            if self.sio.connected:
                self.emit_msg_to_server("start_session", msg_data={"mail":sel_mail, "title":sel_title, "user":curr_name, "rid":sel_rid, "pwd":sel_pwd}, nspace="/start")
        else:
            self.show_message("No session selected.")
    
    def join_session(self):
        curr_name = self.dlg.input_join_user.text()
        if curr_name == "":
            self.show_message("No username provided.", level="warning")
            return
        
        curr_url = self.dlg.input_join_url.toPlainText()
        if curr_url == "":
            self.show_message("No url provided.", level="warning")
            return

        url_parts = curr_url.split("?")
        if len(url_parts) != 3:
            self.show_message("Invalid url provided.", level="warning")
            return
        
        curr_url = url_parts[0]       
        curr_url, curr_sio_path = curr_url.rsplit("/", 1)
        curr_sio_path = "/" + curr_sio_path
        
        curr_rid = url_parts[1]
        curr_pwd = url_parts[2]
        
        self.connect_to_server(url=curr_url, sio_path=curr_sio_path, auth={"rid":curr_rid, "pwd":curr_pwd},  nspaces="/join")
        
        if self.sio.connected:
            self.emit_msg_to_server("join_session", msg_data={"user":curr_name, "rid":curr_rid, "pwd":curr_pwd}, nspace="/join")
    
    def set_rect_tool(self):
        if self.meeting_dlg.add_rect_button.isChecked():
            self.canvas.setMapTool(self.rect_tool)
        else:
            self.canvas.setMapTool(self.pan_tool)

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            
            self.dlg = QollabEODialog()
            self.dlg.setWindowTitle("QollabEO")
            self.dlg.closed.connect(self.dlg_closed)  #use lambda: self.dlg_closed() to pass parameters;
            
            self.dlg.copy_url_button.setIcon(QIcon(os.path.join(self.plugin_dir, "gfx", "icon_copy.png")))
            self.dlg.copy_url_button.clicked.connect(lambda: self.copy_to_clipboard(copy_str=None))
            self.dlg.qollab_menu.currentChanged.connect(self.tab_changed)
             
            self.dlg.create_session_button.clicked.connect(self.schedule_session)
            self.dlg.start_session_button.clicked.connect(self.start_session)
            self.dlg.join_session_button.clicked.connect(self.join_session)
            
            self.dlg.qtsig_created.connect(self.add_session_info_to_gui)
            self.dlg.qtsig_started.connect(self.launch_room_dlg)
            self.dlg.qtsig_joined.connect(self.launch_room_dlg)
            self.dlg.qtsig_entered.connect(self.add_user)
            self.dlg.qtsig_user_list.connect(self.add_user_from_list)
            self.dlg.qtsig_room_left.connect(self.remove_user)
            self.dlg.qtsig_room_closed.connect(self.leave_session)
            self.dlg.qtsig_extent.connect(self.set_extent_from_remote)
            self.dlg.qtsig_crs.connect(self.set_crs_from_remote)
            self.dlg.qtsig_vis_changed.connect(self.vis_remote_lyr)
            self.dlg.qtsig_lyr_added.connect(self.add_remote_lyr)
            self.dlg.qtsig_lyr_removed.connect(self.remove_remote_lyr)
            self.dlg.qtsig_feat_added.connect(self.add_remote_feat)
            
            #QComboBox maxitemsVisible only used when QQomboBox is editable;
            #to disable editing the underlying linedit is changed; flound here: https://forum.qt.io/topic/125735/set-maxvisibleitems-property-in-fusion-style-for-qtcombobox-dropdown-box/2
            self.dlg.time_from.clear()
            self.dlg.time_from.addItems(create_quarter_strings())
            self.dlg.time_from.lineEdit().setFrame(False)
            self.dlg.time_from.lineEdit().setReadOnly(True)
        
            self.dlg.time_to.clear()
            self.dlg.time_to.addItems(create_quarter_strings())
            self.dlg.time_to.lineEdit().setFrame(False)   
            self.dlg.time_to.lineEdit().setReadOnly(True)
            
            #style the table of the start_tab;
            self.dlg.table_session.setColumnWidth(1, 130)           #set from and to columns to fixed size
            self.dlg.table_session.setColumnWidth(2, 130)
            self.dlg.table_session.setColumnHidden(3, True)         #hide columns showing rid and pwd;
            self.dlg.table_session.setColumnHidden(4, True)
            self.dlg.table_session.setColumnHidden(5, True)
            self.dlg.table_session.setColumnWidth(6, 12)
            
            header = self.dlg.table_session.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.Stretch)     #stretch name as this the most dynamical value
            header.setSectionResizeMode(1, QHeaderView.Fixed)
            header.setSectionResizeMode(2, QHeaderView.Fixed)
            header.setSectionResizeMode(6, QHeaderView.Fixed)
         
            self.dlg.input_email.setText(self.email)
            self.dlg.input_start_user.setText(self.name)
            self.dlg.input_join_user.setText(self.name)
            
            self.qgis_project = QgsProject.instance()

        #set date and time for the comboboxes
        self.dlg.date.setDateTime(QDateTime.currentDateTime())

        from_str, to_str = get_current_from_to()
        self.dlg.time_from.setCurrentIndex(create_quarter_strings().index(from_str))
        self.dlg.time_to.setCurrentIndex(create_quarter_strings().index(to_str))
        
        self.fill_table_session()
        
        self.canvas = self.iface.mapCanvas()
                        
        # show the dialog
        self.dlg.show()
    