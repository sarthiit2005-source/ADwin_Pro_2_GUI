"""Try the complete plotting workflow without touching ADwin hardware."""
import math

PROGRAM_NAME = 'Simulated sine wave'
ADC_CHANNELS = []
SUPPORTS_LIVE_PLOT = True
PARAMETERS = {
    'duration': {'type': 'float', 'default': 10.0, 'unit': 's'},
    'frequency': {'type': 'float', 'default': 1.0, 'unit': 'Hz'},
    'amplitude': {'type': 'float', 'default': 1.0, 'unit': 'V'},
}
DATA_COLUMNS = {
    'time': {'label': 'Time', 'unit': 's'},
    'signal': {'label': 'Simulated signal', 'unit': 'V', 'setpoints': ['time']},
}
PLOTS = {'Sine wave': {'x': 'time', 'y': 'signal'}}


def run(adwin, params, stop_event, dataset, data_lock):
    if params['duration'] < 0:
        raise ValueError('Duration must be non-negative.')
    for index in range(int(params['duration'] / 0.05) + 1):
        if stop_event.is_set():
            break
        t = index * 0.05
        value = params['amplitude'] * math.sin(2 * math.pi * params['frequency'] * t)
        with data_lock:
            dataset.append({'time': t, 'signal': value})
        if stop_event.wait(0.05):
            break
