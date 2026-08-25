PROGRAM_NAME = "Physical DAC1 → ADC1 Sweep"
ADC_CHANNELS = [1]
SUPPORTS_LIVE_PLOT = True
DATA_COLUMNS = {
    'voltage': {'label': 'DAC 1 voltage', 'unit': 'V'},
    'adc1': {'label': 'ADC 1', 'unit': 'V', 'setpoints': ['voltage']},
}

PARAMETERS = {
    "start_voltage": {"type": "float", "default": 0.0, "unit": "V"},
    "stop_voltage": {"type": "float", "default": 1.0, "unit": "V"},
    "step_voltage": {"type": "float", "default": 0.1, "unit": "V"},
    "settle_ms": {"type": "float", "default": 100.0, "unit": "ms"},
}

PLOTS = {
    "DAC1_vs_ADC1": {
        "x": "voltage",
        "y": "adc1",
        "x_label": "DAC1 Voltage (V)",
        "y_label": "ADC1 Voltage (V)",
    }
}


def run(adwin, params, stop_event, dataset, data_lock):
    """Physically sweep DAC1 from 0 to 1 V and read ADC1 at each point."""
    import time

    start = float(params["start_voltage"])
    stop = float(params["stop_voltage"])
    step = float(params["step_voltage"])
    settle = float(params["settle_ms"]) / 1000.0

    if step <= 0:
        raise ValueError("step_voltage must be > 0")

    # Integer indexing avoids floating-point accumulation such as 0.30000000004.
    count = int(round((stop - start) / step))

    for index in range(count + 1):
        if stop_event.is_set():
            break

        voltage = round(start + index * step, 12)

        # Physical output: DAC channel 1.
        adwin.dac1.set(voltage)

        if stop_event.wait(settle):
            break

        # Physical measurement: ADC channel 1.
        adc1 = adwin.adc1.get()

        with data_lock:
            dataset.append({
                "voltage": voltage,
                "adc1": float(adc1),
            })
