import time
import threading
import ADwin
import qcodes as qc
from qcodes.instrument import Instrument
from qcodes import validators as vals


class ADwinPro2(Instrument):

    DAC_MODULE = 3
    ADC_MODULE = 2
    DAC_COUNT = 8
    ADC_COUNT = 8

    MIN_VOLTAGE = -10.0
    MAX_VOLTAGE = 10.0
    DAC_ZERO_CODE = 32768
    PROCESS_NUMBER = 1

    CMD_NONE = 0
    CMD_SET_DAC = 1
    CMD_READ_ADC = 2
    CMD_SET_ALL_DAC = 3

    PAR_EMERGENCY = 17
    PAR_COMMAND = 27
    PAR_DONE = 28
    PAR_STATE = 29
    PAR_ABORTED = 30

    ADC_PAR_START = 9
    DAC_ZERO_PAR_START = 18

    def __init__(self, name, device_number=1, boot_file=None,
                 process_file=None, timeout=5.0, poll_interval=0.001, **kwargs):
        super().__init__(name, **kwargs)

        self.device_number = device_number
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._command_lock = threading.Lock()
        self.adw = ADwin.ADwin()

        if boot_file is None:
            boot_file = self.adw.ADwindir + r"\ADwin12.btl"
        if process_file is None:
            raise ValueError("process_file must point to the compiled Pro II ADbasic process.")

        self.boot(boot_file)
        self.load_process(process_file)
        self.set_par(26, 5)
        self.start_process()
        self._create_parameters()
        self._clear_handshake()

    def boot(self, boot_file):
        self.adw.Boot(boot_file)

    def load_process(self, process_file):
        self.adw.Load_Process(process_file)

    def start_process(self, process_number=None):
        self.adw.Start_Process(self.PROCESS_NUMBER if process_number is None else process_number)

    def stop_process(self, process_number=None):
        self.adw.Stop_Process(self.PROCESS_NUMBER if process_number is None else process_number)

    def process_status(self, process_number=None):
        return self.adw.Process_Status(self.PROCESS_NUMBER if process_number is None else process_number)

    def get_par(self, par_number):
        return self.adw.Get_Par(par_number)

    def set_par(self, par_number, value):
        self.adw.Set_Par(par_number, int(value))

    def get_fpar(self, par_number):
        return self.adw.Get_FPar(par_number)

    def set_fpar(self, par_number, value):
        self.adw.Set_FPar(par_number, float(value))

    # VOLTAGE CONVERSION

    @staticmethod
    def convert_V_to_bin(voltage):
        binary = int((voltage + 10.0) / 20.0 * 65535)
        return max(0, min(65535, binary))

    @staticmethod
    def convert_bin_to_V(binary):
        return binary / 65535.0 * 20.0 - 10.0

    # HANDSHAKE

    def _clear_handshake(self):
        self.set_par(self.PAR_COMMAND, self.CMD_NONE)
        self.set_par(self.PAR_DONE, 0)
        self.set_par(self.PAR_STATE, 0)
        self.set_par(self.PAR_ABORTED, 0)

    def _wait_for_completion(self):
        start = time.monotonic()

        while True:
            if self.get_par(self.PAR_ABORTED) == 1:
                self.set_par(self.PAR_DONE, 0)
                raise RuntimeError("ADwin command was aborted by emergency stop.")

            if self.get_par(self.PAR_DONE) == 1:
                self.set_par(self.PAR_DONE, 0)
                return

            if time.monotonic() - start >= self.timeout:
                self.set_par(self.PAR_COMMAND, self.CMD_NONE)
                self.set_par(self.PAR_STATE, 0)
                raise TimeoutError("Timed out waiting for ADwin command to complete.")

            time.sleep(self.poll_interval)

    def _send_command(self, command):
        with self._command_lock:
            self.set_par(self.PAR_DONE, 0)
            self.set_par(self.PAR_ABORTED, 0)
            self.set_par(self.PAR_COMMAND, command)
            self._wait_for_completion()

    # DAC

    def _set_dac(self, channel, voltage):
        if not 1 <= channel <= self.DAC_COUNT:
            raise ValueError("DAC channel must be between 1 and 8.")
        self.set_par(channel, self.convert_V_to_bin(voltage))
        self._send_command(self.CMD_SET_DAC)

    def _get_dac(self, channel):
        if not 1 <= channel <= self.DAC_COUNT:
            raise ValueError("DAC channel must be between 1 and 8.")
        return self.convert_bin_to_V(self.get_par(channel))

    # ALL DACs

    def set_all_dacs(self, voltages):
        if len(voltages) != self.DAC_COUNT:
            raise ValueError("Exactly 8 DAC voltages are required.")

        with self._command_lock:
            self.set_par(self.PAR_DONE, 0)
            self.set_par(self.PAR_ABORTED, 0)

            for channel, voltage in enumerate(voltages, start=1):
                if not self.MIN_VOLTAGE <= voltage <= self.MAX_VOLTAGE:
                    raise ValueError(
                        f"DAC{channel} voltage must be between "
                        f"{self.MIN_VOLTAGE} and {self.MAX_VOLTAGE} V."
                    )
                self.set_par(channel, self.convert_V_to_bin(voltage))

            self.set_par(self.PAR_COMMAND, self.CMD_SET_ALL_DAC)
            self._wait_for_completion()

    def get_all_dacs(self):
        return [self._get_dac(ch) for ch in range(1, self.DAC_COUNT + 1)]

    # ADC

    def _get_adc(self, channel):
        if not 1 <= channel <= self.ADC_COUNT:
            raise ValueError("ADC channel must be between 1 and 8.")
        self._send_command(self.CMD_READ_ADC)
        par_number = self.ADC_PAR_START + channel - 1
        return self.convert_bin_to_V(self.get_par(par_number))

    def get_all_adcs(self):
        self._send_command(self.CMD_READ_ADC)
        return [
            self.convert_bin_to_V(self.get_par(self.ADC_PAR_START + ch - 1))
            for ch in range(1, self.ADC_COUNT + 1)
        ]

    # DAC ZERO CONTROL

    def zero_dac(self, channel):
        if not 1 <= channel <= self.DAC_COUNT:
            raise ValueError("DAC channel must be between 1 and 8.")
        flag_par = self.DAC_ZERO_PAR_START + channel - 1
        with self._command_lock:
            self.set_par(flag_par, 1)
            self.set_par(self.PAR_DONE, 0)
            self.set_par(self.PAR_ABORTED, 0)
            self.set_par(self.PAR_COMMAND, self.CMD_SET_DAC)
            self._wait_for_completion()

    def restart_dac(self, channel):
        if not 1 <= channel <= self.DAC_COUNT:
            raise ValueError("DAC channel must be between 1 and 8.")
        flag_par = self.DAC_ZERO_PAR_START + channel - 1
        with self._command_lock:
            self.set_par(flag_par, 0)
            self.set_par(self.PAR_DONE, 0)
            self.set_par(self.PAR_ABORTED, 0)
            self.set_par(self.PAR_COMMAND, self.CMD_SET_DAC)
            self._wait_for_completion()

    # EMERGENCY STOP

    def emergency_stop(self):
        self.set_par(self.PAR_EMERGENCY, 1)

    def emergency_reset(self):
        self.set_par(self.PAR_EMERGENCY, 0)
        self.set_par(self.PAR_ABORTED, 0)
        self.set_par(self.PAR_DONE, 0)
        self.set_par(self.PAR_COMMAND, self.CMD_NONE)
        self.set_par(self.PAR_STATE, 0)

    # QCoDeS PARAMETERS

    def _create_parameters(self):
        for channel in range(1, self.DAC_COUNT + 1):
            name = f"dac{channel}"
            setattr(self, name, qc.Parameter(
                name=name,
                label=f"DAC {channel}",
                unit="V",
                get_cmd=lambda ch=channel: self._get_dac(ch),
                set_cmd=lambda value, ch=channel: self._set_dac(ch, value),
                vals=vals.Numbers(self.MIN_VOLTAGE, self.MAX_VOLTAGE),
                instrument=self
            ))

        for channel in range(1, self.ADC_COUNT + 1):
            name = f"adc{channel}"
            setattr(self, name, qc.Parameter(
                name=name,
                label=f"ADC {channel}",
                unit="V",
                get_cmd=lambda ch=channel: self._get_adc(ch),
                vals=vals.Numbers(self.MIN_VOLTAGE, self.MAX_VOLTAGE),
                instrument=self
            ))

        self.emergency = qc.Parameter(
            name="emergency",
            label="Emergency Stop",
            unit="",
            get_cmd=lambda: self.get_par(self.PAR_EMERGENCY),
            set_cmd=lambda value: self.set_par(self.PAR_EMERGENCY, int(value)),
            vals=vals.Enum(0, 1),
            instrument=self
        )

    def ask(self, cmd):
        if cmd == "*IDN?":
            return "ADwin Pro II"
        raise ValueError(f"Unknown command: {cmd}")

    def ask_raw(self, cmd):
        return self.ask(cmd)

    def write(self, cmd):
        raise NotImplementedError("Use QCoDeS parameters or set_par() instead.")

    def close(self):
        try:
            if self.process_status() == 1:
                self.stop_process()
        finally:
            super().close()
