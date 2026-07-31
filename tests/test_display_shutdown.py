import importlib.util
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class NullLogger:
    def __init__(self, *args, **kwargs):
        pass

    def debug(self, _message):
        pass

    def error(self, _message):
        pass

    def info(self, _message):
        pass

    def warning(self, _message):
        pass


def display_import_stubs():
    pandas = types.ModuleType("pandas")
    pandas.DataFrame = object

    pil = types.ModuleType("PIL")
    pil.Image = object
    pil.ImageDraw = object

    init_shared = types.ModuleType("init_shared")
    init_shared.shared_data = object()

    comment = types.ModuleType("comment")
    comment.Commentaireia = object

    logger = types.ModuleType("logger")
    logger.Logger = NullLogger

    return {
        "pandas": pandas,
        "PIL": pil,
        "init_shared": init_shared,
        "comment": comment,
        "logger": logger,
    }


class DisplayShutdownTests(unittest.TestCase):
    MODULE_NAME = "_bjorn_display_shutdown_under_test"

    @classmethod
    def setUpClass(cls):
        cls.module_patch = patch.dict(sys.modules, display_import_stubs())
        cls.module_patch.start()
        module_path = Path(__file__).resolve().parents[1] / "display.py"
        module_spec = importlib.util.spec_from_file_location(
            cls.MODULE_NAME,
            module_path,
        )
        if module_spec is None or module_spec.loader is None:
            raise RuntimeError(f"Cannot load display module from {module_path}")
        cls.display_module = importlib.util.module_from_spec(module_spec)
        sys.modules[cls.MODULE_NAME] = cls.display_module
        module_spec.loader.exec_module(cls.display_module)

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop(cls.MODULE_NAME, None)
        cls.module_patch.stop()

    def make_display(self):
        display = object.__new__(self.display_module.Display)
        display.shared_data = SimpleNamespace(display_should_exit=False)
        display.shutdown_event = threading.Event()
        return display

    def test_request_stop_wakes_a_long_display_wait(self):
        display = self.make_display()
        wait_result = []
        waiter = threading.Thread(
            target=lambda: wait_result.append(display.wait_or_stop(300))
        )
        waiter.start()
        time.sleep(0.01)

        display.request_stop()
        waiter.join(timeout=0.5)

        self.assertFalse(waiter.is_alive())
        self.assertEqual(wait_result, [True])
        self.assertTrue(display.shared_data.display_should_exit)
        self.assertTrue(display.shutdown_event.is_set())

    def test_background_threads_returns_every_owned_worker(self):
        display = self.make_display()
        display.main_image_thread = object()
        display.update_shared_data_thread = object()
        display.update_vuln_count_thread = object()

        self.assertEqual(
            display.background_threads(),
            [
                display.main_image_thread,
                display.update_shared_data_thread,
                display.update_vuln_count_thread,
            ],
        )

    def test_close_hardware_delegates_to_epd_helper(self):
        display = self.make_display()
        display.epd_helper = SimpleNamespace(shutdown=Mock())

        display.close_hardware()

        display.epd_helper.shutdown.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
