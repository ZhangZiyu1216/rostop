# 视图基类
import curses

class BaseView:
    """应用程序中所有视图的抽象基类"""
    def __init__(self, stdscr):
        self.stdscr = stdscr

    def handle_input(self, key):
        return self

    def draw(self):
        pass
    
    def get_name(self):
        return self.__class__.__name__

    def close(self):
        """视图关闭时执行清理，由子类重写"""
        pass
    
    def _safe_addstr(self, y, x, text, style=curses.A_NORMAL, fallback_attr=curses.A_NORMAL):
        """安全地添加字符串，处理各种可能的错误"""
        try:
            height, width = self.stdscr.getmaxyx()
            if y >= height or y < 0 or x >= width or x < 0:
                return
            max_len = width - x - 1
            display_text = text[:max_len] if len(text) > max_len else text
            try:
                self.stdscr.addstr(y, x, display_text, style)
            except curses.error:
                try:
                    self.stdscr.addstr(y, x, display_text, fallback_attr)
                except curses.error:
                    debug_text = f"[DEBUG: curses.error in _safe_addstr] {display_text[:width-35]}"
                    self.stdscr.addstr(y, x, debug_text[:width-x])
        except Exception as e:
            try:
                debug_text = f"[DEBUG: Exception in _safe_addstr: {type(e).__name__}]"
                self.stdscr.addstr(y, x, debug_text[:width-x] if width > x else debug_text[:80])
            except:
                pass