import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class NullLogger:
    def __init__(self, *args, **kwargs):
        pass

    def info(self, _message):
        pass

    def error(self, _message):
        pass

    def warning(self, _message):
        pass


class FakeThread:
    def __init__(
        self,
        alive_checks=1,
        name="FakeThread",
        join_error=None,
    ):
        self.alive_checks = alive_checks
        self.name = name
        self.join_timeouts = []
        self.join_error = join_error

    def is_alive(self):
        return len(self.join_timeouts) < self.alive_checks

    def join(self, timeout=None):
        self.join_timeouts.append(timeout)
        if self.join_error is not None:
            raise self.join_error


class FakeDisplay:
    def __init__(self):
        self.stop_requested = False
        self.hardware_closed = False
        self.workers = [
            FakeThread(name="DisplayImage"),
            FakeThread(name="DisplaySharedData"),
            FakeThread(name="DisplayVulnerabilityCount"),
        ]

    def request_stop(self):
        self.stop_requested = True

    def background_threads(self):
        return self.workers

    def close_hardware(self):
        self.hardware_closed = True


class BjornLifecycleTests(unittest.TestCase):
    MODULE_NAME = "_bjorn_lifecycle_under_test"

    @classmethod
    def setUpClass(cls):
        cls.shared_data = SimpleNamespace(
            should_exit=False,
            orchestrator_should_exit=False,
            display_should_exit=False,
            webapp_should_exit=False,
        )

        init_shared = types.ModuleType("init_shared")
        init_shared.shared_data = cls.shared_data
        display = types.ModuleType("display")
        display.Display = object
        comment = types.ModuleType("comment")
        comment.Commentaireia = object
        webapp = types.ModuleType("webapp")
        webapp.web_thread = FakeThread(alive_checks=0)
        orchestrator = types.ModuleType("orchestrator")
        orchestrator.Orchestrator = object
        logger = types.ModuleType("logger")
        logger.Logger = NullLogger

        cls.module_patch = patch.dict(
            sys.modules,
            {
                "init_shared": init_shared,
                "display": display,
                "comment": comment,
                "webapp": webapp,
                "orchestrator": orchestrator,
                "logger": logger,
            },
        )
        cls.module_patch.start()

        module_path = Path(__file__).resolve().parents[1] / "Bjorn.py"
        module_spec = importlib.util.spec_from_file_location(
            cls.MODULE_NAME,
            module_path,
        )
        if module_spec is None or module_spec.loader is None:
            raise RuntimeError(f"Cannot load Bjorn module from {module_path}")
        cls.bjorn_module = importlib.util.module_from_spec(module_spec)
        sys.modules[cls.MODULE_NAME] = cls.bjorn_module
        module_spec.loader.exec_module(cls.bjorn_module)

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop(cls.MODULE_NAME, None)
        cls.module_patch.stop()

    def setUp(self):
        self.shared_data.should_exit = False
        self.shared_data.orchestrator_should_exit = False
        self.shared_data.display_should_exit = False
        self.shared_data.webapp_should_exit = False

    def test_primary_thread_is_joined_until_it_stops(self):
        primary_thread = FakeThread(alive_checks=3)

        self.bjorn_module.wait_for_primary_thread(primary_thread)

        self.assertEqual(primary_thread.join_timeouts, [1, 1, 1])

    def test_exit_handler_stops_and_joins_every_owned_thread(self):
        display = FakeDisplay()
        display_thread = FakeThread(name="Display")
        primary_thread = FakeThread(name="Primary")
        orchestrator_thread = FakeThread(name="Orchestrator")
        web_thread = FakeThread(name="Web")
        bjorn = SimpleNamespace(orchestrator_thread=orchestrator_thread)

        with self.assertRaises(SystemExit) as exit_context:
            self.bjorn_module.handle_exit(
                15,
                None,
                display,
                display_thread,
                bjorn,
                primary_thread,
                web_thread,
            )

        self.assertEqual(exit_context.exception.code, 0)
        self.assertTrue(display.stop_requested)
        self.assertTrue(display.hardware_closed)
        self.assertTrue(self.shared_data.should_exit)
        self.assertTrue(self.shared_data.orchestrator_should_exit)
        self.assertTrue(self.shared_data.display_should_exit)
        self.assertTrue(self.shared_data.webapp_should_exit)
        joined_threads = [
            display_thread,
            *display.workers,
            primary_thread,
            orchestrator_thread,
            web_thread,
        ]
        for thread in joined_threads:
            self.assertEqual(len(thread.join_timeouts), 1)
            self.assertGreater(thread.join_timeouts[0], 0)
            self.assertLessEqual(thread.join_timeouts[0], 0.25)

    def test_shutdown_wait_reports_threads_that_miss_deadline(self):
        stuck_thread = FakeThread(
            alive_checks=1,
            name="StuckWorker",
        )

        alive_names = self.bjorn_module.wait_for_shutdown_threads(
            [stuck_thread],
            timeout=0,
        )

        self.assertEqual(alive_names, ["StuckWorker"])

    def test_shutdown_wait_reports_a_thread_with_custom_join_failure(self):
        gpio_thread = FakeThread(
            name="GPIOHold",
            join_error=RuntimeError(
                "Thread failed to die within 0.25 seconds"
            ),
        )

        alive_names = self.bjorn_module.wait_for_shutdown_threads(
            [gpio_thread],
            timeout=1,
        )

        self.assertEqual(alive_names, ["GPIOHold"])

    def test_exit_handler_waits_for_residual_python_threads(self):
        display = FakeDisplay()
        residual_thread = FakeThread(name="LibraryRefresh")
        current_thread = object()
        bjorn = SimpleNamespace(orchestrator_thread=None)

        with (
            patch.object(
                self.bjorn_module.threading,
                "current_thread",
                return_value=current_thread,
            ),
            patch.object(
                self.bjorn_module.threading,
                "enumerate",
                return_value=[current_thread, residual_thread],
            ),
            self.assertRaises(SystemExit) as exit_context,
        ):
            self.bjorn_module.handle_exit(
                15,
                None,
                display,
                FakeThread(name="Display"),
                bjorn,
                FakeThread(name="Primary"),
                FakeThread(name="Web"),
            )

        self.assertEqual(exit_context.exception.code, 0)
        self.assertEqual(len(residual_thread.join_timeouts), 1)
        self.assertGreater(residual_thread.join_timeouts[0], 0)

    def test_exit_handler_rejects_a_stuck_residual_thread(self):
        display = FakeDisplay()
        residual_thread = FakeThread(
            alive_checks=2,
            name="StuckLibraryThread",
        )
        current_thread = object()
        bjorn = SimpleNamespace(orchestrator_thread=None)

        with (
            patch.object(
                self.bjorn_module.threading,
                "current_thread",
                return_value=current_thread,
            ),
            patch.object(
                self.bjorn_module.threading,
                "enumerate",
                return_value=[current_thread, residual_thread],
            ),
            patch.object(
                self.bjorn_module,
                "RESIDUAL_THREAD_GRACE_SECONDS",
                0,
            ),
            self.assertRaises(SystemExit) as exit_context,
        ):
            self.bjorn_module.handle_exit(
                15,
                None,
                display,
                FakeThread(name="Display"),
                bjorn,
                FakeThread(name="Primary"),
                FakeThread(name="Web"),
            )

        self.assertEqual(exit_context.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
