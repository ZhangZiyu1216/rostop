# rostop/views/topic_display_view.py
import curses
import threading
import time
import re
from .base_view import BaseView
from .. import sub_manager
from ..ros_utils.message_formatter import enhance_display

class TopicDisplayView(BaseView):
    """ROS话题数据显示视图"""
    def __init__(self, stdscr, topic_name, topic_type):
        super().__init__(stdscr)
        self.topic_name = topic_name
        self.topic_type = topic_type
        self.formatted_data = {'raw': f""">>> ROSTOP TOPIC VIEWER <<<\nSTATUS: Waiting for ROS messages...\n\n[Initial content - will be updated when messages arrive]""", 'dict': None}
        self.lock = threading.Lock()
        self.scroll_pos = 0
        self._needs_redraw = True
        self.enhanced_mode = True
        # 动态字段宽度字典
        self.dynamic_field_widths = {} 
        # 用于计算频率
        self.message_count = 0
        self.last_message_time = time.time()
        self.current_frequency = 0.0

        # 订阅ROS话题
        sub_manager.subscribe(self.topic_name, self.topic_type, self._update_data)

    def _update_data(self, formatted_data):
        """ROS消息回调函数"""
        with self.lock:
            was_at_top = (self.scroll_pos == 0)
            self.formatted_data = formatted_data
            # 在顶部时保持显示最新内容，其他位置保持不变
            if was_at_top:
                self.scroll_pos = 0
            self._needs_redraw = True
            
            # 更新频率计算
            self.message_count += 1
            current_time = time.time()
            time_diff = current_time - self.last_message_time
            if time_diff >= 1.0: # 每秒更新一次频率
                self.current_frequency = self.message_count / time_diff
                self.message_count = 0
                self.last_message_time = current_time

    def handle_input(self, key):
        """处理用户输入"""
        # ESC键退出
        if key == 27:
            return self
        
        # 空格键关闭当前选项卡
        elif key == ord(' '):
            return None
        
        # 上下方向键滚动
        elif key == curses.KEY_UP:
            old_pos = self.scroll_pos
            self.scroll_pos = max(0, self.scroll_pos - 1)
            if old_pos != self.scroll_pos:
                self._needs_redraw = True
            return self
        
        elif key == curses.KEY_DOWN:
            old_pos = self.scroll_pos
            self.scroll_pos += 1
            if old_pos != self.scroll_pos:
                self._needs_redraw = True
            return self
        
        else:
            # Tab键切换原始/增强显示模式
            if key == ord('\t'):
                self.enhanced_mode = not self.enhanced_mode
                self._needs_redraw = True
            return self

    def draw(self):
        """绘制视图内容"""
        height, width = self.stdscr.getmaxyx()

        # 绘制标题栏
        self._draw_title_bar(0)

        # 绘制频率信息行
        self._draw_frequency_info(1)
        
        # 准备显示内容
        with self.lock:
            data = self.formatted_data
        
        # 调整可用高度：总高度 - 标题行(1) - 频率行(1) - 全局标签栏(1) - 帮助栏(1) = height - 4
        available_height = height - 4
        
        # 根据模式生成要显示的文本
        # 清理内容区域 (从第2行到帮助栏上方一行)
        # 内容区域为第2行到 height-3 行 (因为 height-2 是全局tab, height-1 是help)
        for r in range(2, height - 2): 
            try:
                self.stdscr.move(r, 0)
                self.stdscr.clrtoeol()
            except curses.error:
                pass # 忽略边界错误

        if self.enhanced_mode and data.get('dict'):
            text = enhance_display(data['dict'], width - 4, available_height, self.dynamic_field_widths)
        else:
            text = data.get('raw', '')
        if text:
            display_lines = text.splitlines()
        else:
            display_lines = ["(No data available)"]
        
        # 调整滚动位置
        max_scroll = max(0, len(display_lines) - available_height)
        self.scroll_pos = max(0, min(self.scroll_pos, max_scroll))
        
        # 显示内容行
        try:
            for i in range(available_height):
                line_index = self.scroll_pos + i
                if line_index < len(display_lines):
                    raw_line = display_lines[line_index]
                    max_w = width - 4
                    disp = raw_line[:max_w] if len(raw_line) > max_w else raw_line
                    # 内容从标题栏和频率行下方开始，即第2行
                    row = i + 2 
                    col = 2
                    if self.enhanced_mode and data.get('dict'):
                        # 跳过空行
                        if disp.strip() == '':
                            continue
                        # 计算缩进层级
                        indent_len = len(disp) - len(disp.lstrip(' '))
                        level = min(indent_len // 2, 2)
                        # 顶级标题行（分隔线样式）
                        if level == 0 and disp.strip().endswith(':'):
                            key = disp.rstrip(':')
                            max_w = width - 4
                            dash_count = max(0, max_w - len(key))
                            line = key + '─' * dash_count
                            self._safe_addstr(row, col, line, curses.color_pair(4) | curses.A_BOLD)
                            continue
                        # 顶级键值对
                        if level == 0:
                            last = 0
                            for m in re.finditer(r'[^:\s]+:', disp):
                                s, e = m.span()
                                if s > last:
                                    self._safe_addstr(row, col + last, disp[last:s])
                                self._safe_addstr(row, col + s, disp[s:e], curses.color_pair(4) | curses.A_BOLD)
                                last = e
                            if last < len(disp):
                                self._safe_addstr(row, col + last, disp[last:])
                            continue
                        # 二级及以上层级
                        indent_count = indent_len // 2
                        prefix_x = col
                        for i in range(indent_count):
                            bar_color = curses.color_pair(4) if i == 0 else curses.color_pair(9)
                            self._safe_addstr(row, prefix_x, '│ ', bar_color)
                            prefix_x += 2
                        stripped = disp.lstrip(' ')
                        cp = curses.color_pair(9) | curses.A_BOLD if level == 1 else curses.color_pair(10) | curses.A_BOLD
                        last_end = 0
                        for m in re.finditer(r'[^:\s]+:', stripped):
                            s, e = m.span()
                            if s > last_end:
                                self._safe_addstr(row, prefix_x + last_end, stripped[last_end:s])
                            self._safe_addstr(row, prefix_x + s, stripped[s:e], cp)
                            last_end = e
                        if last_end < len(stripped):
                            self._safe_addstr(row, prefix_x + last_end, stripped[last_end:])
                        continue
                    # 默认显示
                    self._safe_addstr(row, col, disp)
        except Exception as e:
            self._safe_addstr(4, 2, "Display error - content may be too large", 3, curses.A_BOLD)

        # 显示帮助栏
        help_text = "Up/Down: Scroll  Tab: Toggle Raw/Enhanced  Space: Close Tab  Esc: Quit"
        self._draw_enhanced_help_bar(height - 1, help_text, 6, curses.A_REVERSE | curses.A_BOLD)
        
        # 标记更新完成，用于批处理刷新
        self.stdscr.noutrefresh()

    def _draw_frequency_info(self, y):
        """绘制消息频率信息行"""
        try:
            height, width = self.stdscr.getmaxyx()
            if y >= height or y < 0:
                return

            # 1. 清空指定行，使其恢复到终端默认背景
            self.stdscr.move(y, 0)
            self.stdscr.clrtoeol()

            hz_label_part = "Hz: "  # "Hz: " 部分，包括冒号后的空格
            freq_value_part = f"{self.current_frequency:.2f}"
            
            # 样式定义：白色字体，蓝色背景
            normal_style_on_blue = curses.A_NORMAL
            bold_style_on_blue = curses.A_BOLD
            if curses.has_colors():
                normal_style_on_blue = curses.color_pair(1)  # curses.color_pair(1) 是白字蓝底
                bold_style_on_blue = curses.color_pair(1) | curses.A_BOLD

            # 对齐： H of "Hz:" 在第1列, 与 Topic: 的 T 对齐
            # 因此，Hz: 前面的空格 (在第0列) 也需要蓝色背景

            # 2. 在第0列绘制一个空格，使用蓝色背景
            self._safe_addstr(y, 0, " ", normal_style_on_blue)

            # 3. 在第1列开始绘制 "Hz: " (加粗, 蓝色背景)
            col_for_hz_label = 1
            self._safe_addstr(y, col_for_hz_label, hz_label_part, bold_style_on_blue)
            
            # 4. 绘制频率数字 (普通, 蓝色背景)
            col_for_freq_value = col_for_hz_label + len(hz_label_part)
            self._safe_addstr(y, col_for_freq_value, freq_value_part, normal_style_on_blue)

            # 5. 在数字后绘制一个空格 (普通, 蓝色背景)，作为衬垫
            col_for_trailing_space = col_for_freq_value + len(freq_value_part)
            if col_for_trailing_space < width - 1: # 确保有空间绘制
                 self._safe_addstr(y, col_for_trailing_space, " ", normal_style_on_blue)

        except curses.error:
            try:
                self.stdscr.move(y, 0)
                self.stdscr.clrtoeol()
                self.stdscr.addstr(y, 1, f"Hz: {self.current_frequency:.2f} (display error)")
            except curses.error:
                pass # 再次失败则忽略

    def _draw_title_bar(self, y):
        """绘制标题栏"""
        try:
            height, width = self.stdscr.getmaxyx()
            if y >= height or y < 0:
                return
            
            # 清空整行设置背景色
            try:
                empty_line = " " * width
                if y == height - 1:
                    empty_line = empty_line[:width-1]
                self.stdscr.addstr(y, 0, empty_line, curses.color_pair(1))
            except curses.error:
                pass
            
            # 构建左右两侧内容
            topic_label = "Topic:"
            left_content = f" {topic_label} {self.topic_name}"
            
            type_label = "Type:"
            right_content = f"{type_label} {self.topic_type} "
            
            # 计算可用空间
            total_needed = len(left_content) + len(right_content)
            if total_needed >= width:
                # 空间不足时截断
                available_for_names = width - len(f" {topic_label} ") - len(f"{type_label} ")
                if available_for_names > 10:
                    name_space = available_for_names * 2 // 3
                    type_space = available_for_names - name_space
                    
                    truncated_name = self.topic_name[:name_space-3] + "..." if len(self.topic_name) > name_space else self.topic_name
                    truncated_type = self.topic_type[:type_space-3] + "..." if len(self.topic_type) > type_space else self.topic_type
                    
                    left_content = f" {topic_label} {truncated_name}"
                    right_content = f"{type_label} {truncated_type} "
                else:
                    left_content = f" {topic_label} ..."
                    right_content = f"{type_label} ... "
            
            # 绘制左侧内容
            try:
                col = 1
                # 绘制标签（加粗）
                self.stdscr.addstr(y, col, topic_label, curses.color_pair(1) | curses.A_BOLD)
                col += len(topic_label)
                
                # 绘制话题名称
                topic_name_text = f" {left_content[len(f' {topic_label}'):].strip()}"
                max_name_width = width - col - len(right_content) - 2
                if len(topic_name_text) > max_name_width:
                    topic_name_text = topic_name_text[:max_name_width-3] + "..."
                
                self.stdscr.addstr(y, col, topic_name_text, curses.color_pair(1))
                
            except curses.error:
                pass
            
            # 绘制右侧内容
            try:
                right_start = width - len(right_content)
                if right_start > len(left_content):
                    type_start = right_start
                    self.stdscr.addstr(y, type_start, type_label, curses.color_pair(1) | curses.A_BOLD)
                    
                    type_name_text = f" {right_content[len(type_label):].strip()}"
                    self.stdscr.addstr(y, type_start + len(type_label), type_name_text, curses.color_pair(1))
                    
            except curses.error:
                pass
                    
        except Exception:
            # 显示简单标题
            try:
                simple_title = f" Topic: {self.topic_name} "
                simple_title = simple_title.center(width)[:width-1] if y == height - 1 else simple_title.center(width)[:width]
                self.stdscr.addstr(y, 0, simple_title, curses.A_REVERSE)
            except:
                pass

    def _draw_colored_bar(self, y, text, color_pair, fallback_attr):
        """安全地绘制带颜色的整行条，可以在最后一行绘制"""
        try:
            height, width = self.stdscr.getmaxyx()
            if y >= height or y < 0:
                return
            
            # 创建居中的文本行，两边用空格填充到整行宽度
            text_len = len(text)
            if text_len >= width:
                # 如果文本太长，截断它
                centered_line = text[:width]
            else:
                # 计算左右空格数量来居中文本
                left_spaces = (width - text_len) // 2
                right_spaces = width - text_len - left_spaces
                centered_line = " " * left_spaces + text + " " * right_spaces
            
            # 如果是最后一行，避免写入最后一个字符以防止滚动
            if y == height - 1:
                centered_line = centered_line[:width-1]  # 不写最后一个字符
            else:
                centered_line = centered_line[:width]
            
            try:
                # 一次性绘制整行，包含背景色和文字
                self.stdscr.addstr(y, 0, centered_line, curses.color_pair(color_pair))
                
                # 如果是最后一行，单独处理最后一个字符
                if y == height - 1 and len(centered_line) == width - 1:
                    try:
                        # 使用 insstr 在最后位置插入字符，避免光标移动到下一行
                        self.stdscr.insstr(y, width-1, " ", curses.color_pair(color_pair))
                    except curses.error:
                        pass  # 如果失败就跳过最后一个字符
                        
            except curses.error:
                # 回退到默认样式
                try:
                    self.stdscr.addstr(y, 0, centered_line, fallback_attr)
                    if y == height - 1 and len(centered_line) == width - 1:
                        try:
                            self.stdscr.insstr(y, width-1, " ", fallback_attr)
                        except curses.error:
                            pass
                except curses.error:
                    # 如果還是失败，至少显示文本
                    safe_text = text[:width-1] if y == height-1 else text[:width]
                    self.stdscr.addstr(y, 0, safe_text)
        except Exception:
            # 如果所有操作都失败，至少尝试显示文本
            try:
                safe_len = width-1 if y == height - 1 else width
                safe_text = text[:safe_len] if width > 0 else text[:80]
                self.stdscr.addstr(y, 0, safe_text)
            except:
                pass

    def get_name(self):
        """获取视图显示名称"""
        parts = self.topic_name.split('/')
        # 返回最后一个非空部分
        return next((part for part in reversed(parts) if part), self.topic_name)

    def close(self):
        """关闭视图时取消订阅"""
        sub_manager.unsubscribe(self.topic_name, self._update_data)

    def refresh_view(self):
        """当视图变为活动状态时调用 - 重置滚动以显示最新内容"""
        with self.lock:
            self.scroll_pos = 0
            self._needs_redraw = True

    def needs_redraw(self):
        """检查是否需要重绘"""
        return self._needs_redraw
    
    def clear_redraw_flag(self):
        """清除重绘标志"""
        self._needs_redraw = False

    def _draw_enhanced_help_bar(self, y, text, color_pair, fallback_attr):
        """绘制增强的帮助栏，关键字加粗显示，并增加间距"""
        try:
            height, width = self.stdscr.getmaxyx()
            if y >= height or y < 0:
                return
            
            # 首先清空整行，设置背景色
            try:
                empty_line = " " * width
                if y == height - 1:  # 最后一行特殊处理
                    empty_line = empty_line[:width-1]
                self.stdscr.addstr(y, 0, empty_line, curses.color_pair(color_pair))
            except curses.error:
                pass
            # 重新构建帮助文本，增加间距
            enhanced_text = "Up/Down: Scroll  ·  Left/Right: Switch  ·  Space: Close Tab  ·  Esc: Quit" 

            # 计算居中位置
            text_len = len(enhanced_text)
            if text_len < width:
                start_x = (width - text_len) // 2
                # 定义需要加粗的关键字
                keywords = ["Up/Down:", "Left/Right:", "Space:", "Esc:"]

                try:
                    # 逐段绘制文本，对关键字加粗
                    current_x = start_x
                    remaining_text = enhanced_text
                    
                    while remaining_text and current_x < width - 1:
                        # 检查是否有关键字在当前位置
                        found_keyword = None
                        for keyword in keywords:
                            if remaining_text.startswith(keyword):
                                found_keyword = keyword
                                break
                        
                        if found_keyword:
                            # 绘制关键字（加粗）
                            self.stdscr.addstr(y, current_x, found_keyword, curses.color_pair(color_pair) | curses.A_BOLD)
                            current_x += len(found_keyword)
                            remaining_text = remaining_text[len(found_keyword):]
                        else:
                            # 找到下一个关键字之前的普通文本
                            next_keyword_pos = len(remaining_text)
                            for keyword in keywords:
                                pos = remaining_text.find(keyword)
                                if pos != -1 and pos < next_keyword_pos:
                                    next_keyword_pos = pos
                            
                            # 绘制普通文本
                            normal_text = remaining_text[:next_keyword_pos]
                            if normal_text:
                                self.stdscr.addstr(y, current_x, normal_text, curses.color_pair(color_pair))
                                current_x += len(normal_text)
                                remaining_text = remaining_text[len(normal_text):]
                            else:
                                # 如果没找到更多关键字，绘制剩余文本
                                self.stdscr.addstr(y, current_x, remaining_text, curses.color_pair(color_pair))
                                break
                                
                except curses.error:
                    # 如果分段绘制失败，回退到整体绘制
                    try:
                        safe_text = enhanced_text[:width-1] if y == height - 1 else enhanced_text[:width]
                        self.stdscr.addstr(y, start_x, safe_text, fallback_attr)
                    except:
                        pass
            else:
                # 文本太长，截断并在安全模式下应用关键词加粗
                available_width = width - 1 if y == height - 1 else width
                
                # 使用增强文本而不是原始文本，并应用关键词高亮
                keywords = ["Up/Down:", "Left/Right:", "Space:", "Esc:"]
                safe_text = enhanced_text[:available_width]
                
                try:
                    # 在安全模式下也应用关键词加粗
                    current_x = 0
                    remaining_text = safe_text
                    
                    while remaining_text and current_x < available_width:
                        # 检查是否有关键字在当前位置
                        found_keyword = None
                        for keyword in keywords:
                            if remaining_text.startswith(keyword):
                                found_keyword = keyword
                                break
                        
                        if found_keyword:
                            # 绘制关键字（加粗）
                            if current_x + len(found_keyword) <= available_width:
                                self.stdscr.addstr(y, current_x, found_keyword, curses.color_pair(color_pair) | curses.A_BOLD)
                                current_x += len(found_keyword)
                                remaining_text = remaining_text[len(found_keyword):]
                            else:
                                # 关键词被截断，绘制能显示的部分
                                partial_keyword = found_keyword[:available_width - current_x]
                                self.stdscr.addstr(y, current_x, partial_keyword, curses.color_pair(color_pair) | curses.A_BOLD)
                                break
                        else:
                            # 找到下一个关键字之前的普通文本
                            next_keyword_pos = len(remaining_text)
                            for keyword in keywords:
                                pos = remaining_text.find(keyword)
                                if pos != -1 and pos < next_keyword_pos:
                                    next_keyword_pos = pos
                            
                            # 绘制普通文本
                            normal_text = remaining_text[:next_keyword_pos]
                            if normal_text:
                                display_len = min(len(normal_text), available_width - current_x)
                                if display_len > 0:
                                    self.stdscr.addstr(y, current_x, normal_text[:display_len], curses.color_pair(color_pair))
                                    current_x += display_len
                                    remaining_text = remaining_text[display_len:]
                                else:
                                    break
                            else:
                                # 如果没找到更多关键字，绘制剩余文本
                                display_len = min(len(remaining_text), available_width - current_x)
                                if display_len > 0:
                                    self.stdscr.addstr(y, current_x, remaining_text[:display_len], curses.color_pair(color_pair))
                                break
                                
                except curses.error:
                    # 如果关键词绘制失败，回退到简单截断
                    try:
                        self.stdscr.addstr(y, 0, safe_text, fallback_attr)
                    except:
                        pass
                
        except Exception:
            # 最终回退 - 即使在最终回退中也尝试应用关键词加粗
            try:
                available_width = width - 1 if y == height - 1 else width
                # 使用增强文本的截断版本
                safe_text = enhanced_text[:available_width] if 'enhanced_text' in locals() else text[:available_width]
                
                # 尝试简单的关键词加粗，即使在最终回退中
                keywords = ["Up/Down:", "Left/Right:", "Space:", "Esc:"]
                current_x = 0
                remaining_text = safe_text
                
                for keyword in keywords:
                    if keyword in remaining_text:
                        pos = remaining_text.find(keyword)
                        if pos >= 0:
                            # 绘制关键词前的文本
                            if pos > 0:
                                before_text = remaining_text[:pos]
                                self.stdscr.addstr(y, current_x, before_text, fallback_attr)
                                current_x += len(before_text)
                            
                            # 绘制关键词（加粗）
                            if current_x + len(keyword) <= available_width:
                                self.stdscr.addstr(y, current_x, keyword, fallback_attr | curses.A_BOLD)
                                current_x += len(keyword)
                                remaining_text = remaining_text[pos + len(keyword):]
                            else:
                                break
                
                # 绘制剩余文本
                if remaining_text and current_x < available_width:
                    remaining_len = min(len(remaining_text), available_width - current_x)
                    self.stdscr.addstr(y, current_x, remaining_text[:remaining_len], fallback_attr)
                    
            except:
                # 如果所有尝试都失败，显示基本文本
                try:
                    basic_text = text[:width-1] if y == height - 1 else text[:width]
                    self.stdscr.addstr(y, 0, basic_text, fallback_attr)
                except:
                    pass