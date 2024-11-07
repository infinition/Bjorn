# epd_helper.py

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