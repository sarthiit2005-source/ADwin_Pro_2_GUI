"""One QCoDeS database for experiment results and both plotting modes."""
from contextlib import contextmanager
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import threading


@dataclass(frozen=True)
class SavedRun:
    database: str
    run_id: int
    columns: dict
    points: int


def program_columns(module):
    """Use explicit column metadata, or infer basic columns from older PLOTS."""
    columns = {name: dict(info) for name, info in getattr(module, 'DATA_COLUMNS', {}).items()}
    if not columns:
        for plot in getattr(module, 'PLOTS', {}).values():
            x, y = plot['x'], plot['y']
            columns.setdefault(x, {'label': x, 'unit': ''})
            columns.setdefault(y, {'label': y, 'unit': '', 'setpoints': [x]})
    for name, info in columns.items():
        if not name.isidentifier():
            raise ValueError(f'Invalid data column: {name}')
        for axis in info.get('setpoints', []):
            if axis not in columns or columns[axis].get('setpoints'):
                raise ValueError(f'{name}: setpoints must name independent DATA_COLUMNS.')
    return columns


class RunWriter:
    """Append-only adapter. The experiment worker owns the database connection."""
    def __init__(self, saver, columns, lock):
        self.saver = saver
        self.columns = columns
        self.lock = lock
        self.owner = threading.get_ident()
        self.points = 0
        self.closed = False

    def append(self, row):
        with self.lock:
            if self.closed:
                raise RuntimeError('This run has already finished.')
            if threading.get_ident() != self.owner:
                raise RuntimeError('Write results from the experiment worker only.')
            if set(row) != set(self.columns):
                raise ValueError('Each result row must match DATA_COLUMNS exactly.')
            self.saver.add_result(*[(name, float(row[name])) for name in self.columns])
            self.points += 1

    def __len__(self):
        return self.points


class DataStore:
    def __init__(self, database):
        self.database = str(Path(database).resolve())
        self.write_lock = threading.RLock()

    @contextmanager
    def run(self, name, columns, parameters, stop_event):
        from qcodes.dataset import Measurement, load_or_create_experiment
        from qcodes.dataset.sqlite.database import connect

        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        # Explicit connections avoid changing QCoDeS' global database selection.
        connection = connect(self.database)
        writer = None
        try:
            experiment = load_or_create_experiment('ADwin GUI', 'device', conn=connection)
            measurement = Measurement(exp=experiment, name=name)
            measurement.write_period = 0.2
            for dependent in (False, True):
                for column, info in columns.items():
                    if bool(info.get('setpoints')) == dependent:
                        measurement.register_custom_parameter(
                            column, label=info.get('label', column), unit=info.get('unit', ''),
                            setpoints=tuple(info.get('setpoints', ())), paramtype='numeric')
            with measurement.run(write_in_background=False) as saver:
                writer = RunWriter(saver, columns, self.write_lock)
                saver.dataset.add_metadata('program_parameters', json.dumps(parameters))
                saver.dataset.add_metadata('gui_columns', json.dumps(columns))
                try:
                    yield writer
                except BaseException as exc:
                    saver.dataset.add_metadata('gui_outcome', 'error')
                    saver.dataset.add_metadata('gui_error', str(exc))
                    raise
                else:
                    saver.dataset.add_metadata('gui_outcome', 'stopped' if stop_event.is_set() else 'finished')
                finally:
                    with self.write_lock:
                        writer.closed = True
                        saver.flush_data_to_database(block=True)
            # Measurement's context marks the run complete after the final flush.
        finally:
            if writer is not None:
                writer.closed = True
            connection.close()

    @staticmethod
    def saved_run(writer):
        dataset = writer.saver.dataset
        return SavedRun(dataset.path_to_db, dataset.run_id, writer.columns, writer.points)


def read_columns(run):
    """Open a fresh reader connection; never share the writer's connection."""
    from qcodes.dataset import load_by_id
    from qcodes.dataset.sqlite.database import connect

    connection = connect(run.database)
    try:
        dataset = load_by_id(run.run_id, conn=connection)
        # Read completion first: if the writer finishes during the data read,
        # the viewer will refresh once more instead of stopping on stale data.
        completed = dataset.completed
        columns = {}
        for group in dataset.get_parameter_data().values():
            for name, values in group.items():
                columns.setdefault(name, values.reshape(-1))
        return columns, completed
    finally:
        connection.close()


def save_csv(run, path):
    columns, completed = read_columns(run)
    if not completed:
        raise RuntimeError('Wait for this run to finish saving.')
    names = list(run.columns)
    with open(path, 'w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(names)
        writer.writerows(zip(*(columns[name] for name in names)))
