#Test script to add more actions to  BJORN 

from rich.console import Console
from shared import SharedData

b_class = "IDLE"   
b_module = "idle_action" 
b_status = "idle_action"  
b_port = None  
b_parent = None 

console = Console()

class IDLE:
    def __init__(self, shared_data):
        self.shared_data = shared_data
        


    
