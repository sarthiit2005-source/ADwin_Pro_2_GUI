"""Select a program, run it once, and save its results in QCoDeS."""
from html import escape
import importlib.util
from pathlib import Path
import threading

import ipywidgets as widgets

from adc_monitor import ADCMonitor, SerializedDriver
from data_store import DataStore, program_columns
from plotting import PlottingPanel
from plotter_client import PlotterClient
from ui_dispatch import make_dispatcher


class CompiledProgramsPanel:
    def __init__(self, adwin, programs_dir='compiled_programs', set_status=None,
                 set_navigation_locked=None, database=None, plotter_python=None):
        self.adwin = adwin if isinstance(adwin, SerializedDriver) else SerializedDriver(adwin)
        self.programs_dir = Path(programs_dir)
        self.set_status = set_status or (lambda text: None)
        self.set_navigation_locked = set_navigation_locked or (lambda locked: None)
        self.dispatch = make_dispatcher()
        self.state_lock = threading.RLock()
        self.running = False
        self.plot_busy = False
        self.stop_event = threading.Event()
        self.worker = None
        self.current_module = None
        self.parameter_widgets = {}
        self.columns = {}
        self.saved_run = None
        self.store = DataStore(database or Path(__file__).parent / 'data' / 'experiments.db')
        self.plotter = PlotterClient(plotter_python)
        self.adc_monitor = ADCMonitor(self.adwin, self.dispatch)
        self.plotting_panel = PlottingPanel(self.plotter, self.dispatch, self._plot_busy_changed)
        self.plotting_panel.lock = self.state_lock

        programs = sorted(p.stem for p in self.programs_dir.glob('*.py') if not p.name.startswith('_'))
        self.program_dropdown = widgets.Dropdown(options=programs, description='Program:',
                                                layout=widgets.Layout(width='430px'))
        self.load_button = widgets.Button(description='Load', layout=widgets.Layout(width='80px'))
        self.help_button = widgets.Button(description='?', layout=widgets.Layout(width='34px'))
        self.run_button = widgets.Button(description='Run', button_style='success')
        self.stop_button = widgets.Button(description='Stop', button_style='danger', disabled=True)
        self.live_checkbox = widgets.Checkbox(description='Live plot in pyplotter', disabled=True)
        self.program_area = widgets.VBox()
        self.load_button.on_click(lambda _: self._load_program())
        self.help_button.on_click(lambda _: self._show_help())
        self.run_button.on_click(lambda _: self._run_program())
        self.stop_button.on_click(lambda _: self.stop())

    @property
    def busy(self):
        return self.running or self.plot_busy

    def build(self):
        if self.current_module is None and not self.busy:
            self._load_program()
        return widgets.VBox([
            widgets.HTML('<h3>Compiled Programs</h3>'),
            widgets.HBox([self.program_dropdown, self.load_button, self.help_button]),
            self.program_area,
        ])

    def _load_program(self):
        with self.state_lock:
            if self.busy:
                return
            name = self.program_dropdown.value
            if name is None:
                self.run_button.disabled = True
                self.program_area.children = [widgets.HTML('No programs found.')]
                return
            try:
                path = self.programs_dir / (name + '.py')
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                columns = program_columns(module)
                for plot in getattr(module, 'PLOTS', {}).values():
                    if plot['x'] not in columns or plot['y'] not in columns:
                        raise ValueError('PLOTS axes must exist in DATA_COLUMNS.')
                self.adc_monitor.configure(getattr(module, 'ADC_CHANNELS', []))
                self.current_module = module
                self.columns = columns
                self.saved_run = None
                self.parameter_widgets = {}
                self.live_checkbox.value = False
                self.plotting_panel.reset(getattr(module, 'PLOTS', {}))
                self._build_program_view(name, module)
                self._update_controls()
                self.set_status('Program loaded')
            except Exception as exc:
                self.current_module = None
                self.run_button.disabled = True
                self.program_area.children = [widgets.HTML(escape(f'Load error: {exc}'))]

    def _build_program_view(self, name, module):
        rows = []
        for key, info in getattr(module, 'PARAMETERS', {}).items():
            kind, default = info.get('type', 'str'), info.get('default', '')
            factory = {'float': widgets.FloatText, 'int': widgets.IntText,
                       'bool': widgets.Checkbox}.get(kind, widgets.Text)
            value = default if kind in ('float', 'int', 'bool') else str(default)
            widget = factory(value=value, layout=widgets.Layout(width='180px'))
            self.parameter_widgets[key] = widget
            rows.append(widgets.HBox([
                widgets.Label(key, layout=widgets.Layout(width='180px')),
                widget, widgets.Label(info.get('unit', ''))]))
        parameters = widgets.VBox(rows, layout=widgets.Layout(
            width='460px', min_width='460px', height='300px', overflow='auto'))
        self.program_area.children = [
            widgets.HTML(f'<h4>{escape(getattr(module, "PROGRAM_NAME", name))}</h4>'),
            self.adc_monitor.widget,
            widgets.HBox([parameters, self.plotting_panel.build()],
                         layout=widgets.Layout(grid_gap='24px')),
            self.live_checkbox,
            widgets.HBox([self.run_button, self.stop_button]),
        ]

    def _update_controls(self):
        locked = self.busy
        for widget in (self.program_dropdown, self.load_button, self.help_button):
            widget.disabled = locked
        self.run_button.disabled = locked or self.current_module is None
        self.stop_button.disabled = not self.running or self.stop_event.is_set()
        supports_live = (getattr(self.current_module, 'SUPPORTS_LIVE_PLOT', False) is True
                         and bool(getattr(self.current_module, 'PLOTS', {})))
        self.live_checkbox.disabled = locked or not supports_live
        for widget in self.parameter_widgets.values():
            widget.disabled = locked
        self.set_navigation_locked(locked)

    def _plot_busy_changed(self, busy):
        with self.state_lock:
            if busy and self.busy:
                return False
            self.plot_busy = busy
            self._update_controls()
            return True

    def _run_program(self):
        with self.state_lock:
            if self.busy or self.current_module is None:
                return
            module = self.current_module
            if not callable(getattr(module, 'run', None)):
                self.set_status('Program has no run() function.')
                return
            params = {name: widget.value for name, widget in self.parameter_widgets.items()}
            live = self.live_checkbox.value and not self.live_checkbox.disabled
            self.running = True
            self.stop_event = threading.Event()
            self.saved_run = None
            self._update_controls()
            self.plotting_panel.set_running(True)
            self.set_status('Starting…')
            self.worker = threading.Thread(target=self._program_worker,
                                           args=(module, params, live), daemon=True)
            try:
                self.worker.start()
            except Exception as exc:
                self._finish_run(None, str(exc))

    def stop(self):
        with self.state_lock:
            if self.running:
                self.stop_event.set()
                self.stop_button.disabled = True
                self.set_status('Stopping… waiting for the program and final save.')

    def _program_worker(self, module, params, live):
        saved = None
        writer = None
        error = None
        try:
            with self.store.run(getattr(module, 'PROGRAM_NAME', 'Experiment'),
                                self.columns, params, self.stop_event) as writer:
                if live:
                    self.dispatch(lambda: self.set_status('Opening pyplotter…'))
                    self.plotter.open(self.store.saved_run(writer), module.PLOTS,
                                      live=True, stop_event=self.stop_event)
                if not self.stop_event.is_set():
                    self.adc_monitor.start()
                    self.dispatch(lambda: self.set_status('Running…'))
                    try:
                        module.run(adwin=self.adwin, params=params, stop_event=self.stop_event,
                                   dataset=writer, data_lock=writer.lock)
                    finally:
                        self.adc_monitor.finish('Stopped' if self.stop_event.is_set() else 'Finished')
            saved = self.store.saved_run(writer)
        except BaseException as exc:
            error = str(exc)
            # Only offer partial results if QCoDeS actually finalized the run.
            if writer is not None and writer.saver.dataset.completed:
                saved = self.store.saved_run(writer)
        finally:
            self.dispatch(lambda: self._finish_run(saved, error))

    def _finish_run(self, saved, error):
        with self.state_lock:
            self.saved_run = saved
            self.plotting_panel.set_run(saved)
            self.plotting_panel.set_running(False)
            state = 'Stopped' if self.stop_event.is_set() else 'Finished'
            if error:
                self.set_status(escape(f'Error: {error}'))
            else:
                self.set_status(f'{state} · {saved.points if saved else 0} points saved')
            self.running = False
            self._update_controls()

    def _show_help(self):
        if self.busy:
            return
        help_text = '''<b>Program metadata</b><pre>
SUPPORTS_LIVE_PLOT = True
ADC_CHANNELS = [1]
DATA_COLUMNS = {
    "voltage": {"label": "Voltage", "unit": "V"},
    "adc1": {"label": "ADC 1", "unit": "V", "setpoints": ["voltage"]},
}
PLOTS = {"Sweep": {"x": "voltage", "y": "adc1"}}

def run(adwin, params, stop_event, dataset, data_lock):
    # Read the hardware outside the data lock.
    with data_lock:
        dataset.append({"voltage": voltage, "adc1": reading})
</pre>Each append saves a row through QCoDeS. Post plotting opens the saved run.
Live plotting opens pyplotter automatically when enabled.'''
        back = widgets.Button(description='Back')
        back.on_click(lambda _: self._build_program_view(self.program_dropdown.value, self.current_module))
        self.program_area.children = [widgets.HTML(help_text), back]
