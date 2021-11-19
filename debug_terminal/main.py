import attr
from enum import Enum
from queue import Queue
from serial import Serial
import struct
from threading import Thread
from typing import Callable, List, Optional
import wx

from ktane_lib.constants import CONSTANTS

# Constants:
PORT = "COM4"
SERIAL_TIMEOUT = 1.0
MAX_LOG_LINES = 20
TIMER = 0x1200


def listener(port: str, outgoing: Queue, incoming: Callable):
    serial = Serial(port, CONSTANTS.UART.BAUD_RATE, timeout=SERIAL_TIMEOUT)
    try:
        while True:
            if outgoing.empty():
                data = serial.read(1)  # length
                if data:
                    length = ord(data)
                    wx.CallAfter(incoming, data + serial.read(length + 2))  # checksum
            else:
                packet: Optional[Packet] = outgoing.get()
                if packet:
                    print("out", packet)
                    serial.write(packet.to_bytes())
                else:
                    break
    finally:
        serial.close()


class PacketType(Enum):
    ACK = 0x80
    REQUEST_ID = 0x01
    RESPONSE_ID = 0x81
    STOP = 0x02
    CONFIGURE = 0x03
    START = 0x04
    STRIKE = 0x05
    ERROR = 0x06
    DEFUSED = 0x07
    NEEDY = 0x08
    READ_STATUS = 0x09
    STATUS = 0x89
    SOUND_REQUEST = 0x0A
    SET_TIME = 0x0B


@attr.s(repr=False)
class Packet:
    packet_type: Optional[PacketType] = attr.ib(default=None)
    dest: int = attr.ib(default=0)
    seq_num: int = attr.ib(default=0)
    payload: bytes = attr.ib(default=b"")
    data: bytes = attr.ib(default=b"")
    source: int = attr.ib(default=0)

    def __repr__(self) -> str:
        if self.packet_type is None:
            try:
                length, self.source, self.dest, packet_type, self.seq_num = struct.unpack("<BHHBB", self.data[:7])
                assert len(self.data) == (1 + length + 2)
                self.packet_type = PacketType(packet_type)
                self.payload = self.data[7:-2]
                (checksum,) = struct.unpack("<H", self.data[-2:])
                assert (sum(self.data[:-2]) + checksum) == 0xFFFF
            except (AssertionError, struct.error, ValueError):
                return repr(self.data)
        return "<Packet source=0x%04x dest=0x%04x packet_type=%s seq_num=0x%02x payload=%r>" % (
            self.source,
            self.dest,
            self.packet_type.name,
            self.seq_num,
            self.payload,
        )

    def to_bytes(self):
        if self.packet_type is None:
            return self.data
        else:
            data = (
                struct.pack(
                    "<BHHBB",
                    2 + 2 + 1 + 1 + len(self.payload),
                    self.source,
                    self.dest,
                    self.packet_type.value,
                    self.seq_num,
                )
                + self.payload
            )
            checksum = 0xFFFF - sum(data)
            return data + struct.pack("<H", checksum)


class TermFrame(wx.Frame):
    log_lines: List[Packet]

    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)
        sizer1 = wx.BoxSizer(wx.VERTICAL)
        sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer1.Add(sizer2, 1, wx.ALL | wx.EXPAND, 10)
        sizer3 = wx.BoxSizer(wx.VERTICAL)
        sizer2.Add(sizer3, 1, wx.EXPAND, 0)
        button = wx.Button(self, label="REQUEST_ID")
        button.Bind(wx.EVT_BUTTON, self.on_request_id)
        sizer3.Add(button, 0, wx.EXPAND, 0)
        button = wx.Button(self, label="CONFIGURE1")
        button.Bind(wx.EVT_BUTTON, self.on_configure1)
        sizer3.Add(button, 0, wx.EXPAND | wx.TOP, 10)
        button = wx.Button(self, label="CONFIGURE2")
        button.Bind(wx.EVT_BUTTON, self.on_configure2)
        sizer3.Add(button, 0, wx.EXPAND | wx.TOP, 10)
        button = wx.Button(self, label="START")
        button.Bind(wx.EVT_BUTTON, self.on_start)
        sizer3.Add(button, 0, wx.EXPAND | wx.TOP, 10)
        button = wx.Button(self, label="STOP")
        button.Bind(wx.EVT_BUTTON, self.on_stop)
        sizer3.Add(button, 0, wx.EXPAND | wx.TOP, 10)
        button = wx.Button(self, label="SET_TIME")
        button.Bind(wx.EVT_BUTTON, self.set_time)
        sizer3.Add(button, 0, wx.EXPAND | wx.TOP, 10)
        self.log_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer2.Add(self.log_ctrl, 3, wx.LEFT | wx.EXPAND, 10)
        self.SetSizerAndFit(sizer1)

        self.log_lines = []

    def add(self, line: Packet):
        lines = [line] + self.log_lines
        self.log_lines = lines[:MAX_LOG_LINES]
        self.log_ctrl.SetValue("\n".join([repr(packet) for packet in self.log_lines]))

    def on_request_id(self, _event: wx.CommandEvent):
        app: TerminalApp = wx.GetApp()
        app.seq_num = (app.seq_num + 1) & 0xFF
        packet = Packet(PacketType.REQUEST_ID, CONSTANTS.MODULES.BROADCAST_ALL, app.seq_num)
        app.outgoing.put(packet)
        self.add(packet)

    def on_configure1(self, _event: wx.CommandEvent):
        app: TerminalApp = wx.GetApp()
        app.seq_num = (app.seq_num + 1) & 0xFF
        packet = Packet(PacketType.CONFIGURE, 0x0100, app.seq_num, b"12345")
        app.outgoing.put(packet)
        self.add(packet)

    def on_configure2(self, _event: wx.CommandEvent):
        app: TerminalApp = wx.GetApp()
        app.seq_num = (app.seq_num + 1) & 0xFF
        packet = Packet(PacketType.CONFIGURE, 0x0200, app.seq_num, b"\x03HOLD\x00\x00\x00\x00\x00\x01CAR")
        app.outgoing.put(packet)
        self.add(packet)

    def on_start(self, _event: wx.CommandEvent):
        app: TerminalApp = wx.GetApp()
        app.seq_num = (app.seq_num + 1) & 0xFF
        packet = Packet(PacketType.START, CONSTANTS.MODULES.BROADCAST_ALL, app.seq_num, b"\x00")
        app.outgoing.put(packet)
        self.add(packet)

    def on_stop(self, _event: wx.CommandEvent):
        app: TerminalApp = wx.GetApp()
        app.send_stop()

    def set_time(self, _event: wx.CommandEvent):
        app: TerminalApp = wx.GetApp()
        app.send_set_time()


class TerminalApp(wx.App):
    seq_num: int

    def OnInit(self):
        self.seq_num = 0
        self.frame = TermFrame(None, title="KTANE Terminal")
        self.frame.Show()
        self.frame.Bind(wx.EVT_CLOSE, self.on_close)
        self.outgoing = Queue()
        thread = Thread(target=listener, args=(PORT, self.outgoing, self.incoming))
        thread.start()
        return True

    def on_close(self, event: wx.CloseEvent):
        event.Skip()
        self.outgoing.put(None)

    def send_ack(self, dest: int, seq_num: int):
        packet = Packet(PacketType.ACK, dest, seq_num)
        self.outgoing.put(packet)
        self.frame.add(packet)

    def send_stop(self):
        self.seq_num = (self.seq_num + 1) & 0xFF
        packet = Packet(PacketType.STOP, CONSTANTS.MODULES.BROADCAST_ALL, self.seq_num)
        self.outgoing.put(packet)
        self.frame.add(packet)

    def send_set_time(self):
        self.seq_num = (self.seq_num + 1) & 0xFF
        packet = Packet(
            PacketType.SET_TIME, CONSTANTS.MODULES.TYPES.TIMER, self.seq_num, struct.pack("<L", 70 * 1000000)
        )
        self.outgoing.put(packet)
        self.frame.add(packet)

    def send_status(self, source: int, seq_num: int):
        packet = Packet(PacketType.STATUS, source, seq_num, b"\x01\x0012:34")
        self.outgoing.put(packet)

    def incoming(self, data: bytes):
        packet = Packet(data=data)
        print("in", packet)
        self.frame.add(packet)
        if packet.packet_type != PacketType.ACK:
            self.seq_num = packet.seq_num
        if packet.packet_type == PacketType.ERROR:
            self.send_ack(packet.source, packet.seq_num)
            self.send_stop()
        elif packet.packet_type == PacketType.READ_STATUS:
            self.send_status(packet.source, packet.seq_num)
        elif ((packet.dest & CONSTANTS.MODULES.BROADCAST_MASK) != CONSTANTS.MODULES.BROADCAST_MASK) and (
            (packet.packet_type.value & PacketType.ACK.value) != PacketType.ACK.value
        ):
            self.send_ack(packet.source, packet.seq_num)


if __name__ == "__main__":
    app = TerminalApp()
    app.MainLoop()
