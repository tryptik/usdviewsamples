import logging

from PySide2 import QtGui, QtWidgets, QtCore
from PySide2.QtCharts import QtCharts

from pxr import Usd, UsdSkel, Sdf, Gf

logging.basicConfig()
logger = logging.getLogger('usdchart')
logger.setLevel(logging.DEBUG)

SERIES_ROLE = QtCore.Qt.UserRole + 1024

def prim_iter(prim, inclusive=False):
    if inclusive:
        yield prim
    for ch in prim.GetChildren():
        yield ch
        for ich in prim_iter(ch):
            yield ich


def find_skeleton(prim):
    for k in prim_iter(prim):
        if k.GetTypeName() == 'Skeleton':
            return k


def skel_to_treeitems(joints):
    topo = UsdSkel.Topology(joints)
    parents = topo.GetParentIndices()

    joint_idx_dct = {}
    result = {}
    root = None
    for i in range(len(joints)):
        parent_idx = parents[i]
        this_path = Sdf.Path(joints[i])
        item = QtWidgets.QTreeWidgetItem([this_path.name])
        if not root:
            root = item
        joint_idx_dct[i] = item
        result[joints[i]] = item
        parent_item = joint_idx_dct.get(parent_idx)
        if parent_item:
            parent_item.addChild(item)
    return root,result


class GraphWidget(QtWidgets.QWidget):
    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._prim_map = {}
        self._last_sel = list()

        ly = QtWidgets.QVBoxLayout()

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.pathList = QtWidgets.QTreeWidget()
        self.pathList.setAlternatingRowColors(True)

        self.chartView = QtCharts.QChartView()
        self.chart = QtCharts.QChart()

        self.chartView.setChart(self.chart)

        splitter.addWidget(self.pathList)
        splitter.addWidget(self.chartView)
        ly.addWidget(splitter)
        self.setLayout(ly)
        self.pathList.itemSelectionChanged.connect(self.on_selection_changed)

    def on_selection_changed(self):
        for sel in self._last_sel:
            for series in sel.data(0, SERIES_ROLE) or []:
                series.setVisible(False)
        self._last_sel = self.pathList.selectedItems()
        for sel in self._last_sel:
            for series in sel.data(0, SERIES_ROLE) or []:
                logger.info('   + %s', series.name())
                series.setVisible(True)

    def add_skel_and_anim(self, skel_prim, src):
        # logger.info('    Skeleton: %s', skel_prim)
        skel = UsdSkel.Skeleton(skel_prim)
        skel_joints = skel.GetJointsAttr().Get()

        root, joint_item_dct = skel_to_treeitems(skel_joints)
        prim_item = QtWidgets.QTreeWidgetItem([skel_prim.GetName()])
        prim_item.addChild(root)
        self.pathList.addTopLevelItem(prim_item)

        anim = UsdSkel.Animation(src)
        anim_joints = anim.GetJointsAttr().Get()
        # logger.info('  Anim jnts: %s', anim_joints)

        joint_dict = {x:i for i,x in enumerate(skel_joints)}

        tr = anim.GetTranslationsAttr()
        rt = anim.GetRotationsAttr()
        sc = anim.GetScalesAttr()

        samples = tr.GetTimeSamples()
        tseries = []
        for joint in anim_joints:
            series_index = []
            for chan in ('.tx', '.ty', '.tz',):
                sr = QtCharts.QLineSeries()
                sr.setName(joint.split('/')[-1]+chan)
                sr.setPointsVisible(True)
                series_index.append(sr)
                tseries.append(sr)
                sr.setVisible(False)

            titem = joint_item_dct.get(joint)
            if titem:
                titem.setData(0, SERIES_ROLE, series_index)
                # titem.setCheckState(0, QtCore.Qt.Checked)

        for s in samples:
            values = anim.GetTranslationsAttr().Get(s)
            assert len(values) * 3 == len(tseries)
            for i,val in enumerate(values):
                tidx = i * 3
                tseries[tidx].append(s, val[0])
                tseries[tidx+1].append(s, val[1])
                tseries[tidx+2].append(s, val[2])

        for x in tseries:
            self.chart.addSeries(x)

    def add_skel_animation(self, stage):
        """Find and apply skel anim"""
        for prim in stage.Traverse():
            bnd = UsdSkel.BindingAPI(prim)
            src = bnd.GetAnimationSource()
            if src:
                logger.info('  Found: %s %s', prim.GetPath(), src)
                skel_prim = find_skeleton(prim)
                if skel_prim:
                    self.add_skel_and_anim(skel_prim, src)

    def set_stage(self, stage):
        """Pull all sampled and skel data

        :param stage:
        :return:
        """
        self.chart = QtCharts.QChart()
        self.pathList.clear()

        self.add_skel_animation(stage)

        # do we want static skels? not sure yet
        # self.add_static_skel(stage)

        # self.add_animated_prims(stage)

        self.pathList.expandAll()
        self.pathList.setIndentation(16)
        self.chart.createDefaultAxes()
        self.chartView.setChart(self.chart)

    # def get_series_from_prim(self, prim):
    #     return list()
    #
    # def set_prim(self, prim):
    #     path = prim.GetPath()
    #     series = self._prim_map.get(path)
    #     if series is None:
    #         series = self.get_series_from_prim(prim)
    #         self._prim_map[path] = series
    #
    #     for s in series:
    #         self.chart.addSeries(s)

    def unset_prim(self, prim):
        for series in self._prim_map.get(prim.GetPath(), list()):
            self.chart.removeSeries(series)


    @classmethod
    def initUi(cls):
        cls._instance = cls()
        cls._instance.show()
        cls._instance.raise_()
        return cls._instance

if __name__ == 'builtins':
    t = GraphWidget.initUi()
    t.set_stage(usdviewApi.stage)
