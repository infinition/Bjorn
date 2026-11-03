# epd_helper.py
#
# Thin wrapper around the bundled Waveshare EPD drivers.
#
# This project targets the Waveshare 2.13" e-Paper HAT V4 (epd2in13_V4), a
# 122x250 black/white panel. The helper is written around that panel's refresh
# model but keeps hasattr() guards so the older drivers (V2/V3/2in7) still load
# without crashing.
#
# E-ink refresh model, in short:
#   - A "full" refresh flashes the panel black/white and fully clears every
#     pixel. It is slow but wipes out "ghosting" (faint residue left behind by
#     partial updates).
#   - A "partial" refresh updates pixels in place with no flash. It is fast but
#     leaves ghosting that accumulates over many updates.
#   - displayPartBaseImage() seeds the panel's base RAM bank so that subsequent
#     partial updates diff cleanly against a known image.
# The display loop uses partial updates for speed and periodically forces a full
# refresh (via set_base_image) to clear accumulated ghosting.

import importlib
import logging

logger = logging.getLogger(__name__)


class EPDHelper:
    def __init__(self, epd_type):
        self.epd_type = epd_type
        self.epd = self._load_epd_module()

    def _load_epd_module(self):
        try:
            epd_module_name = f'resources.waveshare_epd.{self.epd_type}'
            epd_module = importlib.import_module(epd_module_name)
            return epd_module.EPD()
        except ImportError as e:
            logger.error(f"EPD module {self.epd_type} not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading EPD module {self.epd_type}: {e}")
            raise

    def init_full_update(self):
        """Run the panel's full initialization sequence.

        On the V4 driver init() takes no argument; the older V2/V3 drivers take
        a mode flag, so we branch on the attributes the driver exposes.
        """
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
        """Initialize the panel for partial updates.

        The V4 driver's displayPartial() is self-contained (it performs its own
        soft reset and register setup on every call), so on the V4 this is only
        needed once. We keep it for driver compatibility.
        """
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

    def set_base_image(self, image):
        """Seed the base image and perform a full (ghost-clearing) refresh.

        displayPartBaseImage writes the image to both the working and base RAM
        banks and drives a full refresh, which both clears accumulated ghosting
        and establishes a clean reference for later partial updates.
        """
        try:
            buffer = self.epd.getbuffer(image)
            if hasattr(self.epd, 'displayPartBaseImage'):
                self.epd.displayPartBaseImage(buffer)
            else:
                self.epd.display(buffer)
            logger.info("EPD base image set (full refresh).")
        except Exception as e:
            logger.error(f"Error setting EPD base image: {e}")
            raise

    def display_partial(self, image):
        """Perform a single fast partial refresh."""
        try:
            buffer = self.epd.getbuffer(image)
            if hasattr(self.epd, 'displayPartial'):
                self.epd.displayPartial(buffer)
            else:
                self.epd.display(buffer)
            logger.debug("Partial display update complete.")
        except Exception as e:
            logger.error(f"Error during partial display update: {e}")
            raise

    def sleep(self):
        """Put the panel into deep sleep.

        Waveshare warns that leaving an e-paper powered in a non-sleep state for
        long periods can damage it, so the display must be slept on shutdown.
        """
        try:
            if hasattr(self.epd, 'sleep'):
                self.epd.sleep()
                logger.info("EPD entered deep sleep.")
        except Exception as e:
            logger.error(f"Error putting EPD to sleep: {e}")

    def clear(self):
        try:
            self.epd.Clear()
            logger.info("EPD cleared.")
        except Exception as e:
            logger.error(f"Error clearing EPD: {e}")
            raise
