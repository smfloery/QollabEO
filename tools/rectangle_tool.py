from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand, QgsMapTool
from qgis.core import QgsWkbTypes, QgsPointXY, QgsRectangle, QgsFeature, QgsGeometry
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
import uuid

class RectangleMapTool(QgsMapToolEmitPoint):
    def __init__(self, canvas, user):
        self.canvas = canvas
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setColor(Qt.red)
        self.rubberBand.setWidth(1)
        self.rubberBand.setFillColor(QColor(0,0,0,0))
        self.user = user
        self.reset()

    def set_lyr(self, lyr):
        self.lyr = lyr
    
    def set_dlg(self, dlg):
        self.dlg = dlg

    def set_user(self, name):
        self.user = name
    
    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)

    def canvasPressEvent(self, e):
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint
        self.isEmittingPoint = True
        self.showRect(self.startPoint, self.endPoint)

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False
        r = self.rectangle()
        if r is not None:
                
            feat = QgsFeature(self.lyr.fields())
            feat_uid = str(uuid.uuid4())
            
            feat.setAttribute('user', self.user)
            feat.setAttribute('uid', feat_uid)
            
            feat.setGeometry(QgsGeometry.fromRect(self.rectangle()))
            
            (res, outFeats) = self.lyr.dataProvider().addFeatures([feat])
            
            self.lyr.reload()
            
            self.dlg.qtsig_local_feat_added.emit({"user":self.user, "geom":self.rectangle().asWktPolygon(), "uid":feat_uid})
            
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        
    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())
        self.showRect(self.startPoint, self.endPoint)

    def showRect(self, startPoint, endPoint):
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return

        point1 = QgsPointXY(startPoint.x(), startPoint.y())
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = QgsPointXY(endPoint.x(), endPoint.y())
        point4 = QgsPointXY(endPoint.x(), startPoint.y())

        self.rubberBand.addPoint(point1, False)
        self.rubberBand.addPoint(point2, False)
        self.rubberBand.addPoint(point3, False)
        self.rubberBand.addPoint(point4, True)    # true to update canvas       

        self.rubberBand.show()

    def rectangle(self):
        if self.startPoint is None or self.endPoint is None:
            return None
        elif (self.startPoint.x() == self.endPoint.x() or \
            self.startPoint.y() == self.endPoint.y()):
            return None

        return QgsRectangle(self.startPoint, self.endPoint)

    def deactivate(self):
        # QgsMapTool.deactivate(self)
        self.deactivated.emit()