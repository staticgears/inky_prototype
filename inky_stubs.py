import datetime, sys
from types import ModuleType

# 1. Define fake modules
class MockButton:
    def __init__(self):
        pass
    def read():
        false
    def led_on():
        pass
    def led_off():
        pass
    def led_toggle():
        pass

class MockInkyFrame:
    def __init__(self):
        pass

    def display(self):
        print("[Mock Inky] Display refreshed!")

    def set_pixel(self, x, y, color):
        pass
 
    def set_time():
        pass

class MockRTC:
    def __init__(self):
        pass
    def datetime():
        datetime.datetime.now()

# 2. Inject it into Python's module cache
mock_inky_frame = ModuleType("inky_frame")
mock_inky_frame.button_a = MockButton()
mock_inky_frame.button_b = MockButton()
mock_inky_frame.button_c = MockButton()
mock_inky_frame.button_d = MockButton()
mock_inky_frame.button_e = MockButton()
mock_inky_frame.led_busy = MockButton()
mock_inky_frame.led_wifi = MockButton()
mock_inky_frame.InkyFrame = MockInkyFrame

sys.modules["inky_frame"] = mock_inky_frame

mock_machine = ModuleType("machine")
mock_machine.RTC = MockRTC
sys.modules["machine"] = mock_machine

mock_jpegdec = ModuleType("jpegdec")
mock_jpegdec.JPEG = None 
sys.modules["jpegdec"] = mock_jpegdec
