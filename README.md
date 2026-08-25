**# ADwin Pro II — driver and measurement GUI**

**Sarth Mhatre · Engineering Physics · IIT Indore**  

**Last updated: 30 September 2026**

Control an ADwin Pro II from Python, run measurement programs from a notebook

GUI, and view live or saved results in pyplotter. QCoDeS stores measurement

data. The current setup uses **one device, device 1**, with eight ADC and eight

DAC channels.

For standalone measurements and the driver's public operations, see the

[driver user manual](docs/driver_manual.tex). This README covers installation

and GUI use. Instructions for writing GUI-compatible programs are available

through the GUI's **? (Help)** button.

**## Repository layout**

```text

repository/

├── ADwin_Pro2_Generic_Purpose_Driver/

│   ├── adwin_pro2.py             # Python/QCoDeS driver

│   └── pro2_io.bas               # ADbasic source; compile before hardware use

├── compiled_programs/           # Python measurement routines shown by the GUI

├── docs/

│   ├── driver_manual.tex        # Driver-only manual; compile to PDF

│   └── screenshots/             # Add screenshots here

├── adwin_gui_v02.py             # Notebook GUI entry point

├── compiled_programs_panel.py

├── adc_monitor.py

├── data_store.py

├── plotting.py

├── plotter_client.py

├── pyplotter_window.py

├── ui_dispatch.py

├── requirements.txt

├── .gitignore

└── README.md

```

The compiled ADwin process is an additional file produced by ADbasic; it is not

the `.bas` source. `compiled_programs/` contains Python measurement routines,

not the ADwin processor binary. Runtime data and `.venv/` are created locally.

**## 1. Prerequisites**

\- Windows with **64-bit Python 3.13**, the Python version used for the GUI tests.

\- **Git**, available from the terminal, for the pinned pyplotter dependency.

\- For hardware use: the vendor's **ADwin software, Windows device drivers,

  processor boot files, and ADbasic compiler**. The Python `ADwin` package alone

  does not install the complete hardware toolchain.

\- An ADwin Pro II connected, powered, and reachable as **device 1** in the

  vendor's tools, using the connection appropriate for your lab's chassis.

\- The supplied process expects **ADC module 2, DAC module 3, channels 1–8, and

  process number 1**. Confirm these match the chassis.

The driver uses a ±10 V conversion range. Choose signals and output values

appropriate for the actual modules and sample; the software range does not

define the sample's allowable voltage.

**## 2. Create the Python environment**

Open PowerShell **in the repository root**:

```powershell

py -3.13 -m venv .venv

.\.venv\Scripts\python.exe -m pip install --upgrade pip

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe -m ipykernel install --user --name adwin-pro2 --display-name "Python (ADwin Pro II)"

.\.venv\Scripts\python.exe -m jupyterlab

```

Activation is optional because these commands use the environment's interpreter

explicitly. To activate it, use `.\.venv\Scripts\Activate.ps1`. If PowerShell

blocks that script, use the explicit commands above.

Create a notebook **in the repository root** and select **Python (ADwin Pro II)**

as its kernel. In VS Code, select that kernel or `.venv\Scripts\python.exe`.

Run this import check from a notebook or script whose working directory is the repository root. It checks the Python imports only; it does not connect to hardware:

```python

import sys
from pathlib import Path

import ADwin
import qcodes
import ipywidgets

from ADwin_Pro2_Generic_Purpose_Driver.adwin_pro2 import ADwinPro2
from adwin_gui_v02 import launch_gui

ROOT = Path.cwd()

print("Python:", sys.executable)
print("QCoDeS:", qcodes.__version__)

```

The driver must use `from qcodes import validators as vals`. The older
`from qcodes.utils import validators as vals` import fails with the QCoDeS
version pinned here.

**### Installed dependencies**

| Dependency | Purpose |

| --- | --- |

| ADwin 0.21.0 | Python access to the vendor's installed ADwin library |

| QCoDeS 0.61.0 | Driver parameters and measurement database |

| ipywidgets 8.1.5 | Notebook controls |

| JupyterLab 4.3.4 / ipykernel 6.29.5 | Notebook application and kernel |

| pyplotter, pinned revision | Native live/post plotting windows |

| scikit-rf 2.1.0 | Pyplotter dependency used in adapter tests |

Pip installs transitive dependencies, including Qt. Pyplotter is pinned because

the launcher uses its internal plot interface. Its scikit-rf compatibility

adjustment is contained in `pyplotter_window.py`.

**## 3. Prepare the ADwin process**

1. Open `ADwin_Pro2_Generic_Purpose_Driver/pro2_io.bas` in ADbasic.

2. Select the processor target matching your device and compile for **process 1**

   with the appropriate vendor include files.

3. Resolve compiler diagnostics and save the generated process binary. Record

   its full path; Python needs the binary, not the `.bas` file.

4. Locate the boot file appropriate for the processor in your ADwin installation.

**Source check:** the supplied `.bas` references `ADC_DATA` but the copy reviewed

here has no explicit declaration for it. If ADbasic reports it as undeclared,

resolve the acquisition-buffer declaration before compiling. No ADbasic

compilation or hardware run was performed as part of the GUI software tests.

When no boot file is supplied, the driver uses `ADwin12.btl` in the vendor boot

directory. Supply the correct boot file explicitly if that default does not

match your processor.

**## 4. Connect and launch**

After the import cell above, set the path to your compiled ADbasic process
file. The driver uses its configured default boot file unless you pass
`boot_file` explicitly. Constructing `ADwinPro2` **boots the device, loads the
process, and starts it**. Do this once at the start of a session, with no
measurement already running.

```python
PROCESS_FILE = ROOT / "path" / "to" / "your_compiled_process_file"

assert PROCESS_FILE.is_file(), "Set the correct compiled process-binary path."

adwin = ADwinPro2(
    "adwin",
    device_number=1,
    process_file=str(PROCESS_FILE),
)

# Initialize every stored setpoint before individual-channel operations.

adwin.set_all_dacs([0.0] * 8)

gui = launch_gui(

    adwin,

    programs_dir=str(ROOT / "compiled_programs"),

    database=str(ROOT / "data" / "experiments.db"),

    plotter_python=sys.executable,

)

```

Reuse this `adwin` instance. Its constructor is not a reconnect button; it

repeats boot and startup. Restart the kernel after updating imported modules.

The GUI is a **notebook widget**, with a fixed **1340 × 850 pixel** frame,

rounded buttons, and internal scrolling. Running the GUI module as a script

does not launch a desktop application. Pyplotter opens separate desktop windows;

use a local notebook session with desktop access.

\> **Screenshot placeholder — GUI overview**  

\> Add `docs/screenshots/01-gui-overview.png`: the full frame, menus, program

\> selector, parameters, ADC panel, and status line.

\<!-- Replace with: ![GUI overview](docs/screenshots/01-gui-overview.png) -->

**### Hardware-free trial**

If `simulated_sine.py` is included in `compiled_programs/`, use this instead of

the device connection cell:

```python

gui = launch_gui(

    None,

    programs_dir=str(ROOT / "compiled_programs"),

    database=str(ROOT / "data" / "simulation.db"),

    plotter_python=sys.executable,

)

```

Select **simulated_sine**, click **Load**, enable **Live plot in pyplotter**,

then click **Run**. Stay on **Compiled Programs**; manual controls require a

real driver. This optional simulator does not test a hardware connection.

**## 5. GUI controls**

**### Compiled Programs**

1. Select a program and click **Load**.

2. Review its parameters and declared ADC channels.

3. Optionally select **Live plot in pyplotter**. It is available only when the

   program declares live-plot support and plot definitions.

4. Click **Run** once. When enabled, pyplotter opens before acquisition begins.

5. Wait for completion, or press **Stop** and wait for the program to return

   and final saving to finish.

During a run, **Run, program selection, Load, Help, parameter edits, live-plot

selection, all menus, Post Plot, axis selection, and CSV export are disabled**.

They remain locked through final saving. Stop is cooperative: it does not

forcibly terminate arbitrary Python code or automatically zero outputs.

Output cleanup depends on the measurement program.

**Live ADC readings** displays the channels declared by the selected program

and retains their last values after the run. These monitor readings are not

necessarily the samples saved by the experiment. Monitoring requires the

generic I/O process; another device process needs a compatible monitor.

Programs declaring no ADC channels display no ADC cards.

For writing GUI-compatible programs, use **? (Help)** beside Load.

\> **Screenshot placeholder — active measurement**  

\> Add `docs/screenshots/02-running-measurement.png`: changing ADC readings,

\> disabled navigation/Run/Post Plot, and the Stop button.

\<!-- Replace with: ![Running measurement](docs/screenshots/02-running-measurement.png) -->

**### Live and post plotting**

Both modes read the **same QCoDeS database and run ID**. An existing viewer

stays attached to its run when another experiment starts.

\- **Live plot:** opens automatically on Run when enabled. No separate command

  prompt or `plotter` command is needed. Refreshes about every 0.5 seconds.

\- **POST PLOT:** after saving, choose X and Y columns and click to open pyplotter.

\- **SAVE CSV:** exports beside the database as `run_\<run_id>.csv`. Exporting

  that run again replaces its CSV file.

\- Closing a viewer does not stop acquisition. A viewer startup failure prevents

  acquisition and reports the log location.

\- Finalized partial results can be plotted after Stop or an error. Empty runs

  cannot be post-plotted.

Opening a post plot or exporting CSV briefly locks the GUI until the operation

completes. The integration supports **X/Y line plots**; heatmaps are not yet

implemented.

\> **Screenshot placeholder — pyplotter**  

\> Add `docs/screenshots/03-pyplotter.png`: a curve with axes, units, and run ID.

\<!-- Replace with: ![Pyplotter](docs/screenshots/03-pyplotter.png) -->

**### ADwin Control**

Use this page when no experiment is running.

| Control | Action |

| --- | --- |

| DAC value + **SET** | Applies the voltage. Editing the field alone does not apply it. |

| **USE / DISABLE** | Allows or blocks manual SET for that channel; does **not** zero or disconnect the output. |

| ADC panel | Repeatedly reads all eight ADC inputs. |

| **ZERO ALL DACs** | Sets all stored DAC setpoints to 0 V and requests output update. |

| **EMERGENCY STOP** | Requests the generic process's software emergency-zero state. |

| **RESET** | Clears emergency and command state; does not clear stored DAC setpoints. |

| **EXIT GUI** | Closes the widget and stops its monitoring; does not close the caller-owned driver or guarantee zero outputs. |

Manual value fields initially show zero; they are not device-output readback.

Emergency Stop/Reset are on this page, which cannot be opened during a run.

The experiment's **Stop** button is a different operation. Software emergency

zeroing needs a responsive device and running generic process; it is not a

hardware interlock.

\> **Screenshot placeholder — manual control**  

\> Add `docs/screenshots/04-manual-control.png`: DAC/ADC panels and action buttons.

\<!-- Replace with: ![Manual controls](docs/screenshots/04-manual-control.png) -->

**### ADwin Processes**

This page is currently marked **Under development**.

**## 6. Data and session shutdown**

With the launch example above:

```text

data/

├── experiments.db        # QCoDeS results, run parameters, and outcome metadata

├── run_1.csv             # Created only on CSV export

└── plotter_sessions/     # Viewer requests, readiness files, and startup logs

```

QCoDeS is the primary store. Results flush during append operations with a

0.2-second write period and again at completion. During a gap between appends,

a buffered point can wait longer. Plot refresh is separate, so live curves may

trail acquisition slightly.

The experiment owns its database writer; viewers use separate reader connections

in separate processes. The GUI serializes its device calls. Avoid competing

commands through other notebook cells, scripts, or driver instances during

acquisition: the GUI cannot lock unrelated callers.

Post Plot refers to the selected run in the current GUI session. Older runs

remain in the database; the GUI has no run-history browser yet. Preserve the

database when archiving measurements; CSV export is optional.

First wait for acquisition and saving to finish. For normal shutdown with the

generic process running and emergency state cleared:

```python

gui.close()

try:

    adwin.set_all_dacs([0.0] * 8)

finally:

    adwin.close()

```

`adwin.close()` stops the process but does not itself zero outputs. If emergency

mode is active or commands fail, follow the driver manual's recovery procedure;

a failed zero command is not confirmation of zero voltage.

**## 7. Troubleshooting**

| Symptom | Check |

| --- | --- |

| Missing Python module | Use the `.venv` notebook kernel and install requirements with that interpreter. |

| `validators` import error | Use `from qcodes import validators as vals`; restart the kernel. |

| Driver cannot be imported | Run the notebook from the repository root and check the folder and module names. |

| ADwin DLL, device, or boot error | Check vendor installation, device 1, boot file, and process-binary path. |

| `ADC_DATA` compiler error | Resolve the acquisition-buffer declaration before compiling the supplied source. |

| ADC timeout | Confirm process 1 is running, the generic binary and module numbers match, and emergency state is cleared. |

| Widgets display as text | Use a JupyterLab notebook with the registered kernel; refresh after installation. |

| Live checkbox disabled | The program has not declared supported live plots. |

| Post Plot disabled | Run still active/saving, no populated run selected, or a plot/export action is busy. |

| Plotter does not open | Read the reported log under `data/plotter_sessions/`; check the plotting interpreter and dependencies. |

| Stop takes time | The program must return cooperatively; final saving also keeps controls locked. |

| Duplicate instrument name | Reuse the existing instance or close it before creating another. |

**## Documentation and verification**

Compile `docs/driver_manual.tex` in a LaTeX editor or upload it to Overleaf.

It is standalone and needs no external images. Add the four screenshots above

and replace the placeholders with the image links supplied in HTML comments.

The current software passed eight hardware-free tests covering run restrictions,

Stop/error handling, saving, and real pyplotter live/post curves. Driver imports

were checked with QCoDeS 0.61.0. This does not establish hardware or ADbasic

process validation.