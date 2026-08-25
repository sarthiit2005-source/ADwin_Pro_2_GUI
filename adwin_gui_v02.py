
import os
import threading
import ipywidgets as widgets
from IPython.display import display

from compiled_programs_panel import CompiledProgramsPanel
from adc_monitor import SerializedDriver


class ADwinGUI:
    """Main GUI. Receives an already-created ADwinPro2 instance."""

    def __init__(self, adwin, programs_dir="compiled_programs", database=None, plotter_python=None):
        self.adwin = SerializedDriver(adwin)
        self.programs_dir = programs_dir

        self.programs_panel = CompiledProgramsPanel(
            adwin=self.adwin,
            programs_dir=self.programs_dir,
            set_status=self._set_status,
            set_navigation_locked=self._lock_navigation,
            database=database,
            plotter_python=plotter_python,
        )

        self.adc_stop_event = threading.Event()
        self.adc_thread = None
        self.dac_enabled = [True] * 8
        self.dac_controls = []
        self.adc_readouts = []

        self._build_widgets()
        self._build_layout()
        self.show_programs()

    def _build_widgets(self):
        self.content = widgets.VBox(layout=widgets.Layout(
            height='770px', min_height='770px', overflow='auto', width='100%'))
        self.status = widgets.HTML(
            "<span style='color:#777;'>Ready</span>",
            layout=widgets.Layout(height="24px")
        )

        self.programs_btn = self._menu_button("Compiled Programs")
        self.control_btn = self._menu_button("ADwin Control")
        self.processes_btn = self._menu_button("ADwin Processes")

        self.programs_btn.on_click(lambda b: self.show_programs())
        self.control_btn.on_click(lambda b: self.show_control())
        self.processes_btn.on_click(lambda b: self.show_processes())

    def _menu_button(self, text):
        return widgets.Button(
            description=text,
            layout=widgets.Layout(width="185px", height="40px"),
            style={"button_color": "#f4f4f4"}
        )

    def _build_layout(self):
        sidebar = widgets.VBox(
            [
                widgets.HTML(
                    "<b style='font-size:17px;'>ADwin</b>",
                    layout=widgets.Layout(height="35px")
                ),
                self.programs_btn,
                self.control_btn,
                self.processes_btn,
            ],
            layout=widgets.Layout(width="215px", min_width="215px", padding="12px")
        )

        main = widgets.VBox(
            [self.content, self.status],
            layout=widgets.Layout(width="1125px", min_width="1125px", padding="18px")
        )

        self.root = widgets.HBox(
            [sidebar, main],
            layout=widgets.Layout(width="1340px", min_width="1340px", max_width="1340px",
                                  height="850px", min_height="850px", max_height="850px",
                                  overflow="hidden", border="1px solid #dce2ea")
        )
        self.root.add_class('adwin-fixed-gui')
        self.css = widgets.HTML('''<style>
        .adwin-fixed-gui, .adwin-fixed-gui * { box-sizing: border-box; }
        .adwin-fixed-gui { border-radius: 14px; background: #fff; }
        .adwin-fixed-gui .jupyter-button,
        .adwin-fixed-gui .widget-button { border-radius: 9px !important; }
        </style>''')
        main.children = (self.css, self.content, self.status)

    def _stop_adc_updates(self):
        self.adc_stop_event.set()
        thread = self.adc_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.3)
        self.adc_thread = None

    def _start_adc_updates(self):
        self._stop_adc_updates()
        self.adc_stop_event.clear()
        self.adc_thread = threading.Thread(
            target=self._adc_update_worker,
            daemon=True
        )
        self.adc_thread.start()

    def _adc_update_worker(self):
        while not self.adc_stop_event.is_set():
            try:
                values = self.adwin.get_all_adcs()
                if isinstance(values, dict):
                    values = [values.get(i, values.get(i + 1, 0.0)) for i in range(8)]

                for channel, value in enumerate(values[:8], start=1):
                    if channel <= len(self.adc_readouts):
                        self.adc_readouts[channel - 1].value = (
                            "<span style='font-family:monospace;'>"
                            f"ADC {channel}: {float(value): .6f} V"
                            "</span>"
                        )
            except Exception as exc:
                if not self.adc_stop_event.is_set():
                    self.status.value = (
                        "<span style='font-family:monospace;'>"
                        f"<span style='color:#d9534f;'>●</span> ADC ERROR: {exc}"
                        "</span>"
                    )

            self.adc_stop_event.wait(0.25)

    def show_programs(self):
        if self.programs_panel.busy:
            return
        self._stop_adc_updates()
        self.content.children = [self.programs_panel.build()]

    def _set_status(self, message):
        self.status.value = message

    def _lock_navigation(self, locked):
        for button in (self.programs_btn, self.control_btn, self.processes_btn):
            button.disabled = locked

    def show_control(self):
        if self.programs_panel.busy:
            self._set_status('Stop the running program before opening manual control.')
            return
        self._stop_adc_updates()
        self.dac_controls = []
        self.adc_readouts = []

        dac_rows = []
        for i in range(1, 9):
            label = widgets.Label(
                f"DAC {i}",
                layout=widgets.Layout(width="65px")
            )
            value = widgets.FloatText(
                value=0.0,
                step=0.001,
                layout=widgets.Layout(width="140px", height="30px")
            )
            set_button = widgets.Button(
                description="SET",
                layout=widgets.Layout(width="90px", height="30px")
            )
            use_button = widgets.Button(
                description="USE",
                button_style="success",
                layout=widgets.Layout(width="60px", height="30px")
            )
            indicator = widgets.HTML(
                "<span style='font-size:17px;color:#777;'>●</span>",
                layout=widgets.Layout(width="20px", height="30px")
            )

            self.dac_controls.append({
                "value": value,
                "set": set_button,
                "use": use_button,
                "indicator": indicator,
            })

            def set_dac(b, ch=i, v=value, set_btn=set_button,
                        use_btn=use_button, dot=indicator):
                if not self.dac_enabled[ch - 1]:
                    self.status.value = (
                        f"<span style='font-family:monospace;'>"
                        f"<span style='color:#d9534f;'>●</span> "
                        f"DAC {ch} DISABLED"
                        f"</span>"
                    )
                    return

                # The controls remain greyed out until this ADwin operation finishes.
                set_btn.disabled = True
                use_btn.disabled = True
                v.disabled = True
                dot.value = "<span style='font-size:17px;color:#f0ad00;'>●</span>"

                def worker():
                    try:
                        voltage = float(v.value)
                        getattr(self.adwin, f"dac{ch}").set(voltage)

                        dot.value = "<span style='font-size:17px;color:#4caf50;'>●</span>"
                        self.status.value = (
                            f"<span style='font-family:monospace;'>"
                            f"<span style='color:#4caf50;'>●</span> "
                            f"DAC {ch} SET → {voltage:.6f} V"
                            f"</span>"
                        )
                    except Exception as exc:
                        dot.value = "<span style='font-size:17px;color:#d9534f;'>●</span>"
                        self.status.value = (
                            f"<span style='font-family:monospace;'>"
                            f"<span style='color:#d9534f;'>●</span> "
                            f"DAC {ch} ERROR: {exc}"
                            f"</span>"
                        )
                    finally:
                        set_btn.disabled = False
                        use_btn.disabled = False
                        v.disabled = False

                threading.Thread(target=worker, daemon=True).start()

            def toggle_dac(b, ch=i, button=use_button):
                enabled = not self.dac_enabled[ch - 1]
                self.dac_enabled[ch - 1] = enabled

                if enabled:
                    button.description = "USE"
                    button.button_style = "success"
                    self.status.value = (
                        f"<span style='font-family:monospace;'>"
                        f"<span style='color:#4caf50;'>●</span> DAC {ch} ENABLED"
                        f"</span>"
                    )
                else:
                    button.description = "DISABLE"
                    button.button_style = "danger"
                    self.status.value = (
                        f"<span style='font-family:monospace;'>"
                        f"<span style='color:#d9534f;'>●</span> DAC {ch} DISABLED"
                        f"</span>"
                    )

            set_button.on_click(set_dac)
            use_button.on_click(toggle_dac)

            dac_rows.append(
                widgets.HBox(
                    [label, value, set_button, use_button, indicator],
                    layout=widgets.Layout(
                        align_items="center",
                        grid_gap="4px",
                        height="42px"
                    )
                )
            )

        adc_labels = []
        for i in range(1, 9):
            label = widgets.HTML(
                value=(
                    "<span style='font-family:monospace;'>"
                    f"ADC {i}: 0.000000 V"
                    "</span>"
                ),
                layout=widgets.Layout(width="190px", height="30px")
            )
            adc_labels.append(label)

        self.adc_readouts = adc_labels

        self.emergency_button = widgets.Button(
            description="EMERGENCY STOP",
            button_style="danger",
            layout=widgets.Layout(width="180px", height="40px")
        )
        self.reset_button = widgets.Button(
            description="RESET",
            layout=widgets.Layout(width="100px", height="40px")
        )
        self.zero_all_button = widgets.Button(
            description="ZERO ALL DACs",
            layout=widgets.Layout(width="140px", height="40px")
        )
        self.exit_button = widgets.Button(
            description="EXIT GUI",
            layout=widgets.Layout(width="100px", height="40px")
        )

        self.emergency_button.on_click(self._emergency_stop)
        self.reset_button.on_click(self._reset)
        self.zero_all_button.on_click(self._zero_all)
        self.exit_button.on_click(self.close)

        dac_box = widgets.VBox(
            [widgets.HTML("<b>DAC OUTPUTS</b>")] + dac_rows,
            layout=widgets.Layout(
                border="1px solid #222",
                padding="12px",
                width="430px",
                overflow="hidden"
            )
        )
        adc_box = widgets.VBox(
            [widgets.HTML("<b>ADC INPUTS</b>")] + adc_labels,
            layout=widgets.Layout(
                border="1px solid #222",
                padding="12px",
                width="240px",
                overflow="hidden"
            )
        )

        self.content.children = [
            widgets.HTML("<h3>ADwin Control</h3>"),
            widgets.HBox(
                [dac_box, adc_box],
                layout=widgets.Layout(
                    grid_gap="25px",
                    align_items="flex-start"
                )
            ),
            widgets.HBox(
                [
                    self.emergency_button,
                    self.reset_button,
                    self.zero_all_button,
                    self.exit_button,
                ],
                layout=widgets.Layout(
                    grid_gap="10px",
                    margin="18px 0 0 0",
                    align_items="center"
                )
            )
        ]

        self.status.value = (
            "<span style='font-family:monospace;'>"
            "<span style='color:#4caf50;'>●</span> READY"
            "</span>"
        )
        self._start_adc_updates()

    def _emergency_stop(self, _=None):
        try:
            self.adwin.emergency_stop()

            # Reflect the emergency state in the GUI immediately.
            for control in self.dac_controls:
                control["set"].disabled = True
                control["use"].disabled = True
                control["value"].disabled = True
                control["indicator"].value = (
                    "<span style='font-size:17px;color:#d9534f;'>●</span>"
                )

            self.status.value = (
                "<span style='font-family:monospace;'>"
                "<span style='color:#d9534f;'>●</span> "
                "EMERGENCY STOP ACTIVE"
                "</span>"
            )
        except Exception as exc:
            self.status.value = (
                f"<span style='font-family:monospace;'>"
                f"<span style='color:#d9534f;'>●</span> "
                f"EMERGENCY ERROR: {exc}"
                f"</span>"
            )

    def _reset(self, _=None):
        try:
            self.adwin.emergency_reset()

            for i, control in enumerate(self.dac_controls):
                enabled = self.dac_enabled[i]
                control["set"].disabled = not enabled
                control["use"].disabled = False
                control["value"].disabled = False
                control["indicator"].value = (
                    "<span style='font-size:17px;color:#777;'>●</span>"
                )

            self.status.value = (
                "<span style='font-family:monospace;'>"
                "<span style='color:#f0ad00;'>●</span> "
                "RESET / READY"
                "</span>"
            )
        except Exception as exc:
            self.status.value = (
                f"<span style='font-family:monospace;'>"
                f"<span style='color:#d9534f;'>●</span> "
                f"RESET ERROR: {exc}"
                f"</span>"
            )

    def _zero_all(self, _=None):
        try:
            # Use the same externally-owned ADwinPro2 instance.
            self.adwin.set_all_dacs([0.0] * 8)

            for control in self.dac_controls:
                control["value"].value = 0.0
                control["indicator"].value = (
                    "<span style='font-size:17px;color:#4caf50;'>●</span>"
                )

            self.status.value = (
                "<span style='font-family:monospace;'>"
                "<span style='color:#4caf50;'>●</span> "
                "ALL DACs → 0 V"
                "</span>"
            )
        except Exception as exc:
            self.status.value = (
                f"<span style='font-family:monospace;'>"
                f"<span style='color:#d9534f;'>●</span> "
                f"ZERO ERROR: {exc}"
                f"</span>"
            )

    def close(self, _=None):
        # The ADwinPro2 object belongs to the caller, so EXIT GUI
        # does not close the physical ADwin connection.
        self.programs_panel.stop()
        self._stop_adc_updates()

        try:
            self.root.close()
        except Exception:
            pass

        self.status.value = (
            "<span style='font-family:monospace;'>"
            "<span style='color:#777;'>●</span> GUI CLOSED"
            "</span>"
        )

    def show_processes(self):
        if self.programs_panel.busy:
            return
        self._stop_adc_updates()
        self.content.children = [
            widgets.HTML("<h3>ADwin Processes</h3>"),
            widgets.HTML(
                "<div style='padding:12px;border-radius:10px;background:#f5f5f5;'>"
                "Under development"
                "</div>"
            )
        ]


def launch_gui(adwin, programs_dir="compiled_programs", database=None, plotter_python=None):
    gui = ADwinGUI(adwin, programs_dir, database, plotter_python)
    display(gui.root)
    return gui
