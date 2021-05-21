from machine import Pin

from constants import CONSTANTS
from hardware import KtaneHardware
from log import LOG

# Constants:
CONFIG_FILENAME = "config.txt"

LED0_RED = 21
LED0_GREEN = 22
LED0_BLUE = 26
LED1_RED = 14
LED1_GREEN = 16
LED1_BLUE = 17
LED2_RED = 13
LED2_GREEN = 12
LED2_BLUE = 11
LED3_RED = 18
LED3_GREEN = 19
LED3_BLUE = 20

BUTTON = 2


class ButtonModule(KtaneHardware):
    def __init__(self) -> None:
        KtaneHardware.__init__(self, self.read_config())
        self.handlers.update(
            {
                CONSTANTS.PROTOCOL.PACKET_TYPE.REQUEST_ID: self.request_id,
                CONSTANTS.PROTOCOL.PACKET_TYPE.CONFIGURE: self.configure,
                CONSTANTS.PROTOCOL.PACKET_TYPE.START: self.start,
                CONSTANTS.PROTOCOL.PACKET_TYPE.STOP: self.stop,
                CONSTANTS.PROTOCOL.PACKET_TYPE.DISARMED: self.disarmed,
            }
        )
        self.button_color=
        self.button_text=b""
        self.num_batteries=0

    @staticmethod
    def read_config() -> int:
        # Format:
        #
        # Field    Length   Notes
        # ------   ------   ---------------------------------------------
        # unique   1        Unique portion of ID, assigned at manufacture
        unique = b""
        try:
            file_obj = open(CONFIG_FILENAME, "rb")
            unique = file_obj.read(1)
            file_obj.close()
        except OSError:
            pass

        return (MT_BUTTON << 8) | (ord(unique) if unique else 0x00)
