#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Subprocess pipeline runner used by gui_run_pipeline.py.
"""

# Fix: SpikeInterface calls version("circus") but PyPI package is "spyking-circus"
try:
    from importlib.metadata import version
    from spikeinterface.sorters.external import spyking_circus

    def _patched_get_sorter_version():
        try:
            return version("spyking-circus")
        except Exception:
            return "unknown"

    spyking_circus.SpykingcircusSorter.get_sorter_version = staticmethod(_patched_get_sorter_version)
except Exception:
    pass

import os
import traceback

from trigger_class import Trigger
from timestamps_class import TimestampsParameters
from sorter_class import Sorter
from intan_class import IntanFile
from probe_class import Probe
from pipeline_class import Pipeline
from pdf_generator_class import PDFGenerator


def is_file_in_use_error(exc):
    """Best-effort detection for 'file already open/locked' errors."""
    text = str(exc).lower()
    return (
        isinstance(exc, PermissionError)
        or "winerror 32" in text
        or "being used" in text
        or "another process" in text
        or "permission denied" in text
        or "accès refusé" in text
    )


def run_pipeline_in_process(params, log_queue):
    """Run full Intan -> sorter -> PDF pipeline in child process."""

    def _log(msg):
        log_queue.put(("log", str(msg)))

    def _progress(running):
        log_queue.put(("progress", bool(running)))

    try:
        folder_path = params["folder_path"]
        output_folder = params["output_folder"]
        sorter_name = params["sorter_name"]
        my_probe_path = params["my_probe_path"]
        protocol_params = params["protocol_params"]
        use_trigger = params.get("use_trigger", False)
        preprocessing = protocol_params.get("preprocessing", {}) if isinstance(protocol_params, dict) else {}

        _log(f"[1/5] Intan folder: {folder_path}")
        _log(f"[2/5] Output folder: {output_folder}")
        _log(f"[3/5] Sorter: {sorter_name}")
        _log(f"[4/5] Preprocessing steps: {', '.join(preprocessing.keys()) or '(none)'}")

        _log("Loading Intan files...")
        rhs_files = IntanFile(folder_path)
        _log(f"  → {rhs_files.number_of_channels} channels detected")

        if use_trigger:
            trigger = Trigger(
                threshold=params["trigger_threshold"],
                edge=params["trigger_edge"],
                min_interval=params["trigger_min_interval"],
            )
            ts_params = TimestampsParameters(
                trigger=trigger,
                trigger_channel_index=params["trigger_channel_index"],
                trigger_type=params.get("trigger_type", "electric"),
            )
            _log("Generating trigger timestamps...")
            rhs_files.generate_trigger_timestamps(ts_params)
            _log(f"  → {len(rhs_files.trigger_timestamps)} triggers detected")

        _log("Associating probe...")
        my_probe_df = Probe(my_probe_path)
        rhs_files.associate_probe(my_probe_df)
        _log("  → Probe associated")

        _log("[5/5] Running sorter + analyzer (may take several minutes)...")
        _progress(True)
        sorter = Sorter(sorter_name)
        pipeline = Pipeline(sorter, output_folder, protocol_params, rhs_files)
        _log("  → Sorting completed")

        _log("Generating PDF report...")
        PDFGenerator(output_folder, pipeline)
        pdf_path = os.path.join(output_folder, f"Summary_figures_sorting_{sorter_name}.pdf")
        _log(f"  → PDF generated: {pdf_path}")
        _log("")
        _log("=== Pipeline completed successfully ===")

        _progress(False)
        log_queue.put(("done", "success", output_folder))
    except Exception as exc:
        _progress(False)
        if is_file_in_use_error(exc):
            log_queue.put(("done", "error", "file_in_use"))
        else:
            log_queue.put(("log", "ERROR: Spike sorting error trace:"))
            log_queue.put(("log", traceback.format_exc()))
            log_queue.put(("done", "error", str(exc)))

