import sys
import termios
import tty
import threading
import select
import os
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
        ' ': 'SPACE',
    }

    def __init__(self, engine):
        self.engine = engine
        self.fd = sys.stdin.fileno()
        self.old_settings = None

    def _read_all_available(self):
        """贪婪读取当前缓冲区内所有可用的字符，绝不阻塞"""
        res = ""
        while True:
            # 检查是否有数据可读，超时设为 0
            dr, _, _ = select.select([sys.stdin], [], [], 0)
            if dr:
                res += sys.stdin.read(1)
            else:
                break
        return res

    def listen(self):
        self.old_settings = termios.tcgetattr(self.fd)
        try:
            tty.setraw(self.fd)
            while self.engine.is_running:
                # 阻塞式等待第一个字符输入，避免 CPU 空转
                dr, _, _ = select.select([sys.stdin], [], [], 0.2)
                if not dr:
                    continue

                char = sys.stdin.read(1)
                
                if char == '\x1b':
                    # 读到 ESC 以后，给一个极短的时间（20ms）等待序列后续字节
                    # 这是处理特殊键（方向键、F1等）的标准做法
                    dr_seq, _, _ = select.select([sys.stdin], [], [], 0.02)
                    if dr_seq:
                        # 读走缓冲区里剩下的所有内容
                        remaining = self._read_all_available()
                        seq = char + remaining
                        key = self.KEY_MAP.get(seq, f"SEQ({repr(seq)})")
                    else:
                        key = 'ESC'
                elif char == '\x03':  # Ctrl+C
                    self.engine.is_running = False
                    break
                else:
                    key = self.KEY_MAP.get(char, char)
                
                if key:
                    with self.engine.lock:
                        self.engine.last_key = key
                        self.engine.input_events.append(key)
                        
        except Exception as e:
            debug_log(f"[InputHandler] Error: {e}")
        finally:
            self.stop()

    def stop(self):
        if self.old_settings:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
