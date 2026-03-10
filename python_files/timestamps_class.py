# -*- coding: utf-8 -*-
"""
Created on Fri Feb  6 11:30:46 2026

@author: WNIlabs
"""

class TimestampsParameters:
    """
    Configuration object for trigger timestamp extraction.

    This class groups all parameters needed by IntanFile methods that detect
    trigger events from a signal:
      - trigger: Trigger object (threshold, edge, min_interval),
      - trigger_channel_index: index of the channel used for detection,
      - trigger_type: "led" or "electric" (metadata for reporting).
    """

    def __init__(
        self,
        trigger,
        trigger_channel_index=0,
        trigger_type="electric",
    ):
        # Trigger model containing detection settings.
        self.trigger = trigger
        # Channel index used to detect threshold crossings.
        self.trigger_channel_index = trigger_channel_index
        # Type of trigger: "led" or "electric".
        self.trigger_type = trigger_type
        

    def __repr__(self):
        # String representation useful for debugging/logging.
        return (
            f"TimestampsParameters("
            f"trigger_type={self.trigger_type}, "
            f"threshold={self.trigger.threshold}, "
            f"trigger_channel_index={self.trigger_channel_index}, "
            f"min_interval={self.trigger.min_interval}, "
            f"edge={self.trigger.edge})"
        )
           