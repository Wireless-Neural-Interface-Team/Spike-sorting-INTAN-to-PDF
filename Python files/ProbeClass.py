# -*- coding: utf-8 -*-
"""
Created on Mon Feb  9 11:03:14 2026

@author: WNIlabs
"""
import probeinterface as ProbeI



class Probe:
    """
    Lightweight wrapper for probe geometry loaded with probeinterface.

    This class stores:
      - the path to the probe description file,
      - a dataframe representation of probe contacts/metadata.

    The dataframe is later filtered/reordered in IntanClass.associate_probe(...)
    to match the channels present in the loaded recording.
    """

    def __init__(self, probe_file_path):
        # Path to probe file (typically .json).
        self._file_path = probe_file_path
        # Full probe table used as a starting point before channel alignment.
        self._dataframe = ProbeI.read_probeinterface(self._file_path).to_dataframe(complete = True)
        
       
        

    