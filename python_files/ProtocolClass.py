# -*- coding: utf-8 -*-
"""
Protocol configuration object used by the spike-sorting pipeline.

This module defines a small container class that centralizes:
1) preprocessing parameters (band-pass filter),
2) postprocessing steps and their options.

The resulting dictionary is intended to be consumed by downstream
pipeline code.
"""

class Protocol:
    """Store and expose analysis protocol parameters.

    Parameters
    ----------
    min_freq : float | int
        Lower cutoff frequency (Hz) for the band-pass preprocessing step.
    max_freq : float | int
        Upper cutoff frequency (Hz) for the band-pass preprocessing step.
    file_path : str
        Path to a protocol file or output location associated with this protocol.
        It is kept as metadata for traceability and potential save/load features.
    """

    def __init__(self, min_freq, max_freq, file_path):
        """Build the protocol parameter dictionary used by the pipeline."""
        self._min_freq = min_freq
        self._max_freq = max_freq
        # Keep the protocol path for bookkeeping (e.g., persistence, audit trail).
        self._file_path = file_path

        # Main protocol dictionary passed to processing functions.
        self.params = {
            'preprocessing': {
                # Band-pass filter configuration applied before spike sorting.
                'bandpass_filter': {"freq_min" : min_freq, "freq_max" : max_freq},
            },
            # Postprocessing computes descriptive features and quality indicators
            # from the sorted spikes. Some steps depend on outputs of previous steps.
            #
            # Recommended execution flow:
            # 1) random_spikes -> provides a representative spike subset
            # 2) waveforms      -> extracts waveform snippets per unit
            # 3) templates      -> builds average waveform templates
            # 4) derived metrics (amplitudes, locations, similarity, quality)
            #
            # Dependency note:
            # templates is a key parent for many downstream computations.
            # If templates is skipped, several metrics below may fail or be empty.
            'postprocessing': {
                # Sampling / baseline descriptors
                'random_spikes': {},
                'noise_levels': {},
                'correlograms': {},

                # Waveform representation
                'waveforms': {},
                # Example dependency chain:
                # random_spikes -> templates -> amplitude_scalings,
                # spike_amplitudes, spike_locations, template_similarity,
                # unit_locations, quality_metrics.
                'templates': {},

                # Amplitude-related descriptors
                'amplitude_scalings': {},
                'spike_amplitudes': {},

                # Spatial descriptors
                'unit_locations': {'method': 'center_of_mass'},
                'spike_locations': {},

                # Cross-unit and per-template comparisons
                'template_similarity': {},
                'template_metrics': {},

                # Final unit-level quality summary metrics
                'quality_metrics': {}
            },
        }
        
    def __repr__(self):
        """Return the protocol dictionary for quick inspection/printing."""
        return (self.params)
    
    
    
    