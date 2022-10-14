"""
C:/Users/trypt/PycharmProjects/charttest/charttest.py

"""
import weakref
import logging

from PySide2 import QtGui, QtWidgets, QtCore
from PySide2.QtCharts import QtCharts

from pxr import Usd, UsdSkel, Sdf, Gf

logging.basicConfig()
logger = logging.getLogger('usdchart')
logger.setLevel(logging.DEBUG)


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

SERIES_ROLE = QtCore.Qt.UserRole + 1024
SERIES_IDX_ROLE = QtCore.Qt.UserRole + 1025


class JointSamples:
    def __init__(self, joint_path, parent):
        self.parent = weakref.proxy(parent)
        self.name = Sdf.Path(joint_path).name
        self._series = []
        for att in ('.tx', '.ty', '.tz', '.rx', '.ry', '.rz', '.sx', '.sy', '.sz'):
            series = QtCharts.QLineSeries()
            series.setName(self.name+att)
            series.setPointsVisible(True)
            # series.setPointSize(4)
            if 'x' in att:
                series.setColor(QtGui.QColor('red'))
            elif 'y' in att:
                series.setColor(QtGui.QColor('green'))
            else:
                series.setColor(QtGui.QColor('blue'))
            self._series.append(series)

    def append(self, sample, trans, rot, scale):
        children = self._series
        children[0].append(sample, trans[0])
        children[1].append(sample, trans[1])
        children[2].append(sample, trans[2])
        rot = Gf.Rotation(rot)
        eul = rot.Decompose(Gf.Vec3d.XAxis(), Gf.Vec3d.YAxis(), Gf.Vec3d.ZAxis())
        children[3].append(sample, eul[0])
        children[4].append(sample, eul[1])
        children[5].append(sample, eul[2])
        children[6].append(sample, scale[0])
        children[7].append(sample, scale[1])
        children[8].append(sample, scale[2])

    def add_to_chart(self, chart):
        if self.parent.view_translate():
            for ch in self._series[0:3]:
                chart.addSeries(ch)
        if self.parent.view_rotate():
            for ch in self._series[3:6]:
                chart.addSeries(ch)
        if self.parent.view_scale():
            for ch in self._series[6:9]:
                chart.addSeries(ch)

    def rm_from_chart(self, chart):
        for ch in self._series:
            chart.removeSeries(ch)

    def set_points_visible(self, val):
        for ch in self._series:
            ch.setPointsVisible(val)


class GraphWidget(QtWidgets.QWidget):
    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._prim_map = {}
        self._last_sel = list()
        self._series_map = {}

        ly = QtWidgets.QVBoxLayout()

        hly = QtWidgets.QHBoxLayout()
        self._tr_only = QtWidgets.QCheckBox('Translate')
        self._tr_only.setChecked(True)
        self._tr_only.stateChanged.connect(self.on_view_cb_stateChanged)
        self._rotate_only = QtWidgets.QCheckBox('Rotate')
        self._rotate_only.setChecked(True)
        self._rotate_only.stateChanged.connect(self.on_view_cb_stateChanged)
        self._sc_only = QtWidgets.QCheckBox('Scale')
        self._sc_only.setChecked(True)
        self._sc_only.stateChanged.connect(self.on_view_cb_stateChanged)

        hly.addWidget(self._tr_only)
        hly.addWidget(self._rotate_only)
        hly.addWidget(self._sc_only)
        ly.addLayout(hly)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.pathList = QtWidgets.QTreeWidget()
        self.pathList.setAlternatingRowColors(True)
        self.pathList.setSelectionMode(self.pathList.ExtendedSelection)

        self.chartView = QtCharts.QChartView()
        self.chart = QtCharts.QChart()

        self.chartView.setChart(self.chart)

        splitter.addWidget(self.pathList)
        splitter.addWidget(self.chartView)
        ly.addWidget(splitter)
        self.setLayout(ly)
        self.pathList.itemSelectionChanged.connect(self.on_selection_changed)
        self.setWindowTitle('Samples Viewer')

    def view_translate(self):
        return self._tr_only.isChecked()

    def view_rotate(self):
        return self._rotate_only.isChecked()

    def view_scale(self):
        return self._sc_only.isChecked()

    def on_view_cb_stateChanged(self, _):
        self.on_selection_changed()

    def on_selection_changed(self):
        for sel in self._last_sel:
            smp = self._series_map.get(sel.data(0, SERIES_IDX_ROLE))
            if smp:
                smp.rm_from_chart(self.chart)
        self._last_sel = self.pathList.selectedItems()
        for sel in self._last_sel:
            smp = self._series_map.get(sel.data(0, SERIES_IDX_ROLE))
            if smp:
                smp.add_to_chart(self.chart)
        self.chart.createDefaultAxes()

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

        tr = anim.GetTranslationsAttr()
        rt = anim.GetRotationsAttr()
        sc = anim.GetScalesAttr()

        assert tr.GetNumTimeSamples() == rt.GetNumTimeSamples() == sc.GetNumTimeSamples()
        samples = tr.GetTimeSamples()
        for s in samples:
            local_tr = tr.Get(s)
            local_rt = rt.Get(s)
            local_sc = sc.Get(s)
            first_sample = True
            for i,joint in enumerate(anim_joints):
                smp = self._series_map.get(i) or self._series_map.setdefault(i, JointSamples(joint, self))
                smp.append(s, local_tr[i], local_rt[i], local_sc[i])

                if first_sample:
                    titem = joint_item_dct.get(joint)
                    if titem:
                        titem.setData(0, SERIES_IDX_ROLE, i)
            first_sample = False

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
