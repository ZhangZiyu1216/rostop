# ROS消息格式化工具
import textwrap
import re

# 路径元组，用作动态字段宽度的键，由字符串化的字典键和整数列表索引构造
# 应始终是可哈希的，例如: ('parent_key', 0, 'child_key')

def format_number_core(value, precision=8):
    """
    将数字格式化为字符串
    - 有效零浮点数(abs(value) < 1e-8)表示为"0"
    - 其他浮点数格式化为'precision'位小数，保留小数部分的尾随零
    - 整数和其他类型按之前的方式转换为字符串
    """
    if isinstance(value, float):
        if abs(value) < 1e-8:  # 被认为是零的阈值
            s_value = "0"
        else:
            # 对于非有效零浮点数，格式化为'precision'位小数
            # 保留小数部分的尾随零以确保稳定长度
            s_value = f"{value:.{precision}f}"
    elif isinstance(value, int):
        s_value = str(value)
    else: # bool, string等
        s_value = str(value)
    return s_value

def format_value_for_display(value_str_core, field_width, is_numeric):
    """
    在固定field_width内格式化预格式化的核心字符串值以供显示
    """
    current_len = len(value_str_core)
    s_value = value_str_core

    if current_len > field_width:
        if is_numeric:
            if s_value.startswith('-') and field_width > 2:
                s_value = "-" + "…" + s_value[-(field_width - 2):]
            elif field_width > 1:
                s_value = "…" + s_value[-(field_width - 1):]
            elif field_width == 1:
                s_value = "…"
            else: 
                s_value = ""
        else:  
            if field_width > 1:
                s_value = s_value[:field_width - 1] + "…"
            elif field_width == 1:
                s_value = "…"
            else: 
                s_value = ""
    elif current_len < field_width:
        if is_numeric:  
            s_value = ' ' * (field_width - current_len) + s_value
        else:  
            s_value = s_value + ' ' * (field_width - current_len)
    
    return s_value

def enhance_display(dict_msg, width, height, dynamic_field_widths):
    """
    格式化字典消息以供增强显示
    - 使用动态字段宽度格式化值
    """
    lines = []
    base_path = () 

    # 确保dict_msg的键早期字符串化以用于路径构造
    simple_root = [(str(k), v) for k, v in dict_msg.items() if not isinstance(v, (dict, list))]
    complex_root = [(str(k), v) for k, v in dict_msg.items() if isinstance(v, (dict, list))]

    if simple_root:
        cur_line_str = ''
        for k_str, v_orig in simple_root: # k_str现在确定是字符串
            item_path = base_path + (k_str,) # 路径是字符串/整数的元组
            is_numeric = isinstance(v_orig, (int, float))
            
            v_core_str = format_number_core(v_orig, precision=8)
            current_natural_len = len(v_core_str)
            
            max_len_for_key = max(dynamic_field_widths.get(item_path, 1), current_natural_len)
            dynamic_field_widths[item_path] = max_len_for_key
            
            v_formatted_display = format_value_for_display(v_core_str, max_len_for_key, is_numeric)
            
            segment = f"{k_str}: {v_formatted_display}"
            separator = '   ' if cur_line_str else ''
            if len(cur_line_str) + len(separator + segment) <= width:
                cur_line_str += separator + segment
            else:
                if cur_line_str: 
                    lines.append(cur_line_str)
                cur_line_str = segment 
        if cur_line_str: 
            lines.append(cur_line_str)
        
        if complex_root and lines and (lines[-1] if lines else '').strip():
            lines.append('')

    def recurse(obj, indent, level, current_path_tuple):
        if isinstance(obj, dict):
            simple_kv_pairs = []
            complex_items = []

            # 分类处理字典项
            for k, v_orig in obj.items():
                k_str = str(k)
                item_path = current_path_tuple + (k_str,)
                is_numeric_val = isinstance(v_orig, (int, float))

                if isinstance(v_orig, (dict, list)):
                    complex_items.append((k_str, v_orig, item_path)) 
                else:
                    v_core_str = format_number_core(v_orig, precision=8)
                    current_natural_len = len(v_core_str)
                    
                    max_len_for_key = max(dynamic_field_widths.get(item_path, 1), current_natural_len)
                    dynamic_field_widths[item_path] = max_len_for_key
                    
                    formatted_v_display = format_value_for_display(v_core_str, max_len_for_key, is_numeric_val)
                    simple_kv_pairs.append((k_str, formatted_v_display))
            
            # 处理简单键值对
            if simple_kv_pairs:
                current_line_segments_str = ""
                for k_str_display, v_str_display in simple_kv_pairs:
                    segment = f"{k_str_display}: {v_str_display}"
                    separator = "  " if current_line_segments_str else ""
                    
                    if len(' ' * indent + current_line_segments_str + separator + segment) <= width:
                        current_line_segments_str += separator + segment
                    else:
                        if current_line_segments_str:
                            lines.append(' ' * indent + current_line_segments_str)
                        current_line_segments_str = segment
                
                if current_line_segments_str:
                    lines.append(' ' * indent + current_line_segments_str)

            # 处理复杂项
            for complex_item_index, (k_str_complex, v_orig_nested, item_path_for_nested) in enumerate(complex_items): 
                # 在顶级复杂项之间添加空行
                if level == 0 and complex_item_index > 0:
                    if lines and lines[-1].strip():
                        lines.append('')

                lines.append(' ' * indent + f"{k_str_complex}:")
                recurse(v_orig_nested, indent + 2, level + 1, item_path_for_nested)

        elif isinstance(obj, list):
            is_simple_list = all(not isinstance(i, (dict, list)) for i in obj)

            if is_simple_list:
                formatted_items_display = []
                for idx, list_item_orig in enumerate(obj):
                    item_path = current_path_tuple + (idx,)
                    is_numeric_item = isinstance(list_item_orig, (int, float))

                    item_core_str = format_number_core(list_item_orig, precision=8)
                    current_natural_len = len(item_core_str)

                    max_len_for_key = max(dynamic_field_widths.get(item_path, 1), current_natural_len)
                    dynamic_field_widths[item_path] = max_len_for_key
                    
                    formatted_display_item = format_value_for_display(item_core_str, max_len_for_key, is_numeric_item)
                    formatted_items_display.append(formatted_display_item)
                
                if not formatted_items_display:
                    lines.append(' ' * indent + '[]')
                    return

                current_line_content = '['
                first_item_on_this_line = True

                for idx, item_s_display in enumerate(formatted_items_display):
                    part_to_add = ""
                    if not first_item_on_this_line:
                        part_to_add += ", "
                    part_to_add += item_s_display
                    
                    if len(' ' * indent + current_line_content + part_to_add) + 1 <= width : 
                        current_line_content += part_to_add
                        first_item_on_this_line = False
                    else:
                        if current_line_content.endswith(", "):
                             current_line_content = current_line_content[:-2]
                        lines.append(' ' * indent + current_line_content + ']')
                        current_line_content = '[' + item_s_display 
                        first_item_on_this_line = False
                
                if current_line_content.endswith(", "):
                    current_line_content = current_line_content[:-2]
                lines.append(' ' * indent + current_line_content + ']')

            else:  
                for idx, item_orig in enumerate(obj):
                    item_path_for_list_item = current_path_tuple + (idx,) 
                    lines.append(' ' * indent + '-') 
                    recurse(item_orig, indent + 2, level + 1, item_path_for_list_item) 
        else:  
            # 处理基本类型值
            is_numeric_obj = isinstance(obj, (int, float))
            obj_core_str = format_number_core(obj, precision=8)
            current_natural_len = len(obj_core_str)
            
            max_len_for_key = max(dynamic_field_widths.get(current_path_tuple, 1), current_natural_len)
            dynamic_field_widths[current_path_tuple] = max_len_for_key

            formatted_obj_display = format_value_for_display(obj_core_str, max_len_for_key, is_numeric_obj)
            lines.append(' ' * indent + formatted_obj_display)

    # 初始调用递归处理
    if complex_root:
        recurse({k_str: v for k_str, v in complex_root}, indent=0, level=0, current_path_tuple=base_path) 
    
    # 清理最终输出
    final_lines = []
    if lines:
        first_content_idx = 0
        while first_content_idx < len(lines) and not lines[first_content_idx].strip():
            first_content_idx += 1
        
        if first_content_idx < len(lines):
            final_lines.append(lines[first_content_idx])
            for i in range(first_content_idx + 1, len(lines)):
                if lines[i].strip() or (final_lines[-1] if final_lines else '').strip():
                    final_lines.append(lines[i])
        
        while final_lines and not (final_lines[-1] if final_lines else '').strip():
            final_lines.pop()
            
    return "\n".join(final_lines)
