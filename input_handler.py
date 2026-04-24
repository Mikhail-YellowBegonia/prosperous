import sys
import os
import termios
import tty
import threading
import select
import codecs
from utils import debug_log


class InputHandler:
    # 核心映射表
    KEY_MAP = {
        "\x1b[A": "UP",
        "\x1b[B": "DOWN",
        "\x1b[C": "RIGHT",
        "\x1b[D": "LEFT",
        "\r": "ENTER",
        "\n": "ENTER",
        "\x1b": "ESC",
        "\x7f": "BACKSPACE",
        "\t": "TAB",
        " ": "SPACE",
    }

    CONTROL_KEYS = {"UP", "DOWN", "LEFT", "RIGHT", "ENTER", "ESC", "BACKSPACE", "TAB", "SPACE"}

    def __init__(self, engine):
        self.engine = engine
        self.fd = sys.stdin.fileno()
        self.old_settings = None
        # 使用替换模式处理无法解码的字节
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.buffer = b""

    def listen(self):
        self.old_settings = termios.tcgetattr(self.fd)
        try:
            tty.setraw(self.fd)
            while self.engine.is_running:
                dr, _, _ = select.select([sys.stdin], [], [], 0.1)

                # 处理 ESC 超时：清理孤立 ESC 或无法完成的 CSI 序列
                if not dr:
                    if self.buffer == b"\x1b":
                        self._emit("ESC")
                        self.buffer = b""
                    elif self.buffer.startswith(b"\x1b") and len(self.buffer) >= 2:
                        debug_log(
                            f"[InputHandler] Discarding stale escape sequence: {self.buffer!r}"
                        )
                        self.buffer = b""
                    continue

                raw_bytes = os.read(self.fd, 1024)
                for b in raw_bytes:
                    char_byte = bytes([b])

                    if self.buffer.startswith(b"\x1b") or char_byte == b"\x1b":
                        self.buffer += char_byte
                        self._process_sequence()
                    else:
                        try:
                            char = self.decoder.decode(char_byte, final=False)
                            if char:
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
        if len(buf) < 2:
            return

        if buf.startswith(b"\x1b["):
            if len(buf) > 2:
                last_byte = buf[-1:]
                if b"A" <= last_byte <= b"Z" or b"a" <= last_byte <= b"z" or last_byte == b"~":
                    seq = buf.decode("ascii", errors="ignore")
                    key = self.KEY_MAP.get(seq, f"SEQ({repr(seq)})")
                    self._emit(key)
                    self.buffer = b""
            return

        if len(buf) >= 2:
            try:
                seq = buf.decode("ascii", errors="ignore")
                self._emit(f"ALT+{repr(seq[1:])}")
            except:
                pass
            self.buffer = b""

    def _emit(self, key):
        if not key:
            return
        if key == "\x03":  # Ctrl+C
            self.engine.is_running = False
            return

        with self.engine.lock:
            self.engine.last_key = key
            self.engine.input_events.append(key)

    def stop(self):
        if self.old_settings:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
