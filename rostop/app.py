# rostop主应用程序类
import curses
import rospy
import time
from .views.topic_select_view import TopicSelectView
from .views.topic_display_view import TopicDisplayView # 新增导入
from .views.base_view import BaseView

class App:
    """管理视图和主循环的应用程序主类"""
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.views = [TopicSelectView(stdscr)]
        self.current_view_index = 0
        
        # 初始化颜色配色方案
        self.has_colors = False
        try:
            if curses.has_colors():
                curses.start_color()
                curses.use_default_colors()
                
                # 定义统一配色方案
                curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)     # 标题栏
                curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)    # 选中标签
                curses.init_pair(3, curses.COLOR_RED, -1)                      # 错误信息
                curses.init_pair(4, curses.COLOR_GREEN, -1)                    # 成功信息
                curses.init_pair(5, curses.COLOR_YELLOW, -1)                   # 警告信息
                curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE)     # 信息栏
                curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_CYAN)     # 高亮话题
                curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_GREEN)    # 一级标题
                curses.init_pair(9, curses.COLOR_CYAN, -1)                    # 二级标题
                curses.init_pair(10, curses.COLOR_BLUE, -1)                   # 三级标题
                self.has_colors = True
        except Exception:
            # 颜色初始化失败时使用单色模式
            self.has_colors = False

    def run(self):
        """主程序循环"""
        curses.curs_set(0)
        self.stdscr.nodelay(False) 
        self.stdscr.timeout(10)     # 10ms超时，提高ESC键响应速度
        
        # 跟踪重绘需求
        needs_redraw = True
        last_draw_time = 0
        refresh_interval = 0.05 # 默认刷新间隔 (20Hz)

        while not rospy.is_shutdown():
            # 处理ROS回调
            try:
                rospy.rostime.wallsleep(0.001)
            except rospy.ROSInterruptException:
                break
                
            key = self.stdscr.getch()
            
            # 处理用户输入
            if key == 27:  # ESC键退出
                break
            elif key == curses.KEY_RIGHT:
                self.current_view_index = (self.current_view_index + 1) % len(self.views)
                self._on_view_switch()
                needs_redraw = True
            elif key == curses.KEY_LEFT:
                self.current_view_index = (self.current_view_index - 1 + len(self.views)) % len(self.views)
                self._on_view_switch()
                needs_redraw = True
            elif key != -1:  # 其他有效按键
                current_view = self.views[self.current_view_index]
                result = current_view.handle_input(key)
                
                # 处理关闭选项卡请求
                if result is None and self.current_view_index != 0:
                    view_to_close = self.views[self.current_view_index]
                    view_to_close.close()
                    self.views.pop(self.current_view_index)
                    self.current_view_index = max(0, self.current_view_index - 1)
                    self._on_view_switch() # 切换视图后可能需要调整刷新率
                    needs_redraw = True
                elif isinstance(result, BaseView) and result is not current_view:
                    existing_index = self._find_view(result)
                    if existing_index != -1:
                        self.current_view_index = existing_index
                    else:
                        self.views.append(result)
                        self.current_view_index = len(self.views) - 1
                    self._on_view_switch() # 切换视图后可能需要调整刷新率
                    needs_redraw = True
                else: # 其他按键也可能导致重绘
                    needs_redraw = True


            # 检查当前视图是否需要重绘
            current_view = self.views[self.current_view_index] 
            if hasattr(current_view, 'needs_redraw') and current_view.needs_redraw():
                needs_redraw = True

            # 根据当前视图类型确定刷新间隔
            active_view_for_rate = self.views[self.current_view_index]
            if isinstance(active_view_for_rate, TopicSelectView):
                refresh_interval = 0.05  # 菜单界面 20Hz
            elif isinstance(active_view_for_rate, TopicDisplayView):
                refresh_interval = 0.2   # 数据界面 5Hz
            else:
                refresh_interval = 0.05  # 其他视图默认为 20Hz

            # 控制重绘频率
            current_time = time.time()
            if needs_redraw and (current_time - last_draw_time) > refresh_interval:
                active_view_to_draw = self.views[self.current_view_index]
                active_view_to_draw.draw()
                self.draw_global_tabs()
                self.stdscr.refresh() 
                needs_redraw = False
                last_draw_time = current_time
                # 重置视图重绘标志
                if hasattr(active_view_to_draw, 'clear_redraw_flag'):
                    active_view_to_draw.clear_redraw_flag()

            # 短暂休眠防止过度占用CPU
            # 根据刷新间隔调整休眠时间，但要确保 responsiveness
            # 此处的 time.sleep(0.01) 主要是为了让 getch 有机会响应
            # 实际的绘制间隔由 refresh_interval 控制
            time.sleep(0.01)

    def _on_view_switch(self):
        """视图切换时的处理"""
        new_view = self.views[self.current_view_index]
        # 更新刷新率相关的逻辑已移至主循环
        if isinstance(new_view, TopicSelectView):
            new_view.refresh_topics()
        elif hasattr(new_view, 'refresh_view'):
            new_view.refresh_view()

    def _find_view(self, new_view):
        """查找已存在的视图"""
        if not hasattr(new_view, 'topic_name'): 
            return -1
        for i, view in enumerate(self.views):
            if hasattr(view, 'topic_name') and view.topic_name == new_view.topic_name:
                return i
        return -1

    def draw_global_tabs(self):
        """绘制全局标签栏"""
        height, width = self.stdscr.getmaxyx()
        tabs_y = height - 2
        
        # 清空标签栏并填充背景
        try:
            tab_line = " " * min(width-1, 200)  # 避免写入最后一列
            self.stdscr.addstr(tabs_y, 0, tab_line, curses.A_NORMAL)
        except curses.error:
            return
        
        x_pos = 0
        for i, view in enumerate(self.views):
            if x_pos >= width - 5:
                break
                
            name = "Menu" if isinstance(view, TopicSelectView) else view.get_name()
            tab_text = f" {i}:{name} "
            
            # 确保标签文本不超出屏幕边界
            if x_pos + len(tab_text) >= width:
                max_len = width - x_pos - 1
                tab_text = tab_text[:max_len]
            
            # 为活动标签使用不同样式
            try:
                if i == self.current_view_index:
                    if self.has_colors:
                        style = curses.color_pair(2) | curses.A_BOLD  # 选中标签
                    else:
                        style = curses.A_REVERSE | curses.A_BOLD
                else:
                    if self.has_colors:
                        style = curses.color_pair(6)  # 未选中标签
                    else:
                        style = curses.A_NORMAL
                        
                self.stdscr.addstr(tabs_y, x_pos, tab_text, style)
                x_pos += len(tab_text) + 1
            except curses.error:
                # 绘制失败时尝试无样式绘制
                try:
                    self.stdscr.addstr(tabs_y, x_pos, tab_text)
                    x_pos += len(tab_text) + 1
                except curses.error:
                    break