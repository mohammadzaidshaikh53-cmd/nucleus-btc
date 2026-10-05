"""Pinned-authority authenticated Noise with official reference cryptography.

Only encrypted framing crosses the socket. Cryptography is delegated to the
locked Rust noise_sv2 helper; no unauthenticated or plaintext fallback exists.
"""
import json
import os
import queue
import select
import socket
import subprocess
import threading
from pathlib import Path
from hashlib import sha256
from .stratum_v1 import ProtocolError
from .stratum_v2 import Frame

ROOT=Path(__file__).resolve().parents[2]
MAX_PLAIN=65519

def authority_key(text):
    alphabet="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    value=0
    if not 1<=len(text)<=64:raise ValueError("Invalid SV2 authority encoding")
    for char in text:
        if char not in alphabet:raise ValueError("Invalid SV2 base58 key")
        value=value*58+alphabet.index(char)
    raw=b"\x00"*(len(text)-len(text.lstrip("1")))+value.to_bytes((value.bit_length()+7)//8,"big")
    if len(raw)!=38 or raw[:2]!=b"\x01\x00" or sha256(sha256(raw[:-4]).digest()).digest()[:4]!=raw[-4:]:raise ValueError("SV2 authority version/checksum mismatch")
    return raw[2:-4]

class NoiseProcess:
    def __init__(self,executable=None,timeout=10):
        suffix=".exe" if os.name=="nt" else ""
        choices=[ROOT/"build"/("nucleus-sv2-noise"+suffix),ROOT/"native"/"sv2-noise"/"target"/"release"/("nucleus-sv2-noise"+suffix)]
        executable=Path(executable) if executable else next((p for p in choices if p.is_file()),None)
        if executable is None:raise ProtocolError("SV2 Noise helper unavailable; build native/sv2-noise with Cargo")
        self.timeout=timeout;self.answers=queue.Queue(maxsize=1);self.closed=False
        self.process=subprocess.Popen([str(executable)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        def reader():
            try:
                while True:
                    line=self.process.stdout.readline(140001)
                    if not line:
                        if not self.closed:self.answers.put({"error":"Noise helper exited"},timeout=.1)
                        return
                    if len(line)>140000:raise ValueError("Oversized helper response")
                    answer=json.loads(line)
                    if not isinstance(answer,dict):raise ValueError("Invalid helper object")
                    self.answers.put(answer,timeout=.1)
            except (OSError,ValueError,queue.Full):
                if not self.closed:
                    try:self.answers.put({"error":"Invalid Noise helper response"},timeout=.1)
                    except queue.Full:pass
        self.reader=threading.Thread(target=reader,daemon=True);self.reader.start()
    def request(self,operation,data):
        if self.closed or len(data)>65536:raise ProtocolError("Closed or oversized Noise request")
        try:
            self.process.stdin.write((json.dumps({"op":operation,"data":data.hex()})+"\n").encode());self.process.stdin.flush()
            answer=self.answers.get(timeout=self.timeout)
            if answer.get("error"):raise ProtocolError(answer["error"])
            return bytes.fromhex(answer["data"])
        except (OSError,ValueError,KeyError,queue.Empty) as error:
            self.close();raise ProtocolError("Noise helper failed or timed out") from None
        except ProtocolError:self.close();raise
    def close(self):
        if self.closed:return
        self.closed=True
        if self.process.poll() is None:self.process.terminate()
        try:self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=2)
        self.process.stdin.close();self.process.stdout.close()
        self.reader.join(timeout=1)

class NoiseTransport:
    def __init__(self,sock,codec=None,max_payload=1<<20,timeout=10):
        self.socket=sock;self.codec=codec or NoiseProcess(timeout=timeout);self.max_payload=max_payload
        self.buffer=bytearray();self.header=None;self.body_size=0;self.closed=False;self.authenticated=False
        self.socket.settimeout(timeout)
    def handshake(self,key):
        if len(key)!=32:raise ValueError("Pinned 32-byte authority key required")
        try:
            self.socket.sendall(self.codec.request("init",key));reply=bytearray()
            while len(reply)<234:
                data=self.socket.recv(234-len(reply))
                if not data:raise ProtocolError("Disconnected during Noise handshake")
                reply.extend(data)
            self.codec.request("finish",bytes(reply));self.authenticated=True
        except Exception:self.close();raise
    def send_frame(self,frame):
        if not self.authenticated:raise ProtocolError("Authenticated Noise handshake required")
        raw=frame.encode()
        if len(frame.payload)>self.max_payload:raise ProtocolError("SV2 payload bound exceeded")
        try:
            encrypted=self.codec.request("encrypt",raw[:6])
            for i in range(6,len(raw),MAX_PLAIN):encrypted+=self.codec.request("encrypt",raw[i:i+MAX_PLAIN])
            self.socket.sendall(encrypted)
        except Exception:self.close();raise
    def recv_frame(self,timeout=0):
        if not self.authenticated:raise ProtocolError("Authenticated Noise handshake required")
        try:
            ready=self.header is not None and len(self.buffer)>=self.body_size or self.header is None and len(self.buffer)>=22
            if not ready:
                if not select.select([self.socket],[],[],timeout)[0]:return None
                data=self.socket.recv(65536)
                if not data:raise ProtocolError("SV2 upstream disconnected")
                self.buffer.extend(data)
            if self.header is None:
                if len(self.buffer)<22:return None
                self.header=self.codec.request("decrypt",bytes(self.buffer[:22]));del self.buffer[:22]
                if len(self.header)!=6:raise ProtocolError("Malformed encrypted SV2 header")
                length=int.from_bytes(self.header[3:6],"little")
                if length>self.max_payload:raise ProtocolError("SV2 payload bound exceeded")
                self.body_size=length+16*((length+MAX_PLAIN-1)//MAX_PLAIN)
            if len(self.buffer)<self.body_size:return None
            ciphertext=bytes(self.buffer[:self.body_size]);del self.buffer[:self.body_size]
            payload=b"".join(self.codec.request("decrypt",ciphertext[i:i+65535]) for i in range(0,len(ciphertext),65535))
            frame=Frame.decode(self.header+payload);self.header=None;self.body_size=0;return frame
        except Exception:self.close();raise
    def close(self):
        if self.closed:return
        self.closed=True;self.socket.close();self.codec.close();self.buffer.clear()
