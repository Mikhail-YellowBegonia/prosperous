import sys
import os
import termios
import tty
import threading
import select
import codecs
from utils import debug_log

class InputHandler:
    KEY_MAP = {
        '\x1b[A': 'UP',
        '\x1b[B': 'DOWN',
        '\x1b[C': 'RIGHT',
        '\x1b[D': 'LEFT',
        '\r': 'ENTER',
        '\n': 'ENTER',
        '\x1b': 'ESC',
        '\x7f': 'BACKSPACE',
        '\t': 'TAB',
    }

    def __init__(self, engine):
        self.engine = engine
        self.fd = sys.stdin.fileno()
        self.old_settings = None
        # 使用替换模式处理无法解码的字节，但在逻辑中我们会尽量避免
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.buffer = b""

    def listen(self):
        self.old_settings = termios.tcgetattr(self.fd)
        try:
            tty.setraw(self.fd)
            while self.engine.is_running:
                dr, _, _ = select.select([sys.stdin], [], [], 0.1)
                
                # 处理 ESC 超时（孤立的 ESC 键）
                if not dr:
                    if self.buffer == b'\x1b':
                        self._emit('ESC')
                        self.buffer = b""
                    continue

                raw_bytes = os.read(self.fd, 1024)
                for b in raw_bytes:
                    char_byte = bytes([b])
                    
                    # 如果正在处理转义序列，或者是转义序列的开头
                    if self.buffer.startswith(b'\x1b') or char_byte == b'\x1b':
                        self.buffer += char_byte
                        self._process_sequence()
                    else:
                        # 普通字符：直接交给增量解码器，且只传这一个新字节
                        try:
                            char = self.decoder.decode(char_byte, final=False)
                            if char:
                                # 某些单字节控制键可能在这里出现（如回车 \r）
                                key = self.KEY_MAP.get(char, char)
                                self._emit(key)
                        except Exception as e:
                            debug_log(f"[InputHandler] Decode error: {e}")
                            self.decoder.reset()
                            
        except Exception as e:
            debug_log(f"[InputHandler] Global Error: {e}")
        finally:
            self.stop()

    def _process_sequence(self):
        buf = self.buffer
        if len(buf) < 2: return # 只有 \x1b，继续等

        # 处理 CSI 序列 \x1b[...
        if buf.startswith(b'\x1b['):
            if len(buf) > 2:
                last_byte = buf[-1:]
                # 终止符：A-Z, a-z, ~ (如 \x1b[A, \x1b[2J, \x1b[5~)
                if b'A' <= last_byte <= b'Z' or b'a' <= last_byte <= b'z' or last_byte == b'~':
                    seq = buf.decode('ascii', errors='ignore')
                    key = self.KEY_MAP.get(seq, f"SEQ({repr(seq)})")
                    self._emit(key)
                    self.buffer = b""
            return
        
        # 处理 Alt+Key 或其它 \x1b 开头的双字节序列
        if len(buf) >= 2:
            try:
                seq = buf.decode('ascii', errors='ignore')
                self._emit(f"ALT+{repr(seq[1:])}")
            except:
                pass
            self.buffer = b""

    def _emit(self, key):
        if not key: return
        if key == '\x03': # Ctrl+C
            self.engine.is_running = False
            return
            
        with self.engine.lock:
            self.engine.last_key = key
            self.engine.input_events.append(key)

    def stop(self):
        if self.old_settings:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
