"""Strict core SV2 mining codecs, checked against sv2-spec and SRI constants."""
from struct import pack,unpack
from .stratum_v1 import ProtocolError

SETUP=0;SETUP_OK=1;SETUP_ERROR=2;ENDPOINT_CHANGED=3;RECONNECT=4
OPEN_STANDARD=0x10;OPEN_STANDARD_OK=0x11;OPEN_ERROR=0x12;OPEN_EXTENDED=0x13;OPEN_EXTENDED_OK=0x14
NEW_STANDARD=0x15;UPDATE=0x16;UPDATE_ERROR=0x17;CLOSE=0x18;EXTRANONCE=0x19
SUBMIT_STANDARD=0x1A;SUBMIT_EXTENDED=0x1B;SUBMIT_OK=0x1C;SUBMIT_ERROR=0x1D
NEW_EXTENDED=0x1F;PREV_HASH=0x20;TARGET=0x21;GROUP=0x25
CHANNEL_TYPES={NEW_STANDARD,UPDATE,UPDATE_ERROR,CLOSE,EXTRANONCE,SUBMIT_STANDARD,SUBMIT_EXTENDED,SUBMIT_OK,SUBMIT_ERROR,NEW_EXTENDED,PREV_HASH,TARGET}

def blob(raw,limit=255,width=1):
    if len(raw)>limit:raise ProtocolError("SV2 byte field exceeds bound")
    return len(raw).to_bytes(width,"little")+raw
def text(value):return blob(value.encode("utf-8"))
def option(value):return b"\x00" if value is None else b"\x01"+pack("<I",value)

class Reader:
    def __init__(self,data):self.data=data;self.offset=0
    def take(self,size):
        if size<0 or self.offset+size>len(self.data):raise ProtocolError("Truncated SV2 message")
        data=self.data[self.offset:self.offset+size];self.offset+=size;return data
    def integer(self,size=4):return int.from_bytes(self.take(size),"little")
    def bytes(self,limit=255,width=1):
        size=self.integer(width)
        if size>limit:raise ProtocolError("SV2 sequence bound exceeded")
        return self.take(size)
    def text(self):
        value=self.bytes()
        if any(b<32 or b>126 for b in value):raise ProtocolError("Nonprintable SV2 error/host code")
        return value.decode("ascii")
    def option(self):
        count=self.integer(1)
        if count not in (0,1):raise ProtocolError("Invalid OPTION[U32]")
        return self.integer() if count else None
    def finish(self):
        if self.offset!=len(self.data):raise ProtocolError("Unexpected unnegotiated SV2 fields")

def setup(host,port,extended=False):
    return pack("<BHHI",0,2,2,0 if extended else 1)+text(host)+pack("<H",port)+text("Nucleus-BTC")+text("commodity CPU/GPU")+text("0.2")+text("nucleus")
def open_channel(worker,hashrate,target,extended=False,min_extranonce_size=4):
    if not 0<=hashrate<3.4e38 or not 0<target<1<<256:raise ProtocolError("Invalid channel rate/target")
    raw=pack("<I",1)+text(worker)+pack("<f",hashrate)+target.to_bytes(32,"little")
    return raw+pack("<H",min_extranonce_size) if extended else raw
