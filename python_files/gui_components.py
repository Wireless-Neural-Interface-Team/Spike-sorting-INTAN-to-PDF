#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GUI helper components used by gui_run_pipeline.py.
"""

from PySide6.QtCore import QObject, Signal, QTimer

try:
    from intan_class import load_channel_ids_only
except ImportError:
    # Support package-style imports too.
    from .intan_class import load_channel_ids_only


class ChannelsLoaderWorker(QObject):
    """Worker that loads Intan channel IDs in a background QThread."""

    finished = Signal(str, object)  # (folder_path, channel_ids or None)

    def __init__(self, folder_path):
        super().__init__()
        self._folder_path = folder_path

    def run(self):
        try:
            channel_ids = load_channel_ids_only(self._folder_path)
            self.finished.emit(self._folder_path, channel_ids)
        except Exception:
            self.finished.emit(self._folder_path, None)


try:
    from mea_editor.electrode_array_editor_qt import ElectrodeArrayEditorQt
    from mea_editor.electrode_array_editor_io import save_electrodes_to_file

    MEA_EDITOR_AVAILABLE = True

    class EmbeddedMEAEditor(ElectrodeArrayEditorQt):
        """Adapter around mea_editor window with callbacks used by GUI."""

        def __init__(self, initial_path="", on_file_loaded=None, on_close_callback=None):
            super().__init__()
            self._initial_path = initial_path or ""
            self._on_file_loaded_cb = on_file_loaded
            self._on_close_cb = on_close_callback
            self._initial_view_adjust_pending = True

            if self._initial_path:
                try:
                    self._load_array_from_file(self._initial_path)
                    self.current_file_path = self._initial_path
                except Exception:
                    pass

        def _load_array_from_file(self, path):
            super()._load_array_from_file(path)
            self._initial_path = path
            self.current_file_path = path
            # After MEA editor auto-fit, slightly zoom out to avoid a "too zoomed" first view.
            self._initial_view_adjust_pending = True
            QTimer.singleShot(0, self._apply_initial_view_adjustment)
            if callable(self._on_file_loaded_cb):
                self._on_file_loaded_cb(path)

        def showEvent(self, event):
            super().showEvent(event)
            QTimer.singleShot(0, self._apply_initial_view_adjustment)

        def _apply_initial_view_adjustment(self):
            if not self._initial_view_adjust_pending:
                return
            try:
                if hasattr(self, "view") and self.view is not None:
                    self.view.scale(0.85, 0.85)
            except Exception:
                pass
            self._initial_view_adjust_pending = False

        def closeEvent(self, event):
            # Close silently: no save/discard popup from MEA editor.
            try:
                self.is_dirty = False
            except Exception:
                pass
            if callable(self._on_close_cb):
                try:
                    current = getattr(self, "current_file_path", "") or self._initial_path
                    self._on_close_cb(current)
                except Exception:
                    pass
            event.accept()

except Exception:
    MEA_EDITOR_AVAILABLE = False
    EmbeddedMEAEditor = None

    def save_electrodes_to_file(path, electrodes, si_units):
        raise RuntimeError("MEA editor is not available in this environment.")

