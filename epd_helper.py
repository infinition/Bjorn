# epd_helper.py

import importlib
import logging

logger = logging.getLogger(__name__)

class EPDHelper:
    def __init__(self, epd_type):
        self.epd_type = epd_type
        self.epd_module = None
        self._shutdown_complete = False
        self.epd = self._load_epd_module()

    def _load_epd_module(self):
        try:
            epd_module_name = f'resources.waveshare_epd.{self.epd_type}'
            self.epd_module = importlib.import_module(epd_module_name)
            return self.epd_module.EPD()
        except ImportError as e:
            logger.error(f"EPD module {self.epd_type} not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading EPD module {self.epd_type}: {e}")
            raise

    def init_full_update(self):
        try:
            if hasattr(self.epd, 'FULL_UPDATE'):
                self.epd.init(self.epd.FULL_UPDATE)
            elif hasattr(self.epd, 'lut_full_update'):
                self.epd.init(self.epd.lut_full_update)
            else:
                self.epd.init()
            logger.info("EPD full update initialization complete.")
        except Exception as e:
            logger.error(f"Error initializing EPD for full update: {e}")
            raise

    def init_partial_update(self):
        try:
            if hasattr(self.epd, 'PART_UPDATE'):
                self.epd.init(self.epd.PART_UPDATE)
            elif hasattr(self.epd, 'lut_partial_update'):
                self.epd.init(self.epd.lut_partial_update)
            else:
                self.epd.init()
            logger.info("EPD partial update initialization complete.")
        except Exception as e:
            logger.error(f"Error initializing EPD for partial update: {e}")
            raise

    def display_partial(self, image):
        try:
            if hasattr(self.epd, 'displayPartial'):
                self.epd.displayPartial(self.epd.getbuffer(image))
            else:
                self.epd.display(self.epd.getbuffer(image))
            logger.info("Partial display update complete.")
        except Exception as e:
            logger.error(f"Error during partial display update: {e}")
            raise

    def clear(self):
        try:
            self.epd.Clear()
            logger.info("EPD cleared.")
        except Exception as e:
            logger.error(f"Error clearing EPD: {e}")
            raise

    def shutdown(self):
        """Power down the panel and release gpiozero/lgpio resources."""
        if self._shutdown_complete:
            return
        self._shutdown_complete = True

        try:
            if hasattr(self.epd, "sleep"):
                self.epd.sleep()
        except Exception as e:
            logger.warning(f"Error putting EPD into sleep mode: {e}")

        epdconfig = getattr(self.epd_module, "epdconfig", None)
        implementation = getattr(epdconfig, "implementation", None)
        closed_devices = set()
        for attribute in (
            "GPIO_RST_PIN",
            "GPIO_DC_PIN",
            "GPIO_CS_PIN",
            "GPIO_PWR_PIN",
            "GPIO_BUSY_PIN",
        ):
            device = getattr(implementation, attribute, None)
            if device is None or id(device) in closed_devices:
                continue
            closed_devices.add(id(device))
            try:
                device.close()
            except Exception as e:
                logger.warning(
                    f"Error closing EPD GPIO device {attribute}: {e}"
                )

        try:
            import gpiozero

            pin_factory = getattr(gpiozero.Device, "pin_factory", None)
            if pin_factory is not None:
                pin_factory.close()
        except ImportError:
            # Non-Raspberry Pi backends do not use gpiozero.
            pass
        except Exception as e:
            logger.warning(f"Error closing gpiozero pin factory: {e}")

        try:
            import lgpio

            notify_thread = getattr(lgpio, "_notify_thread", None)
            if notify_thread is not None:
                notify_thread.stop()
                notify_handle = getattr(notify_thread, "_notify", None)
                if notify_handle is not None:
                    lgpio.notify_close(notify_handle)
                notify_thread.join(timeout=1)
                if notify_thread.is_alive():
                    logger.warning(
                        "lgpio notification thread did not stop "
                        "within 1 second"
                    )
        except ImportError:
            pass
        except Exception as e:
            logger.warning(
                f"Error stopping lgpio notification thread: {e}"
            )
