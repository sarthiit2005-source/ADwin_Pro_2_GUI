"""Connect a specific QCoDeS run to pyplotter's native plot windows.

Only this adapter depends on pyplotter's internal API. Keep its version pinned.
The Qt timer and database reader both live in this separate process.
"""
import json
from pathlib import Path
import sys
import traceback


def main(request_path):
    from PyQt5 import QtCore, QtWidgets
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    from pyplotter.sources.config import initConfig
    initConfig()
    # Pyplotter expects the older scikit-rf top-level Touchstone export.
    import skrf
    if not hasattr(skrf, 'Touchstone'):
        from skrf.io.touchstone import Touchstone
        skrf.Touchstone = Touchstone
    from pyplotter.ui.mainWindow import MainApp
    import pyqtgraph as pg
    # These line plots do not need GPU rendering; this also works on lab PCs
    # without an OpenGL context and in offscreen verification.
    pg.setConfigOption('useOpenGL', False)
    import numpy as np
    from data_store import SavedRun, read_columns

    request_path = Path(request_path)
    request = json.loads(request_path.read_text(encoding='utf-8'))
    run = SavedRun(request['database'], request['run_id'], request['columns'], 0)
    app = QtWidgets.QApplication(sys.argv)
    window = MainApp(app)
    window.setWindowTitle(f'ADwin · QCoDeS run {run.run_id}')
    window.show()
    curves = []
    for index, (name, plot) in enumerate(request['plots'].items()):
        x, y = plot['x'], plot['y']
        x_info, y_info = run.columns[x], run.columns[y]
        reference = f'adwin_{run.run_id}_{index}'
        curve = reference + '_curve'
        window.addPlot(
            plotRef=reference, databaseAbsPath=run.database,
            data=(np.array([]), np.array([])),
            xLabelText=x_info.get('label', x), xLabelUnits=x_info.get('unit', ''),
            yLabelText=y_info.get('label', y), yLabelUnits=y_info.get('unit', ''),
            zLabelText='', zLabelUnits='', runId=run.run_id, curveId=curve,
            plotTitle=name, windowTitle=f'{name} · run {run.run_id}',
            dateTimeAxis=False, curveLegend=y_info.get('label', y))
        curves.append((reference, curve, x, y, name))

    timer = QtCore.QTimer()
    def refresh(initial=False):
        try:
            data, completed = read_columns(run)
            for reference, curve, x, y, name in curves:
                if reference not in window._plotRefs:
                    continue
                if x in data and y in data and len(data[x]) == len(data[y]):
                    window.slotUpdateCurve(reference, curve, y, data[x], data[y], True, False)
                window.slotUpdatePlotProperty(reference, 'plotTitle',
                                             name + (' · finished' if completed else ' · measuring'))
            window.statusBar().showMessage(f'Run {run.run_id} · {"finished" if completed else "measuring"}')
            if completed:
                timer.stop()
            if request.get('diagnostics'):
                request_path.with_suffix('.state').write_text(json.dumps({
                    'completed': completed,
                    'points': {name: len(values) for name, values in data.items()},
                    'curves': {
                        name: {'x': window._plotRefs[reference].curves[curve].x.tolist(),
                               'y': window._plotRefs[reference].curves[curve].y.tolist()}
                        for reference, curve, x, y, name in curves
                        if reference in window._plotRefs
                    },
                }), encoding='utf-8')
                if completed:
                    for reference, *_ in curves:
                        if reference in window._plotRefs:
                            window._plotRefs[reference].grab().save(str(request_path.with_suffix('.plot.png')))
                    if request.get('exit_when_complete'):
                        QtCore.QTimer.singleShot(0, app.quit)
        except Exception:
            if initial:
                raise
            traceback.print_exc()
            window.statusBar().showMessage('Could not refresh data; check the plotter log.')

    timer.timeout.connect(refresh)
    timer.start(500)
    app.aboutToQuit.connect(timer.stop)
    refresh(initial=True)
    request_path.with_suffix('.ready').write_text('ready', encoding='utf-8')
    return app.exec_()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
