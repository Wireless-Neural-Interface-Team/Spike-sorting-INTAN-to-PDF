#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Qt GUI to run the full Intan -> sorting -> PDF pipeline.

This script lets a user fill all required inputs from a form instead of
editing the main Python script manually.

High-level behavior:
  - Collect runtime paths and processing parameters from the user.
  - Run the full pipeline in a background worker thread.
  - Keep all Qt UI updates on the main thread (thread-safe).
  - Show progress and errors in a log panel.
"""

import os
import json
import time
import ctypes
import threading
import traceback
import multiprocessing
from queue import Empty

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QComboBox,
    QGroupBox,
    QTextEdit,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QMenu,
    QDialog,
    QDialogButtonBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction

from trigger_class import Trigger
from timestamps_class import TimestampsParameters
from sorter_class import Sorter
from protocol_class import Protocol
from intan_class import IntanFile
from probe_class import Probe
from pipeline_class import Pipeline
from pdf_generator_class import PDFGenerator


class PipelineGUI(QMainWindow):
    log_signal = Signal(str)
    progress_signal = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpikeSorting Pipeline Launcher")
        self.resize(960, 680)
        self._session_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_last_session.json")

        # Form field values (we use QLineEdit.text() etc. directly, no StringVar)
        self._protocol_params = None
        self._trigger_widgets = []
        self._stop_requested = False
        self._pipeline_process = None
        self._log_queue = None
        self._queue_reader_thread = None
        self.log_signal.connect(self._log_impl)
        self.progress_signal.connect(self._progress_impl)
        self._load_last_session()

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Top bar: File menu
        top_bar = QHBoxLayout()
        file_btn = QPushButton("File")
        file_btn.setFixedWidth(120)
        file_menu = QMenu(self)
        save_action = QAction("Save settings", self)
        save_action.triggered.connect(self._save_last_session)
        load_action = QAction("Load settings", self)
        load_action.triggered.connect(self._load_config_from_file)
        file_menu.addAction(save_action)
        file_menu.addAction(load_action)
        file_btn.setMenu(file_menu)
        top_bar.addWidget(file_btn)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Main content: 2 columns
        content = QHBoxLayout()
        content.setSpacing(12)

        # Left column: folder, probe, sorter, protocol
        left_widget = QWidget()
        left_layout = QGridLayout(left_widget)
        left_layout.setColumnStretch(1, 1)

        r = 0
        left_layout.addWidget(QLabel("Intan files folder path"), r, 0)
        self.folder_edit = QLineEdit()
        self.folder_edit.setMinimumWidth(400)
        left_layout.addWidget(self.folder_edit, r, 1)
        folder_btn = QPushButton("Browse")
        folder_btn.clicked.connect(lambda: self._browse_path("folder", self.folder_edit))
        left_layout.addWidget(folder_btn, r, 2)
        r += 1

        left_layout.addWidget(QLabel("Probe file path (.json)"), r, 0)
        self.probe_edit = QLineEdit()
        self.probe_edit.setText("C:/Spikesorting_utilities/MEA_RdLGN64.json")
        left_layout.addWidget(self.probe_edit, r, 1)
        probe_btn = QPushButton("Browse")
        probe_btn.clicked.connect(lambda: self._browse_path("file", self.probe_edit, "*.json"))
        left_layout.addWidget(probe_btn, r, 2)
        r += 1

        left_layout.addWidget(QLabel("Sorter name"), r, 0)
        self.sorter_edit = QLineEdit()
        self.sorter_edit.setText("tridesclous2")
        left_layout.addWidget(self.sorter_edit, r, 1)
        r += 1

        left_layout.addWidget(QLabel("Protocol"), r, 0)
        protocol_btn = QPushButton("Edit protocol params")
        protocol_btn.clicked.connect(self._open_protocol_params_editor)
        left_layout.addWidget(protocol_btn, r, 1)
        r += 1

        content.addWidget(left_widget)

        # Right column: Trigger section
        trigger_group = QGroupBox("Trigger")
        trigger_layout = QGridLayout(trigger_group)
        trigger_layout.setColumnStretch(1, 1)

        t = 0
        self.use_trigger_cb = QCheckBox("Use trigger detection")
        self.use_trigger_cb.setChecked(True)
        self.use_trigger_cb.toggled.connect(self._toggle_trigger_fields_state)
        trigger_layout.addWidget(self.use_trigger_cb, t, 0, 1, 2)
        t += 1

        trigger_layout.addWidget(QLabel("Trigger type:"), t, 0)
        trigger_type_widget = QWidget()
        trigger_type_layout = QHBoxLayout(trigger_type_widget)
        trigger_type_layout.setContentsMargins(0, 0, 0, 0)
        self.trigger_type_group = QButtonGroup()
        self.rb_led = QRadioButton("LED")
        self.rb_electric = QRadioButton("Electric")
        self.rb_electric.setChecked(True)
        self.trigger_type_group.addButton(self.rb_led)
        self.trigger_type_group.addButton(self.rb_electric)
        self.rb_led.toggled.connect(self._on_trigger_type_change)
        self.rb_electric.toggled.connect(self._on_trigger_type_change)
        trigger_type_layout.addWidget(self.rb_led)
        trigger_type_layout.addWidget(self.rb_electric)
        trigger_layout.addWidget(trigger_type_widget, t, 1)
        self._trigger_widgets.extend([self.rb_led, self.rb_electric])
        t += 1

        trigger_layout.addWidget(QLabel("Trigger threshold"), t, 0)
        self.trigger_threshold_edit = QLineEdit()
        self.trigger_threshold_edit.setText("37000")
        self.trigger_threshold_edit.setMaximumWidth(150)
        trigger_layout.addWidget(self.trigger_threshold_edit, t, 1)
        self._trigger_widgets.append(self.trigger_threshold_edit)
        t += 1

        trigger_layout.addWidget(QLabel("Trigger polarity"), t, 0)
        self.polarity_combo = QComboBox()
        self.polarity_combo.addItems(["Rising Edge", "Falling Edge"])
        self.polarity_combo.setCurrentText("Falling Edge")
        self.polarity_combo.setMaximumWidth(150)
        trigger_layout.addWidget(self.polarity_combo, t, 1)
        self._trigger_widgets.append(self.polarity_combo)
        t += 1

        trigger_layout.addWidget(QLabel("Minimum elapsed time between triggers (s)"), t, 0)
        self.trigger_interval_edit = QLineEdit()
        self.trigger_interval_edit.setText("5.1")
        self.trigger_interval_edit.setMaximumWidth(150)
        trigger_layout.addWidget(self.trigger_interval_edit, t, 1)
        self._trigger_widgets.append(self.trigger_interval_edit)
        t += 1

        trigger_layout.addWidget(QLabel("Trigger channel index"), t, 0)
        self.trigger_channel_edit = QLineEdit()
        self.trigger_channel_edit.setText("0")
        self.trigger_channel_edit.setMaximumWidth(150)
        trigger_layout.addWidget(self.trigger_channel_edit, t, 1)
        self._trigger_widgets.append(self.trigger_channel_edit)

        content.addWidget(trigger_group)
        main_layout.addLayout(content)

        # Controls
        controls = QHBoxLayout()
        self._run_button = QPushButton("Run Pipeline")
        self._run_button.setFixedWidth(150)
        self._run_button.clicked.connect(self._run_pipeline_async)
        controls.addWidget(self._run_button)
        self._stop_button = QPushButton("Stop Pipeline")
        self._stop_button.setFixedWidth(150)
        self._stop_button.setEnabled(False)
        self._stop_button.clicked.connect(self._request_stop)
        controls.addWidget(self._stop_button)
        clear_btn = QPushButton("Clear Logs")
        clear_btn.setFixedWidth(150)
        clear_btn.clicked.connect(self._clear_logs)
        controls.addWidget(clear_btn)
        controls.addStretch()
        main_layout.addLayout(controls)

        # Logs
        main_layout.addWidget(QLabel("Logs"))
        self._progressbar = QProgressBar()
        self._progressbar.setRange(0, 0)  # indeterminate
        self._progressbar.setVisible(False)
        main_layout.addWidget(self._progressbar)

        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMinimumHeight(200)
        main_layout.addWidget(self.logs, 1)

        self._toggle_trigger_fields_state()

    def _toggle_trigger_fields_state(self):
        enabled = self.use_trigger_cb.isChecked()
        for w in self._trigger_widgets:
            w.setEnabled(enabled)

    def _on_trigger_type_change(self):
        preset = {"led": ("37000", "Falling Edge", "5.1"), "electric": ("39000", "Rising Edge", "5.1")}
        t = "led" if self.rb_led.isChecked() else "electric"
        if t in preset:
            thresh, polarity, interval = preset[t]
            self.trigger_threshold_edit.setText(thresh)
            self.polarity_combo.setCurrentText(polarity)
            self.trigger_interval_edit.setText(interval)
        self._save_last_session()

    def _polarity_to_edge(self, polarity_str):
        if polarity_str.strip() == "Rising Edge":
            return 1
        if polarity_str.strip() == "Falling Edge":
            return -1
        raise ValueError("trigger polarity must be 'Rising Edge' or 'Falling Edge'.")

    def _edge_to_polarity(self, edge):
        return "Rising Edge" if edge == 1 else "Falling Edge"

    def _collect_form_state(self):
        state = {
            "folder_path": self.folder_edit.text(),
            "use_trigger": self.use_trigger_cb.isChecked(),
            "trigger_type": "led" if self.rb_led.isChecked() else "electric",
            "trigger_threshold": self.trigger_threshold_edit.text(),
            "trigger_polarity": self.polarity_combo.currentText(),
            "trigger_min_interval": self.trigger_interval_edit.text(),
            "trigger_channel_index": self.trigger_channel_edit.text(),
            "sorter_name": self.sorter_edit.text(),
            "my_probe_path": self.probe_edit.text(),
        }
        if self._protocol_params is not None:
            state["protocol_params"] = self._protocol_params
        return state

    def _apply_form_state(self, state):
        if not isinstance(state, dict):
            return
        self.folder_edit.setText(state.get("folder_path", self.folder_edit.text()))
        self.use_trigger_cb.setChecked(bool(state.get("use_trigger", True)))
        t = state.get("trigger_type", "electric")
        self.rb_led.setChecked(t == "led")
        self.rb_electric.setChecked(t == "electric")
        self.trigger_threshold_edit.setText(state.get("trigger_threshold", self.trigger_threshold_edit.text()))
        polarity = state.get("trigger_polarity") or state.get("trigger_edge")
        if polarity in ("-1", "1"):
            polarity = self._edge_to_polarity(int(polarity))
        if polarity in ("Rising Edge", "Falling Edge"):
            self.polarity_combo.setCurrentText(polarity)
        self.trigger_interval_edit.setText(state.get("trigger_min_interval", self.trigger_interval_edit.text()))
        self.trigger_channel_edit.setText(state.get("trigger_channel_index", self.trigger_channel_edit.text()))
        self.sorter_edit.setText(state.get("sorter_name", self.sorter_edit.text()))
        self.probe_edit.setText(state.get("my_probe_path", self.probe_edit.text()))
        self._protocol_params = state.get("protocol_params")

    def _load_last_session(self):
        if not os.path.isfile(self._session_file):
            return
        try:
            with open(self._session_file, "r", encoding="utf-8") as f:
                self._apply_form_state(json.load(f))
        except Exception:
            pass

    def _save_last_session(self):
        try:
            with open(self._session_file, "w", encoding="utf-8") as f:
                json.dump(self._collect_form_state(), f, indent=2, ensure_ascii=True)
        except Exception:
            pass

    def closeEvent(self, event):
        self._save_last_session()
        event.accept()

    def _browse_path(self, mode, target_edit, filter_ext=None):
        if mode == "folder":
            selected = QFileDialog.getExistingDirectory(self, "Select folder")
        else:
            filter_str = "JSON files (*.json);;All files (*.*)" if filter_ext else "All files (*.*)"
            selected, _ = QFileDialog.getOpenFileName(self, "Select file", "", filter_str)
        if selected:
            target_edit.setText(selected)
            self._save_last_session()

    def _get_current_protocol_params(self):
        if self._protocol_params is not None:
            return self._protocol_params
        return Protocol(400, 5000, "").params

    def _open_protocol_params_editor(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit protocol params")
        dialog.resize(700, 500)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Edit the protocol params (JSON). Keys: preprocessing, postprocessing."))
        text_edit = QTextEdit()
        text_edit.setFontFamily("Consolas")
        text_edit.setPlainText(json.dumps(self._get_current_protocol_params(), indent=2, ensure_ascii=False))
        layout.addWidget(text_edit)

        btn_layout = QHBoxLayout()

        def apply_and_close():
            try:
                parsed = json.loads(text_edit.toPlainText())
                if not isinstance(parsed, dict):
                    raise ValueError("Root must be a JSON object.")
                if "preprocessing" not in parsed or "postprocessing" not in parsed:
                    raise ValueError("Must contain 'preprocessing' and 'postprocessing' keys.")
                self._protocol_params = parsed
                self._save_last_session()
                dialog.accept()
                QMessageBox.information(self, "Protocol params", "Protocol params saved.")
            except json.JSONDecodeError as e:
                QMessageBox.critical(self, "Invalid JSON", str(e))
            except ValueError as e:
                QMessageBox.critical(self, "Invalid params", str(e))

        def reset_defaults():
            text_edit.setPlainText(json.dumps(Protocol(400, 5000, "").params, indent=2, ensure_ascii=False))

        def load_from_file():
            path, _ = QFileDialog.getOpenFileName(self, "Select protocol file", "", "JSON files (*.json);;All files (*.*)")
            if not path:
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    parsed = json.load(f)
                if not isinstance(parsed, dict):
                    raise ValueError("File must contain a JSON object.")
                if "preprocessing" not in parsed or "postprocessing" not in parsed:
                    raise ValueError("Protocol must contain 'preprocessing' and 'postprocessing' keys.")
                text_edit.setPlainText(json.dumps(parsed, indent=2, ensure_ascii=False))
                QMessageBox.information(self, "Protocol loaded", f"Protocol loaded from:\n{path}")
            except json.JSONDecodeError as e:
                QMessageBox.critical(self, "Invalid JSON", str(e))
            except ValueError as e:
                QMessageBox.critical(self, "Invalid protocol", str(e))

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(apply_and_close)
        load_btn = QPushButton("Load protocol")
        load_btn.clicked.connect(load_from_file)
        reset_btn = QPushButton("Reset to defaults")
        reset_btn.clicked.connect(reset_defaults)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)

        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(load_btn)
        btn_layout.addWidget(reset_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _clear_logs(self):
        self.logs.clear()

    def _set_run_button_state(self, enabled):
        self._run_button.setEnabled(enabled)
        self._stop_button.setEnabled(not enabled)

    def _request_stop(self):
        if self._pipeline_process and self._pipeline_process.is_alive():
            self._log("Stopping pipeline immediately...")
            self._pipeline_process.terminate()
            self._pipeline_process.join(timeout=2.0)
            if self._pipeline_process.is_alive():
                self._pipeline_process.kill()
                self._pipeline_process.join(timeout=1.0)
            self._pipeline_process = None
            self._set_run_button_state(True)
            self._set_sorter_progress(False)
            self._log("Pipeline stopped.")

    def _set_sorter_progress(self, running):
        self.progress_signal.emit(running)

    def _progress_impl(self, visible):
        self._progressbar.setVisible(visible)

    def _open_output_folder(self, folder_path):
        if os.path.isdir(folder_path):
            os.startfile(folder_path)
            time.sleep(0.25)
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW("CabinetWClass", None)
            if hwnd:
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
        else:
            raise ValueError(f"Output folder not found: {folder_path}")

    def _log(self, message):
        self.log_signal.emit(message)

    def _log_impl(self, message):
        self.logs.append(message)
        scrollbar = self.logs.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _show_info(self, title, message):
        QMessageBox.information(self, title, message)

    def _show_error(self, title, message):
        QMessageBox.critical(self, title, message)

    def _load_config_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select settings file", "", "JSON files (*.json);;All files (*.*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            state.pop("_description", None)
            self._apply_form_state(state)
            self._save_last_session()
            self._toggle_trigger_fields_state()
            QMessageBox.information(self, "Config loaded", f"Parameters loaded from:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", str(exc))

    def _save_protocol_to_output_folder(self, folder_path):
        protocol_path = os.path.join(folder_path, "protocol.json")
        try:
            with open(protocol_path, "w", encoding="utf-8") as f:
                json.dump(self._get_current_protocol_params(), f, indent=2, ensure_ascii=False)
            self._log(f"Protocol saved to {protocol_path}")
        except Exception as exc:
            self._log(f"Warning: could not save protocol.json: {exc}")

    def _on_pipeline_success(self, folder_path):
        self._set_sorter_progress(False)
        self._save_protocol_to_output_folder(folder_path)
        self._log("Pipeline completed successfully.")
        self._log("Opening output folder...")
        self._open_output_folder(folder_path)
        self._show_info("Done", "Pipeline completed successfully.\n\nOutput folder has been opened.")

    def _run_pipeline_async(self):
        self._save_last_session()
        self._set_run_button_state(False)
        params = self._collect_pipeline_params()
        if params is None:
            self._set_run_button_state(True)
            return
        self._log_queue = multiprocessing.Queue()
        self._pipeline_process = multiprocessing.Process(
            target=_run_pipeline_in_process,
            args=(params, self._log_queue),
            daemon=True,
        )
        self._pipeline_process.start()
        self._queue_reader_thread = threading.Thread(target=self._queue_reader_loop, daemon=True)
        self._queue_reader_thread.start()

    def _collect_pipeline_params(self):
        """Collect all params from GUI for the pipeline process. Returns None if validation fails."""
        try:
            folder_path = self.folder_edit.text().strip()
            use_trigger = self.use_trigger_cb.isChecked()
            sorter_name = self.sorter_edit.text().strip()
            my_probe_path = self.probe_edit.text().strip()
            protocol_params = self._get_current_protocol_params()
            bandpass = protocol_params.get("preprocessing", {}).get("bandpass_filter", {})
            min_freq = float(bandpass.get("freq_min", 400))
            max_freq = float(bandpass.get("freq_max", 5000))
            trigger_threshold = None
            trigger_edge = None
            trigger_min_interval = None
            trigger_channel_index = None
            if use_trigger:
                trigger_threshold = float(self.trigger_threshold_edit.text().strip())
                trigger_edge = self._polarity_to_edge(self.polarity_combo.currentText())
                trigger_min_interval = float(self.trigger_interval_edit.text().strip())
                trigger_channel_index = int(self.trigger_channel_edit.text().strip())

            if not folder_path or not os.path.isdir(folder_path):
                raise ValueError("folder_path is missing or does not exist.")
            if not my_probe_path or not os.path.isfile(my_probe_path):
                raise ValueError("my_probe_df path is missing or does not exist.")
            if min_freq <= 0 or max_freq <= 0:
                raise ValueError("protocol min_freq and max_freq must be > 0.")
            if min_freq >= max_freq:
                raise ValueError("protocol min_freq must be < max_freq.")
            if use_trigger:
                if trigger_edge not in (-1, 1):
                    raise ValueError("trigger polarity must be 'Rising Edge' or 'Falling Edge'.")
                if trigger_channel_index < 0:
                    raise ValueError("trigger_channel_index must be >= 0.")

            return {
                "folder_path": folder_path,
                "use_trigger": use_trigger,
                "sorter_name": sorter_name,
                "my_probe_path": my_probe_path,
                "protocol_params": protocol_params,
                "min_freq": min_freq,
                "max_freq": max_freq,
                "trigger_threshold": trigger_threshold,
                "trigger_edge": trigger_edge,
                "trigger_min_interval": trigger_min_interval,
                "trigger_channel_index": trigger_channel_index,
                "trigger_type": "led" if self.rb_led.isChecked() else "electric",
            }
        except Exception as exc:
            self._log(f"Validation error: {exc}")
            return None

    def _queue_reader_loop(self):
        """Read messages from the pipeline process queue and update the GUI."""
        while True:
            try:
                item = self._log_queue.get(timeout=0.2)
            except Empty:
                if self._pipeline_process and not self._pipeline_process.is_alive():
                    break
                continue
            if item is None:
                break
            if isinstance(item, tuple):
                kind = item[0]
                if kind == "log":
                    self.log_signal.emit(item[1])
                elif kind == "progress":
                    self.progress_signal.emit(item[1])
                elif kind == "done":
                    _, status, payload = item
                    self._set_sorter_progress(False)
                    if status == "success":
                        QTimer.singleShot(0, lambda f=payload: self._on_pipeline_success(f))
                    else:
                        self.log_signal.emit(f"ERROR: {payload}")
                        QTimer.singleShot(0, lambda m=payload: self._show_error("Error", m))
                    QTimer.singleShot(0, lambda: self._set_run_button_state(True))
                    break
            else:
                self.log_signal.emit(str(item))
        self._pipeline_process = None

def _run_pipeline_in_process(params, log_queue):
    """Run the pipeline in a subprocess. Sends (log, msg), (progress, bool), (done, status, payload)."""
    def _log(msg):
        log_queue.put(("log", msg))

    def _progress(visible):
        log_queue.put(("progress", visible))

    try:
        folder_path = params["folder_path"]
        use_trigger = params["use_trigger"]
        sorter_name = params["sorter_name"]
        my_probe_path = params["my_probe_path"]
        protocol_params = params["protocol_params"]
        min_freq = params["min_freq"]
        max_freq = params["max_freq"]
        trigger_type = params["trigger_type"]
        my_protocol_path = os.path.join(folder_path, "protocol.json")

        _log("Starting pipeline...")
        _log(f"folder_path: {folder_path}")
        _log(f"sorter_name: {sorter_name}")
        _log(f"use_trigger: {use_trigger}")
        if use_trigger:
            _log(
                f"trigger: type={trigger_type}, "
                f"threshold={params['trigger_threshold']}, "
                f"polarity={'Rising' if params['trigger_edge'] == 1 else 'Falling'} Edge, "
                f"min_interval={params['trigger_min_interval']}"
            )
            _log(f"trigger_channel_index: {params['trigger_channel_index']}")
        _log(f"protocol_path (auto): {my_protocol_path}")
        _log(f"probe_path: {my_probe_path}")
        _log(f"bandpass: {min_freq} -> {max_freq} Hz")

        timestamps_parameters = None
        if use_trigger:
            trigger = Trigger(
                params["trigger_threshold"],
                params["trigger_edge"],
                params["trigger_min_interval"],
            )
            timestamps_parameters = TimestampsParameters(
                trigger=trigger,
                trigger_channel_index=params["trigger_channel_index"],
                trigger_type=trigger_type,
            )
        sorter = Sorter(sorter_name)
        _log("Loading Intan files...")
        rhs_files = IntanFile(folder_path)
        _log(f"Channel IDs: {rhs_files.channel_ids}")
        _log(f"Sampling frequency: {rhs_files.frequency}")
        _log(f"Number of channels: {rhs_files.number_of_channels}")
        _log(f"Number of segments: {rhs_files.number_of_segments}")
        if use_trigger:
            _log("Computing trigger timestamps...")
            rhs_files.generate_trigger_timestamps(timestamps_parameters)
        else:
            _log("Trigger disabled: skipping trigger timestamp extraction.")

        protocol = Protocol(min_freq, max_freq, my_protocol_path, params=protocol_params)
        my_probe_df = Probe(my_probe_path)
        _log("Associating probe...")
        rhs_files.associate_probe(my_probe_df)

        _log("Running sorter + analyzer (this can take time)...")
        _progress(True)
        pipeline = Pipeline(sorter, folder_path, protocol, rhs_files)

        _progress(False)
        _log("Generating PDF report...")
        PDFGenerator(folder_path, pipeline)

        log_queue.put(("done", "success", folder_path))
    except Exception as exc:
        _progress(False)
        _log(f"ERROR: {exc}")
        _log(traceback.format_exc())
        log_queue.put(("done", "error", str(exc)))


def run_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    window = PipelineGUI()
    window.show()
    app.exec()


if __name__ == "__main__":
    run_app()
