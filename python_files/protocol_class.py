# -*- coding: utf-8 -*-
"""
Protocol configuration for the spike-sorting pipeline.

This module provides:
- TypedDict for protocol structure (type hints, IDE support),
- default_protocol_params() as single source of truth for the protocol dict.

The resulting dictionary is consumed by Pipeline and PDFGenerator.
"""

from typing import TypedDict


class ProtocolParams(TypedDict, total=False):
    """Type hints for the protocol params dict structure."""
    preprocessing: dict
    postprocessing: dict
    _file_path: str


def default_protocol_params(min_freq: int = 400, max_freq: int = 5000) -> dict:
    """Build the default protocol dictionary.

    Single source of truth for preprocessing and postprocessing structure.
    """
    return {
        "preprocessing": {
            "bandpass_filter": {"freq_min": min_freq, "freq_max": max_freq},
        },
        "postprocessing": {
            "random_spikes": {"method": "uniform", "max_spikes_per_unit": 500, "seed": None},
            "waveforms": {"ms_before": 1.0, "ms_after": 2.0},
            "templates": {"ms_before": 1.0, "ms_after": 2.0},
            "noise_levels": {},
            "template_metrics": {"include_multi_channel_metrics": False, "peak_sign": "neg"},
            "spike_amplitudes": {"peak_sign": "neg"},
            "unit_locations": {"method": "monopolar_triangulation"},
            "spike_locations": {"method": "center_of_mass"},
            "template_similarity": {"method": "cosine", "max_lag_ms": 0, "support": "union"},
            "correlograms": {"window_ms": 50.0, "bin_ms": 1.0, "method": "auto"},
            "acgs_3d": {"window_ms": 50.0, "bin_ms": 1.0, "num_firing_rate_quantiles": 10, "smoothing_factor": 250},
            "isi_histograms": {"window_ms": 50.0, "bin_ms": 1.0, "method": "auto"},
        },
    }
