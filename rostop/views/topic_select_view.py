# 话题选择视图
import curses
import rospy
from .base_view import BaseView

class TopicSelectView(BaseView):
    """用于从列表中选择ROS话题的视图"""
    def __init__(self, stdscr):
        super().__init__(stdscr)
        self.topics = []  # 原始话题列表: [(name, type), ...]
        self.display_items = []  # 显示项列表
        self.selected_index = 0
        self.scroll_start_index = 0
        # 搜索相关状态
        self.search_text = ""
        self.cursor_in_search = False
        self.filtered_topics = []
        # 展开状态保存
        self.expanded_groups = set()
        self.refresh_topics()

    def refresh_topics(self):
        """刷新话题列表并重新构建显示树"""
        self.topics = sorted(rospy.get_published_topics() or [])
        self._apply_search_filter()
        self._build_display_tree()
        if self.selected_index >= len(self.display_items):
            self.selected_index = max(0, len(self.display_items) - 1)

    def _build_display_tree(self):
        """构建层级显示树"""
        # 构建完整的递归树结构
        self.tree_root = self._build_recursive_tree()
        
        # 将树转换为扁平的显示列表
        self.display_items = []
        self._flatten_tree_to_display_items(self.tree_root, 0)

    def _build_recursive_tree(self):
        """递归构建完整的话题树"""
        tree = {}
        
        # 使用过滤后的话题列表或原始列表
        topics_to_use = self.filtered_topics if self.search_text else self.topics
        
        for topic_name, topic_type in topics_to_use:
            parts = topic_name.strip('/').split('/')
            current_node = tree
            current_path = ""
            
            # 逐级构建路径
            for i, part in enumerate(parts):
                if i == 0:
                    current_path = '/' + part
                else:
                    current_path = current_path + '/' + part
                
                if part not in current_node:
                    if i == len(parts) - 1:
                        # 最后一部分，创建话题节点
                        current_node[part] = {
                            'type': 'topic',
                            'name': part,
                            'full_name': topic_name,
                            'topic_type': topic_type,
                            'path': current_path,
                            'children': {},
                            'expanded': False
                        }
                    else:
                        # 中间路径，创建组节点
                        current_node[part] = {
                            'type': 'group',
                            'name': part,
                            'full_name': current_path,
                            'topic_type': None,
                            'path': current_path,
                            'children': {},
                            'expanded': current_path in self.expanded_groups
                        }
                
                current_node = current_node[part]['children']
        
        return tree

    def _flatten_tree_to_display_items(self, tree_node, level):
        """将树结构扁平化为显示项列表，话题在前，组在后"""
        # 将节点分为两类：组和话题
        groups = []
        topics = []
        
        for name in sorted(tree_node.keys()):
            node = tree_node[name]
            
            # 创建显示项
            display_item = {
                'type': node['type'],
                'name': node['name'],
                'full_name': node['full_name'],
                'topic_type': node.get('topic_type'),
                'level': level,
                'expanded': node.get('expanded', False),
                'children': node['children']
            }
            
            if node['type'] == 'group':
                groups.append((display_item, node))
            else:
                topics.append((display_item, node))
        
        # 首先添加所有话题
        for display_item, node in topics:
            self.display_items.append(display_item)
        
        # 然后添加所有组
        for display_item, node in groups:
            self.display_items.append(display_item)
            
            # 如果组已展开且有子节点，递归添加子项
            if display_item['expanded'] and node['children']:
                self._flatten_tree_to_display_items(node['children'], level + 1)

    def handle_input(self, key):
        # ESC键退出
        if key == 27:
            return self
        
        # 空格键刷新话题列表
        elif key == ord(' '):
            self.refresh_topics()
            return self
        
        # 退格键删除搜索文本
        elif key == curses.KEY_BACKSPACE or key == 127:
            if self.search_text:
                self.search_text = self.search_text[:-1]
                self._update_search_display()
            return self
        
        # 上下方向键导航
        elif key == curses.KEY_UP:
            if self.display_items:
                if self.selected_index > 0:
                    self.selected_index -= 1
                else:
                    self.selected_index = len(self.display_items) - 1
                self.cursor_in_search = False
            return self
        
        elif key == curses.KEY_DOWN:
            if self.display_items:
                if self.selected_index < len(self.display_items) - 1:
                    self.selected_index += 1
                else:
                    self.selected_index = 0
                self.cursor_in_search = False
            return self
        
        # Tab键折叠父组
        elif key == ord('\t'):
            if self.display_items:
                self._collapse_parent_group(self.selected_index)
            return self
        
        # Enter键选择话题或展开/折叠组
        elif key == ord('\n'):
            if self.display_items:
                selected_item = self.display_items[self.selected_index]
                
                if selected_item['type'] == 'group':
                    self._toggle_group_expansion(self.selected_index)
                elif selected_item['type'] == 'topic':
                    try:
                        topic_name = selected_item['full_name']
                        topic_type = selected_item['topic_type']
                        from .topic_display_view import TopicDisplayView
                        return TopicDisplayView(self.stdscr, topic_name, topic_type)
                    except Exception:
                        pass
            return self
        
        # 字符输入（字母、数字、下划线）
        elif 32 <= key <= 126:
            char = chr(key)
            if char.isalnum() or char == '_':
                self.search_text += char
                self._update_search_display()
            return self
        
        else:
            return self

    def _toggle_group_expansion(self, group_index):
        """切换组的展开/折叠状态"""
        group_item = self.display_items[group_index]
        if group_item['type'] != 'group':
            return
            
        selected_item_path = group_item['full_name'] if group_index < len(self.display_items) else None
        
        self._toggle_node_in_tree(self.tree_root, group_item['full_name'])
        
        # 重新构建显示列表
        self.display_items = []
        self._flatten_tree_to_display_items(self.tree_root, 0)
        
        if selected_item_path:
            self._restore_selection_position(selected_item_path)
        
        if self.selected_index >= len(self.display_items):
            self.selected_index = max(0, len(self.display_items) - 1)

    def _toggle_node_in_tree(self, tree_node, target_path):
        """在树中查找并切换指定路径节点的展开状态"""
        for name in tree_node:
            node = tree_node[name]
            if node['full_name'] == target_path:
                node['expanded'] = not node['expanded']
                if node['expanded']:
                    self.expanded_groups.add(target_path)
                else:
                    self.expanded_groups.discard(target_path)
                return True
            elif node['children'] and target_path.startswith(node['full_name']):
                if self._toggle_node_in_tree(node['children'], target_path):
                    return True
        return False

    def _restore_selection_position(self, target_path):
        """恢复选中位置到指定路径"""
        for i, item in enumerate(self.display_items):
            if item['full_name'] == target_path:
                self.selected_index = i
                return

    def _collapse_parent_group(self, current_index):
        """折叠当前选中项所属的父组"""
        if not self.display_items or current_index >= len(self.display_items):
            return
        
        current_item = self.display_items[current_index]
        current_level = current_item['level']
        
        # 如果当前项本身就是展开的组，直接折叠它
        if current_item['type'] == 'group' and current_item['expanded']:
            self._toggle_group_expansion(current_index)
            return
        
        # 如果当前项是顶级项（level 0），无法折叠
        if current_level == 0:
            return
        
        # 向上查找父组（level比当前项小的组）
        parent_level = current_level - 1
        parent_index = -1
        
        # 从当前位置向上搜索
        for i in range(current_index - 1, -1, -1):
            item = self.display_items[i]
            if item['level'] == parent_level and item['type'] == 'group' and item['expanded']:
                parent_index = i
                break
            # 如果遇到level更小的项，说明已经超出了当前分支
            if item['level'] < parent_level:
                break
        
        # 如果找到了展开的父组，折叠它
        if parent_index != -1:
            self._toggle_group_expansion(parent_index)
            # 将选中位置移到刚折叠的父组
            self.selected_index = parent_index

    def draw(self):
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        
        # 绘制标题栏
        title = "rostop - ROS Topic Viewer"
        self._draw_enhanced_title_bar(0, title, 1, curses.A_REVERSE | curses.A_BOLD)
        
        current_row = 1
        
        # 绘制搜索栏
        current_row += 1
        self._draw_search_bar(current_row, width)
        current_row += 1
        
        if not self.display_items:
            if self.search_text:
                no_topics_msg = f"No topics match '{self.search_text}'. (Clear search to see all topics)"
            else:
                no_topics_msg = "No topics found. Is roscore running? (Press 'r' to refresh)"
            self._safe_addstr(current_row + 1, 2, no_topics_msg, 
                             curses.color_pair(4), curses.A_NORMAL)
        else:
            max_items = height - current_row - 3
            if self.selected_index < self.scroll_start_index:
                self.scroll_start_index = self.selected_index
            if self.selected_index >= self.scroll_start_index + max_items:
                self.scroll_start_index = self.selected_index - max_items + 1

            for i, item in enumerate(self.display_items[self.scroll_start_index:self.scroll_start_index + max_items]):
                actual_index = self.scroll_start_index + i
                
                indent = "  " * item['level']
                row = current_row + 1 + i
                col = 2
                
                if actual_index == self.selected_index:
                    base_style = curses.color_pair(7) | curses.A_BOLD
                    base_fallback = curses.A_REVERSE | curses.A_BOLD
                else:
                    base_style = 0
                    base_fallback = curses.A_NORMAL
                
                if item['type'] == 'group':
                    expand_indicator = "v" if item['expanded'] else ">"
                    display_text = f"{indent}{expand_indicator} {item['name']}"
                    display_text = display_text[:width-3]
                    
                    if actual_index == self.selected_index:
                        group_style = curses.color_pair(7) | curses.A_BOLD
                        group_fallback = curses.A_REVERSE | curses.A_BOLD
                    else:
                        group_style = curses.A_BOLD
                        group_fallback = curses.A_BOLD
                    
                    self._safe_addstr(row, col, display_text, group_style, group_fallback)
                else:
                    # 显示话题
                    if item['level'] > 0:
                        topic_name = f"{indent}  {item['name']}"
                    else:
                        topic_name = f"  {item['name']}"
                    
                    topic_type = item['topic_type']
                    
                    available_width = width - col - 2  # 只减去右边距2个空格
                    name_len = len(topic_name)
                    type_len = len(topic_type)
                    
                    if name_len + type_len + 4 <= available_width:
                        fill_len = available_width - name_len - type_len - 2
                        connector = " " + "-" * max(2, fill_len) + " "
                        
                        # 绘制话题名称
                        self._safe_addstr(row, col, topic_name, base_style, base_fallback)
                        
                        # 绘制连接符
                        connector_col = col + name_len
                        if actual_index == self.selected_index:
                            connector_style = curses.color_pair(7)
                            connector_fallback = curses.A_REVERSE
                        else:
                            connector_style = curses.color_pair(5)
                            connector_fallback = curses.A_DIM
                        self._safe_addstr(row, connector_col, connector, connector_style, connector_fallback)
                        
                        # 绘制话题类型
                        type_col = col + name_len + len(connector)
                        if actual_index == self.selected_index:
                            type_style = curses.color_pair(7)
                            type_fallback = curses.A_REVERSE
                        else:
                            type_style = curses.color_pair(4)
                            type_fallback = curses.A_NORMAL
                        self._safe_addstr(row, type_col, topic_type, type_style, type_fallback)
                    else:
                        # 空间不够时截断显示
                        if name_len + 6 < available_width:
                            remaining = available_width - name_len - 4
                            truncated_type = topic_type[:remaining] if remaining > 0 else ""
                            display_text = topic_name + " -- " + truncated_type
                        else:
                            display_text = topic_name[:available_width]
                        self._safe_addstr(row, col, display_text, base_style, base_fallback)

        # 显示帮助栏
        help_text = "Up/Down/Enter: Select  Tab: Collapse  Space: Refresh  Esc: Quit"
        self._draw_enhanced_help_bar(height - 1, help_text, 6, curses.A_REVERSE | curses.A_BOLD)

    def _draw_enhanced_title_bar(self, y, text, color_pair, fallback_attr):
        """绘制增强的标题栏，"rostop"单词加粗显示"""
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
            
            # 计算居中位置
            text_len = len(text)
            if text_len < width:
                start_x = (width - text_len) // 2
                
                # 分析文本，找到"rostop"部分并加粗
                rostop_word = "rostop"
                if rostop_word in text:
                    # 分解文本为三部分：rostop前、rostop、rostop后
                    rostop_pos = text.find(rostop_word)
                    before_rostop = text[:rostop_pos]
                    after_rostop = text[rostop_pos + len(rostop_word):]
                    
                    try:
                        # 绘制rostop前的部分
                        if before_rostop:
                            self.stdscr.addstr(y, start_x, before_rostop, curses.color_pair(color_pair))
                        
                        # 绘制"rostop"（加粗）
                        rostop_x = start_x + len(before_rostop)
                        self.stdscr.addstr(y, rostop_x, rostop_word, curses.color_pair(color_pair) | curses.A_BOLD)
                        
                        # 绘制rostop后的部分
                        if after_rostop:
                            after_x = rostop_x + len(rostop_word)
                            self.stdscr.addstr(y, after_x, after_rostop, curses.color_pair(color_pair))
                            
                    except curses.error:
                        # 如果分段绘制失败，回退到整体绘制
                        self.stdscr.addstr(y, start_x, text, fallback_attr)
                else:
                    # 如果没有找到rostop，正常绘制
                    self.stdscr.addstr(y, start_x, text, curses.color_pair(color_pair))
            else:
                # 文本太长，截断并居中
                truncated = text[:width-1] if y == height - 1 else text[:width]
                self.stdscr.addstr(y, 0, truncated, curses.color_pair(color_pair))
                
        except Exception:
            # 最终回退
            try:
                safe_text = text[:width-1] if y == height - 1 else text[:width]
                self.stdscr.addstr(y, 0, safe_text, fallback_attr)
            except:
                pass

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
            
            # 使用传入的文本而不是硬编码的文本
            enhanced_text = text

            # 计算居中位置
            text_len = len(enhanced_text)
            if text_len < width:
                start_x = (width - text_len) // 2
                # 定义需要加粗的关键字
                keywords = ["Up/Down/Enter:", "Left/Right:", "Tab:", "Space:", "Esc:", "Enter:", "ESC:", "Backspace:"]

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
                keywords = ["Up/Down/Enter:", "Left/Right:", "Tab:", "Space:", "Esc:", "Enter:", "ESC:", "Backspace:"]
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
                # 使用文本的截断版本
                safe_text = text[:available_width]
                
                # 尝试简单的关键词加粗，即使在最终回退中
                keywords = ["Up/Down/Enter:", "Left/Right:", "Tab:", "Space:", "Esc:"]
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
                    # 如果还是失败，至少显示文本
                    safe_text = text[:width-1] if y == height-1 else text[:width]
                    self.stdscr.addstr(y, 0, safe_text)
        except Exception:
            # 如果所有操作都失败，至少尝试显示文本
            try:
                safe_len = width-1 if y == height-1 else width
                safe_text = text[:safe_len] if width > 0 else text[:80]
                self.stdscr.addstr(y, 0, safe_text)
            except:
                pass

    def _safe_addstr(self, y, x, text, style=curses.A_NORMAL, fallback_attr=curses.A_NORMAL):
        """安全地添加字符串，处理各种可能的错误"""
        try:
            height, width = self.stdscr.getmaxyx()
            if y >= height or y < 0 or x >= width or x < 0:
                return
            
            # 截断文本以适应屏幕宽度
            max_len = width - x - 1
            display_text = text[:max_len] if len(text) > max_len else text
            
            # 直接使用传入的样式，而不是分解 color_pair
            try:
                self.stdscr.addstr(y, x, display_text, style)
            except curses.error:
                # 如果颜色样式失败，使用回退样式
                try:
                    self.stdscr.addstr(y, x, display_text, fallback_attr)
                except curses.error:
                    # 如果还是失败，显示调试信息
                    debug_text = f"[DEBUG: curses.error in _safe_addstr] {display_text[:width-35]}"
                    self.stdscr.addstr(y, x, debug_text[:width-x])
        except Exception as e:
            # 如果所有操作都失败，显示异常调试信息
            try:
                debug_text = f"[DEBUG: Exception in _safe_addstr: {type(e).__name__}]"
                self.stdscr.addstr(y, x, debug_text[:width-x] if width > x else debug_text[:80])
            except:
                pass

    def _apply_search_filter(self):
        """根据搜索文本过滤话题列表"""
        if not self.search_text.strip():
            self.filtered_topics = []
            return
        
        # 验证输入的合法性 - 只允许字母、数字、下划线、斜杠和空格
        search_text = self.search_text.strip()
        if not all(c.isalnum() or c in '/_- ' for c in search_text):
            return
        
        # 过滤包含搜索文本的话题（不区分大小写）
        search_lower = search_text.lower()
        self.filtered_topics = [
            (name, topic_type) for name, topic_type in self.topics
            if search_lower in name.lower() or search_lower in topic_type.lower()
        ]

    def _update_search_display(self):
        """更新搜索结果显示"""
        self._apply_search_filter()
        self._build_display_tree()
        # 重置选中索引到搜索结果的开始
        if not self.cursor_in_search:
            self.selected_index = 0
        self.scroll_start_index = 0

    def _draw_search_bar(self, y, width):
        """绘制搜索栏"""
        try:
            height, _ = self.stdscr.getmaxyx()
            if y >= height or y < 0:
                return
            
            # 搜索栏标签
            search_label = "Search: "
            search_display = self.search_text
            
            # 计算显示内容
            max_search_len = width - len(search_label) - 4  # 减去标签长度和边距
            if len(search_display) > max_search_len:
                # 如果搜索文本太长，只显示后面部分
                search_display = "..." + search_display[-(max_search_len-3):]
            
            full_text = search_label + search_display
            
            # 绘制搜索栏背景
            try:
                empty_line = " " * (width - 1)
                self.stdscr.addstr(y, 0, empty_line, curses.A_NORMAL)
            except curses.error:
                pass
            
            # 绘制搜索内容
            try:
                # 绘制 "Search:" 标签（加粗）
                self.stdscr.addstr(y, 2, search_label, curses.A_BOLD)
                
                # 绘制搜索文本（普通样式）
                self.stdscr.addstr(y, 2 + len(search_label), search_display, curses.A_NORMAL)
                
            except curses.error:
                # 如果绘制失败，尝试简单版本
                try:
                    simple_text = full_text[:width-3]
                    self.stdscr.addstr(y, 2, simple_text, curses.A_NORMAL)
                except curses.error:
                    pass
                    
        except Exception:
            # 如果所有操作都失败，忽略这次绘制
            pass