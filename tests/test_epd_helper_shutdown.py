import sys
import types
import unittest
from unittest.mock import Mock, patch

from epd_helper import EPDHelper


class EPDHelperShutdownTests(unittest.TestCase):
    def make_helper(self, sleep_side_effect=None):
        devices = {
            name: SimpleClosable()
            for name in (
                "GPIO_RST_PIN",
                "GPIO_DC_PIN",
                "GPIO_PWR_PIN",
                "GPIO_BUSY_PIN",
            )
        }
        implementation = types.SimpleNamespace(**devices)
        epdconfig = types.SimpleNamespace(implementation=implementation)
        helper = object.__new__(EPDHelper)
        helper.epd_type = "epd2in13_V4"
        helper.epd_module = types.SimpleNamespace(epdconfig=epdconfig)
        helper._shutdown_complete = False
        helper.epd = types.SimpleNamespace(
            sleep=Mock(side_effect=sleep_side_effect)
        )
        pin_factory = SimpleClosable()
        gpiozero = types.ModuleType("gpiozero")
        gpiozero.Device = types.SimpleNamespace(pin_factory=pin_factory)
        notify_thread = FakeNotifyThread()
        lgpio = types.ModuleType("lgpio")
        lgpio._notify_thread = notify_thread
        lgpio.notify_close = Mock()
        return (
            helper,
            devices,
            pin_factory,
            gpiozero,
            lgpio,
            notify_thread,
        )

    def test_shutdown_releases_panel_devices_and_pin_factory_once(self):
        (
            helper,
            devices,
            pin_factory,
            gpiozero,
            lgpio,
            notify_thread,
        ) = self.make_helper()

        with patch.dict(
            sys.modules,
            {"gpiozero": gpiozero, "lgpio": lgpio},
        ):
            helper.shutdown()
            helper.shutdown()

        helper.epd.sleep.assert_called_once_with()
        for device in devices.values():
            self.assertEqual(device.close_count, 1)
        self.assertEqual(pin_factory.close_count, 1)
        self.assertEqual(notify_thread.stop_count, 1)
        self.assertEqual(notify_thread.join_timeouts, [1])
        lgpio.notify_close.assert_called_once_with(17)

    def test_gpio_cleanup_still_runs_when_panel_sleep_fails(self):
        (
            helper,
            devices,
            pin_factory,
            gpiozero,
            lgpio,
            notify_thread,
        ) = self.make_helper(RuntimeError("sleep failed"))

        with patch.dict(
            sys.modules,
            {"gpiozero": gpiozero, "lgpio": lgpio},
        ):
            helper.shutdown()

        for device in devices.values():
            self.assertEqual(device.close_count, 1)
        self.assertEqual(pin_factory.close_count, 1)
        self.assertEqual(notify_thread.stop_count, 1)
        lgpio.notify_close.assert_called_once_with(17)


class SimpleClosable:
    def __init__(self):
        self.close_count = 0

    def close(self):
        self.close_count += 1


class FakeNotifyThread:
    def __init__(self):
        self._notify = 17
        self.stop_count = 0
        self.join_timeouts = []

    def stop(self):
        self.stop_count += 1

    def join(self, timeout=None):
        self.join_timeouts.append(timeout)

    def is_alive(self):
        return False


if __name__ == "__main__":
    unittest.main()
