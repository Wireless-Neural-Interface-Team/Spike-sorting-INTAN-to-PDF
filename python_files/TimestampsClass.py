# -*- coding: utf-8 -*-
"""
Created on Fri Feb  6 11:30:46 2026

@author: WNIlabs
"""

class TimestampsParameters:
    """
    Configuration object for trigger timestamp extraction.

    This class groups all parameters needed by IntanClass methods that detect
    trigger events from a signal:
      - trigger: Trigger object (threshold, edge, min_interval),
      - trigger_channel_index: index of the channel used for detection.
    """

    def __init__(
        self,
        trigger,
        trigger_channel_index=0
    ):
        # Trigger model containing detection settings.
        self.trigger = trigger
        # Channel index used to detect threshold crossings.
        self.trigger_channel_index = trigger_channel_index
        

    def __repr__(self):
        # String representation useful for debugging/logging.
        return (
            f"TimestampsParameters("
            f"threshold={self.trigger.threshold}, "
            f"trigger_channel_index={self.trigger_channel_index}, "
            f"min_interval={self.trigger.min_interval}, "
            f"edge={self.trigger.edge})"
        )
           