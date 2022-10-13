from PySide2 import QtWidgets
from charttest import GraphWidget

from pxr import Usd

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    test = 'resources/UsdSkelExamples/HumanFemale/HumanFemale.keepAlive.usd'
    stage = Usd.Stage.Open(test)

    app = QtWidgets.QApplication([])
    chart = GraphWidget.initUi()
    chart.set_stage(stage)
    app.exec_()
