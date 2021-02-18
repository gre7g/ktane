import attr
from enum import Enum
from queue import Queue
from serial import Serial
import struct
from threading import Thread
from typing import Callable, List, Optional
import wx

# Constants:
PORT = "COM4"
BAUD = 38400
SERIAL_TIMEOUT = 1.0
MAX_LOG_LINES = 10


def listener(port: str, outgoing: Queue, incoming: Callable):
    serial = Serial(port, BAUD, timeout=SERIAL_TIMEOUT)
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
                    serial.write(packet.to_bytes())
                else:
                    break
    finally:
        serial.close()


class PacketType(Enum):
    REQUEST_ID = 0
    RESPONSE_ID = 1
    STOP = 2
    START = 3
    STRIKE = 4
    ERROR = 5
    DEFUSED = 6
    NEEDY = 7
    READ_STATUS = 8
    STATUS = 9
    SOUND_REQUEST = 10


@attr.s(repr=False)
class Packet:
    data: bytes = attr.ib(default=b"")
    source: int = attr.ib(default=0)
    dest: int = attr.ib(default=0)
    packet_type: Optional[PacketType] = attr.ib(default=None)
    seq_num: int = attr.ib(default=0)
    payload: bytes = attr.ib(default=b"")

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
        button = wx.Button(self, label="BUTTON 2")
        sizer3.Add(button, 0, wx.EXPAND | wx.TOP, 10)
        button = wx.Button(self, label="BUTTON 3")
        sizer3.Add(button, 0, wx.EXPAND | wx.TOP, 10)
        button = wx.Button(self, label="BUTTON 4")
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
        packet = Packet(dest=0xFFFF, packet_type=PacketType.REQUEST_ID)
        app: TerminalApp = wx.GetApp()
        app.outgoing.put(packet)
        self.add(packet)


class TerminalApp(wx.App):
    def OnInit(self):
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

    def incoming(self, data: bytes):
        self.frame.add(data)


if __name__ == "__main__":
    app = TerminalApp()
    app.MainLoop()
