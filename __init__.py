# -*- coding: utf-8 -*-

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load Qollab class from file Qollab.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .qollabeo import QollabEO
    return QollabEO(iface)
