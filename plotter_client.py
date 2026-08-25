"""Launch pyplotter in its own process, without opening a command prompt."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


class PlotterClient:
    def __init__(self, python=None):
        self.python = python or sys.executable
        self.processes = []

    def open(self, run, plots, live=False, stop_event=None):
        folder = Path(run.database).parent / 'plotter_sessions'
        folder.mkdir(exist_ok=True)
        request = folder / f'{uuid.uuid4().hex}.json'
        ready = request.with_suffix('.ready')
        request.write_text(json.dumps({
            'database': run.database, 'run_id': run.run_id,
            'columns': run.columns, 'plots': plots, 'live': live,
        }), encoding='utf-8')
        with request.with_suffix('.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(
                [self.python, str(Path(__file__).with_name('pyplotter_window.py')), str(request)],
                stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.processes = [p for p in self.processes if p.poll() is None] + [process]
        deadline = time.monotonic() + 60
        while not ready.exists():
            if process.poll() is not None:
                raise RuntimeError(f'Pyplotter could not open. See {request.with_suffix(".log")}')
            if stop_event is not None and stop_event.is_set():
                process.terminate()
                process.wait(timeout=5)
                return
            if time.monotonic() >= deadline:
                process.terminate()
                process.wait(timeout=5)
                raise TimeoutError(f'Pyplotter did not become ready. See {request.with_suffix(".log")}')
            time.sleep(0.05)
        return process
