"""Numeric ADC monitoring sharing complete driver calls with an experiment."""
import functools
import threading
import time
from html import escape

import ipywidgets as widgets


class SerializedDriver:
    """Serialize methods and QCoDeS parameter calls, including result reads."""

    def __init__(self, target, lock=None):
        self._target = target
        self._lock = lock if lock is not None else threading.RLock()

    def __getattr__(self, name):
        value = getattr(self._target, name)
        if name == 'adw':
            return SerializedDriver(value, self._lock)
        if name.startswith(('adc', 'dac')) and hasattr(value, 'get'):
            return SerializedDriver(value, self._lock)
        if callable(value):
            @functools.wraps(value)
            def call(*args, **kwargs):
                with self._lock:
                    return value(*args, **kwargs)
            return call
        return value

    def __call__(self, *args, **kwargs):
        with self._lock:
            return self._target(*args, **kwargs)


class ADCMonitor:
    def __init__(self, adwin, dispatch=None):
        self.adwin = adwin
        self.dispatch = dispatch or (lambda callback: callback())
        self.channels = []
        self.readouts = {}
        self.stop_event = threading.Event()
        self.thread = None
        self.status = widgets.HTML('Select a program to configure ADC channels.')
        self.cards = widgets.HBox(layout=widgets.Layout(grid_gap='8px', flex_flow='row wrap'))
        self.widget = widgets.VBox(
            [widgets.HTML('<b>Live ADC readings</b>'), self.cards, self.status],
            layout=widgets.Layout(height='166px', min_height='166px', width='100%',
                                  padding='10px', border='1px solid #dce2ea', overflow='auto'))

    def configure(self, channels):
        channels = list(channels)
        if any(type(ch) is not int or not 1 <= ch <= 8 for ch in channels):
            raise ValueError('ADC_CHANNELS must contain channel numbers from 1 to 8.')
        self.channels = list(dict.fromkeys(channels))
        self.readouts = {ch: widgets.HTML(self._card(ch, '—')) for ch in self.channels}
        self.cards.children = list(self.readouts.values())
        self.status.value = ('Ready — readings start when you press Run.' if channels
                             else 'This program declares no ADC channels.')

    @staticmethod
    def _card(channel, value):
        return (f'<div style="width:106px;padding:8px;background:#f3f6fa;border-radius:9px;'
                f'font-family:monospace"><span>ADC {channel}</span><br>'
                f'<b>{escape(value)}</b></div>')

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError('ADC monitor is still stopping.')
        self.stop_event = threading.Event()
        if self.channels:
            def reset():
                for ch in self.channels:
                    self.readouts[ch].value = self._card(ch, '—')
                self.status.value = 'Monitoring…'
            self.dispatch(reset)
            self.thread = threading.Thread(target=self._worker, daemon=True)
            self.thread.start()

    def _worker(self):
        while not self.stop_event.is_set():
            try:
                with self.adwin._lock:
                    if self.stop_event.is_set():
                        break
                    values = self.adwin.get_all_adcs()
                readings = {ch: float(values[ch - 1]) for ch in self.channels}
                self.dispatch(lambda readings=readings: self._show_readings(readings))
            except Exception as exc:
                message = f'ADC read failed: {escape(str(exc))}'
                self.dispatch(lambda message=message: setattr(self.status, 'value', message))
            self.stop_event.wait(0.25)

    def _show_readings(self, readings):
        for ch, value in readings.items():
            self.readouts[ch].value = self._card(ch, f'{value: .6f} V')
        self.status.value = f'Updated {time.strftime("%H:%M:%S")} · monitoring'

    def finish(self, state):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join()
        if self.channels:
            self.dispatch(lambda: setattr(self.status, 'value', f'{state} — last readings retained.'))
