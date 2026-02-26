# -*- coding: utf-8 -*-
"""
Trigger configuration object used for timestamp detection.

Parameter order (important):
1) threshold: signal threshold used for edge detection,
2) edge: slope direction that triggers detection (-1 or 1),
3) min_interval: minimum time (seconds) between two valid detected edges.
"""

class Trigger:
    def __init__(self, threshold, edge, min_interval):
        # 1) Threshold value used to split signal above/below threshold.
        self.threshold = threshold
        # 2) Edge polarity:
        #    +1 -> rising edge crossing, -1 -> falling edge crossing.
        self.edge = edge
        # 3) Minimum interval in seconds between two accepted edges.
        self.min_interval = min_interval

    def __repr__(self):
        return (f"Trigger(threshold={self.threshold}, "
                f"edge={self.edge}, "
                f"min_interval={self.min_interval})")