# epd_helper.py

import importlib
import logging
import time

logger = logging.getLogger(__name__)

class EPDHelper:
    def __init__(self, epd_type):
        self.epd_type = epd_type
        self.epd = self._load_epd_module()
        self.is_tri_color = epd_type in ["epd2in13bc"]
        self.refresh_count = 0
        self.full_refresh_interval = 20  # 每20次刷新后执行全刷清屏
        self.last_sleep_time = 0
        self.sleep_interval = 1800  # 30分钟强制睡眠一次（保护屏幕）
        self.min_refresh_interval = 180 if self.is_tri_color else 1  # 三色屏最小180秒

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
            if self.is_tri_color:
                self.epd.init()
                logger.info("EPD tri-color mode: using full update instead of partial.")
            elif hasattr(self.epd, 'PART_UPDATE'):
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
            if self.is_tri_color:
                current_time = time.time()
                
                # 每N次刷新后执行全刷清屏
                if self.refresh_count >= self.full_refresh_interval:
                    logger.info("Tri-color EPD: performing full refresh to clear ghosting.")
                    self.clear()
                    self.refresh_count = 0
                
                # 每隔一段时间强制睡眠一次以保护膜片
                if current_time - self.last_sleep_time >= self.sleep_interval:
                    logger.info("Tri-color EPD: periodic sleep to protect panel.")
                    self.sleep()
                    self.last_sleep_time = current_time
                    # 睡眠后需要重新初始化
                    self.init_partial_update()

                buf = self.epd.getbuffer(image)
                red_buf = [0xFF] * len(buf)
                self.epd.display(buf, red_buf)
                self.refresh_count += 1
            elif hasattr(self.epd, 'displayPartial'):
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

    def sleep(self):
        try:
            if hasattr(self.epd, 'sleep'):
                self.epd.sleep()
                logger.info("EPD entered sleep mode.")
        except Exception as e:
            logger.error(f"Error putting EPD to sleep: {e}")
