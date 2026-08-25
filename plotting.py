"""Post-run plotting and export use the same saved run as live plotting."""
from html import escape
from pathlib import Path
import threading
import ipywidgets as widgets
from data_store import save_csv


class PlottingPanel:
    def __init__(self, plotter, dispatch, on_busy):
        self.plotter, self.dispatch, self.on_busy = plotter, dispatch, on_busy
        self.lock = threading.RLock()
        self.run = None
        self.running = self.busy = False
        self.metadata = {}
        self.info = widgets.HTML('Results will be saved in QCoDeS.')
        self.x_dropdown = widgets.Dropdown(description='X:', layout=widgets.Layout(width='210px'))
        self.y_dropdown = widgets.Dropdown(description='Y:', layout=widgets.Layout(width='210px'))
        self.plot_button = widgets.Button(description='POST PLOT', disabled=True, button_style='primary')
        self.save_button = widgets.Button(description='SAVE CSV', disabled=True)
        self.plot_button.on_click(lambda _: self.post_plot())
        self.save_button.on_click(lambda _: self.export_csv())

    def build(self):
        return widgets.VBox([
            widgets.HTML('<b>Saved-run plotting</b>'),
            widgets.HBox([self.x_dropdown, self.y_dropdown]), self.info,
            widgets.HBox([self.plot_button, self.save_button]),
        ], layout=widgets.Layout(width='570px'))

    def reset(self, metadata):
        with self.lock:
            if self.running or self.busy:
                return
            self.metadata = metadata or {}
            self.run = None
            names = list(dict.fromkeys(axis for plot in self.metadata.values()
                                       for axis in (plot['x'], plot['y'])))
            self.x_dropdown.options = self.y_dropdown.options = names
            self.info.value = 'Results will be saved in QCoDeS.'
            self._update_controls()

    def set_running(self, running):
        with self.lock:
            self.running = running
            if running:
                self.run = None
                self.info.value = 'Post plotting is available after the run finishes saving.'
            self._update_controls()

    def set_run(self, run):
        with self.lock:
            self.run = run
            names = list(run.columns) if run else []
            self.x_dropdown.options = self.y_dropdown.options = names
            first = next(iter(self.metadata.values()), {})
            if first.get('x') in names:
                self.x_dropdown.value = first['x']
            if first.get('y') in names:
                self.y_dropdown.value = first['y']
            self.info.value = (f'QCoDeS run {run.run_id} · {run.points} points'
                               if run else 'No completed data available.')
            self._update_controls()

    def _update_controls(self):
        disabled = self.running or self.busy or self.run is None or self.run.points == 0
        for widget in (self.x_dropdown, self.y_dropdown, self.plot_button, self.save_button):
            widget.disabled = disabled

    def post_plot(self):
        self._start_action(export=False)

    def export_csv(self):
        self._start_action(export=True)

    def _start_action(self, export):
        with self.lock:
            if self.running or self.busy or self.run is None or self.run.points == 0:
                return
            if not self.on_busy(True):
                return
            self.busy = True
            self._update_controls()
            run = self.run
            plots = {'Selected plot': {'x': self.x_dropdown.value, 'y': self.y_dropdown.value}}
        def work():
            try:
                if export:
                    path = Path(run.database).with_name(f'run_{run.run_id}.csv')
                    save_csv(run, path)
                    message = f'Saved {path}'
                else:
                    self.plotter.open(run, plots)
                    message = f'Opened QCoDeS run {run.run_id} in pyplotter.'
            except Exception as exc:
                message = str(exc)
            self.dispatch(lambda: self._finish_action(message))
        try:
            threading.Thread(target=work, daemon=True).start()
        except Exception as exc:
            self._finish_action(str(exc))

    def _finish_action(self, message):
        with self.lock:
            self.busy = False
            self.info.value = escape(message)
            self._update_controls()
        self.on_busy(False)
