import logging
from . import epdconfig

# Display resolution
EPD_WIDTH       = 122
EPD_HEIGHT      = 250

logger = logging.getLogger(__name__)

class EPD:
    def __init__(self):
        self.is_initialized = False  # New flag to track if the display has been initialized #INFINITION
        self.reset_pin = epdconfig.RST_PIN
        self.dc_pin = epdconfig.DC_PIN
        self.busy_pin = epdconfig.BUSY_PIN
        self.cs_pin = epdconfig.CS_PIN
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT
        
    '''
    function :Hardware reset
    parameter:
    '''
    def reset(self):
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(20) 
        epdconfig.digital_write(self.reset_pin, 0)
        epdconfig.delay_ms(2)
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(20)   

    '''
    function :send command
    parameter:
     command : Command register
    '''
    def send_command(self, command):
        epdconfig.digital_write(self.dc_pin, 0)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte([command])
        epdconfig.digital_write(self.cs_pin, 1)

    '''
    function :send data
    parameter:
     data : Write data
    '''
    def send_data(self, data):
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte([data])
        epdconfig.digital_write(self.cs_pin, 1)

    # send a lot of data   
    def send_data2(self, data):
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte2(data)
        epdconfig.digital_write(self.cs_pin, 1)
    
    '''
    function :Wait until the busy_pin goes LOW
    parameter:
    '''
    def ReadBusy(self):
        logger.debug("e-Paper busy")
        while(epdconfig.digital_read(self.busy_pin) == 1):      # 0: idle, 1: busy
            epdconfig.delay_ms(10)  
        logger.debug("e-Paper busy release")

    '''
    function : Turn On Display
    parameter:
    '''
    def TurnOnDisplay(self):
        self.send_command(0x22) # Display Update Control
        self.send_data(0xf7)
        self.send_command(0x20) # Activate Display Update Sequence
        self.ReadBusy()

    '''
    function : Turn On Display Fast
    parameter:
    '''
    def TurnOnDisplay_Fast(self):
        self.send_command(0x22) # Display Update Control
        self.send_data(0xC7)    # fast:0x0c, quality:0x0f, 0xcf
        self.send_command(0x20) # Activate Display Update Sequence
        self.ReadBusy()
    
    '''
    function : Turn On Display Part
    parameter:
    '''
    def TurnOnDisplayPart(self):
        self.send_command(0x22) # Display Update Control
        self.send_data(0xff)    # fast:0x0c, quality:0x0f, 0xcf
        self.send_command(0x20) # Activate Display Update Sequence
        self.ReadBusy()


    '''
    function : Setting the display window
    parameter:
        xstart : X-axis starting position
        ystart : Y-axis starting position
        xend : End position of X-axis
        yend : End position of Y-axis
    '''
    def SetWindow(self, x_start, y_start, x_end, y_end):
        self.send_command(0x44) # SET_RAM_X_ADDRESS_START_END_POSITION
        # x point must be the multiple of 8 or the last 3 bits will be ignored
        self.send_data((x_start>>3) & 0xFF)
        self.send_data((x_end>>3) & 0xFF)
        
        self.send_command(0x45) # SET_RAM_Y_ADDRESS_START_END_POSITION
        self.send_data(y_start & 0xFF)
        self.send_data((y_start >> 8) & 0xFF)
        self.send_data(y_end & 0xFF)
        self.send_data((y_end >> 8) & 0xFF)

    '''
    function : Set Cursor
    parameter:
        x : X-axis starting position
        y : Y-axis starting position
    '''
    def SetCursor(self, x, y):
        self.send_command(0x4E) # SET_RAM_X_ADDRESS_COUNTER
        # x point must be the multiple of 8 or the last 3 bits will be ignored
        self.send_data(x & 0xFF)
        
        self.send_command(0x4F) # SET_RAM_Y_ADDRESS_COUNTER
        self.send_data(y & 0xFF)
        self.send_data((y >> 8) & 0xFF)
    
    '''
    function : Initialize the e-Paper register
    parameter:
    '''
    def init(self):
        if not self.is_initialized:  # Avoid repeated initialization and accumulation of File descriptors #INFINITION
            if epdconfig.module_init() != 0:
                return -1
            self.reset()
            self.is_initialized = True
        self.ReadBusy()
        self.send_command(0x12)  #SWRESET
        self.ReadBusy() 

        self.send_command(0x01) #Driver output control      
        self.send_data(0xf9)
        self.send_data(0x00)
        self.send_data(0x00)
    
        self.send_command(0x11) #data entry mode       
        self.send_data(0x03)

        self.SetWindow(0, 0, self.width-1, self.height-1)
        self.SetCursor(0, 0)
        
        self.send_command(0x3c)
        self.send_data(0x05)

        self.send_command(0x21) #  Display update control
        self.send_data(0x00)
        self.send_data(0x80)
    
        self.send_command(0x18)
        self.send_data(0x80)
        
        self.ReadBusy()
        
        return 0

    '''
    function : Initialize the e-Paper fast register
    parameter:
    '''
    def init_fast(self):
        if (epdconfig.module_init() != 0):
            return -1
        # EPD hardware init start
        self.reset()

        self.send_command(0x12)  #SWRESET
        self.ReadBusy() 

        self.send_command(0x18) # Read built-in temperature sensor
        self.send_command(0x80)

        self.send_command(0x11) # data entry mode       
        self.send_data(0x03)    

        self.SetWindow(0, 0, self.width-1, self.height-1)
        self.SetCursor(0, 0)
        
        self.send_command(0x22) # Load temperature value
        self.send_data(0xB1)	
        self.send_command(0x20)
        self.ReadBusy()

        self.send_command(0x1A) # Write to temperature register
        self.send_data(0x64)
        self.send_data(0x00)
                        
        self.send_command(0x22) # Load temperature value
        self.send_data(0x91)	
        self.send_command(0x20)
        self.ReadBusy()
        
        return 0
    '''
    function : Display images
    parameter:
        image : Image data
    '''
    def getbuffer(self, image):
        img = image
        imwidth, imheight = img.size
        if(imwidth == self.width and imheight == self.height):
            img = img.convert('1')
        elif(imwidth == self.height and imheight == self.width):
            # image has correct dimensions, but needs to be rotated
            img = img.rotate(90, expand=True).convert('1') 
            #to remove
        else:
            logger.warning("Wrong image dimensions: must be " + str(self.width) + "x" + str(self.height))
            # return a blank buffer
            return [0x00] * (int(self.width/8) * self.height)

        buf = bytearray(img.tobytes('raw')) 
        return buf
        
    '''
    function : Sends the image buffer in RAM to e-Paper and displays
    parameter:
        image : Image data
    '''
    def display(self, image):
        self.send_command(0x24)
        self.send_data2(image)  
        self.TurnOnDisplay()
    
    '''
    function : Sends the image buffer in RAM to e-Paper and fast displays
    parameter:
        image : Image data
    '''
    def display_fast(self, image):
        self.send_command(0x24)
        self.send_data2(image) 
        self.TurnOnDisplay_Fast()
    '''
    function : Sends the image buffer in RAM to e-Paper and partial refresh
    parameter:
        image : Image data
    '''
    def displayPartial(self, image):
        epdconfig.digital_write(self.reset_pin, 0)
        epdconfig.delay_ms(1)
        epdconfig.digital_write(self.reset_pin, 1)  

        self.send_command(0x3C) # BorderWavefrom
        self.send_data(0x80)

        self.send_command(0x01) # Driver output control      
        self.send_data(0xF9) 
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x11) # data entry mode       
        self.send_data(0x03)

        self.SetWindow(0, 0, self.width - 1, self.height - 1)
        self.SetCursor(0, 0)
        
        self.send_command(0x24) # WRITE_RAM
        self.send_data2(image)  
        self.TurnOnDisplayPart()

    '''
    function : Refresh a base image
    parameter:
        image : Image data
    '''
    def displayPartBaseImage(self, image):
        self.send_command(0x24)
        self.send_data2(image)  
                
        self.send_command(0x26)
        self.send_data2(image)  
        self.TurnOnDisplay()
    
    '''
    function : Clear screen
    parameter:
    '''
    def Clear(self, color=0xFF):
        if self.width%8 == 0:
            linewidth = int(self.width/8)
        else:
            linewidth = int(self.width/8) + 1
        # logger.debug(linewidth)
        
        self.send_command(0x24)
        self.send_data2([color] * int(self.height * linewidth))  
        self.TurnOnDisplay()

    '''
    function : Enter sleep mode
    parameter:
    '''
    def sleep(self):
        self.send_command(0x10) #enter deep sleep
        self.send_data(0x01)
        
        epdconfig.delay_ms(2000)
        epdconfig.module_exit()

### END OF FILE ###

