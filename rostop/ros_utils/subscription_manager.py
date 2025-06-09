# ROS订阅管理器
import rospy
import os
import threading
import yaml
from io import BytesIO
from importlib import import_module
from rospy_message_converter import message_converter
import logging
import subprocess

# 配置日志记录
logger = logging.getLogger('SubscriptionManager')
handler = logging.FileHandler('subscription_manager.log')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

class SubscriptionManager:
    """管理ROS订阅，包括取消订阅功能"""
    def __init__(self, data_size_threshold=10240):
        # 自动加载ROS环境变量
        self._load_ros_environment()
        self.subscribers = {}
        self.callbacks = {}
        self.display_modes = {}
        # 使用RLock避免死锁
        self.lock = threading.RLock()
        self.DATA_SIZE_THRESHOLD = data_size_threshold

    def subscribe(self, topic_name, topic_type, callback, table_width=80):
        """订阅ROS话题并注册回调函数"""
        logger.debug(f"尝试订阅话题 '{topic_name}'，类型为 '{topic_type}'")
        with self.lock:
            if topic_name in self.subscribers:
                if callback not in self.callbacks.get(topic_name, []):
                    self.callbacks[topic_name].append(callback)
                return
            
            self.callbacks[topic_name] = [callback]
            try:
                module_name, class_name = topic_type.split('/')
                logger.debug(f"订阅: 分割话题类型 '{topic_type}' 为模块 '{module_name}', 类 '{class_name}'")
                
                logger.debug(f"订阅: 尝试导入模块 '{module_name}.msg'")
                try:
                    msg_mod = import_module(f"{module_name}.msg")
                    logger.debug(f"订阅: 模块导入成功: {msg_mod}")
                except ModuleNotFoundError:
                    err_text = f"消息包 '{module_name}' 未找到，跳过订阅并显示静态信息。"
                    logger.error(f"订阅: 导入 '{module_name}.msg' 时发生模块未找到错误")
                    self._distribute_error(topic_name, err_text)
                    # 使用线程执行回调，避免阻塞主线程
                    threading.Thread(target=lambda: [cb({'raw': err_text, 'dict': None}) for cb in self.callbacks.get(topic_name, [])]).start()
                    return

                logger.debug(f"订阅: 尝试获取属性 '{class_name}'")
                try:
                    msg_class = getattr(msg_mod, class_name)
                    logger.debug(f"订阅: 获取属性成功，消息类: {msg_class}")
                except AttributeError:
                    err_text = f"包 '{module_name}' 中不支持的消息类 '{class_name}'，跳过订阅并显示静态信息。"
                    logger.error(f"订阅: 属性错误，'{module_name}.msg' 没有属性 '{class_name}'")
                    self._distribute_error(topic_name, err_text)
                    # 使用线程执行回调，避免阻塞主线程
                    threading.Thread(target=lambda: [cb({'raw': err_text, 'dict': None}) for cb in self.callbacks.get(topic_name, [])]).start()
                    return

                # 进行订阅
                logger.debug(f"订阅: 订阅话题 '{topic_name}'，消息类 {msg_class}")
                sub = rospy.Subscriber(topic_name, msg_class, lambda msg: self._on_message(msg, topic_name))
                self.subscribers[topic_name] = sub
                logger.debug(f"成功订阅话题 '{topic_name}'，类型为 {module_name}.msg.{class_name}")
            except Exception as e:
                logger.error(f"订阅话题 '{topic_name}' 类型为 {topic_type} 失败: {e}", exc_info=True)
                # 回退使用AnyMsg
                try:
                    sub = rospy.Subscriber(topic_name, rospy.AnyMsg, lambda msg: self._on_message(msg, topic_name))
                    self.subscribers[topic_name] = sub
                    logger.warning(f"使用AnyMsg回退方式订阅话题 '{topic_name}'")
                    warning = f"警告: 由于错误 {e}，使用AnyMsg方式订阅 {topic_name}"
                    self._distribute_error(topic_name, warning)
                except Exception as e2:
                    logger.error(f"话题 '{topic_name}' 的AnyMsg回退方式失败: {e2}", exc_info=True)
                    error_msg = f"订阅话题 {topic_name} 失败: {e2}"
                    self._distribute_error(topic_name, error_msg)

    def unsubscribe(self, topic_name, callback):
        """移除话题回调并在无回调时注销订阅者"""
        with self.lock:
            if topic_name in self.callbacks:
                # 移除匹配的回调
                if callback in self.callbacks[topic_name]:
                    self.callbacks[topic_name].remove(callback)
                
                # 如果没有更多视图在监听，注销订阅者
                if not self.callbacks[topic_name]:
                    if topic_name in self.subscribers:
                        self.subscribers[topic_name].unregister()
                        del self.subscribers[topic_name]
                    del self.callbacks[topic_name]
                    if topic_name in self.display_modes:
                        del self.display_modes[topic_name]

    def _on_message(self, msg, topic_name):
        """处理接收到的ROS消息"""
        with self.lock:
            if topic_name in self.callbacks:
                for callback in self.callbacks[topic_name]:
                    formatted_data = self._format_message(msg, topic_name)
                    callback(formatted_data)
                    
    def _distribute_error(self, topic_name, error_msg):
        """向话题的所有回调分发错误消息"""
        with self.lock:
            if topic_name in self.callbacks:
                for callback in self.callbacks[topic_name]:
                    callback(error_msg)

    def _get_message_size(self, msg):
        """估算ROS消息大小"""
        try:
            buff = BytesIO()
            msg.serialize(buff)
            return len(buff.getvalue())
        except Exception:
            # 回退方案：基于字符串表示估算大小
            return len(str(msg))

    def _format_message(self, msg, topic_name):
        """格式化ROS消息为清洁可读的文本"""
        try:
            # 尝试使用yaml格式化，失败则回退到字符串表示
            try:
                dict_msg = message_converter.convert_ros_message_to_dictionary(msg)
                yaml_output = yaml.dump(dict_msg, default_flow_style=False, allow_unicode=True, indent=2)
                
                # 返回原始YAML文本和字典，供视图两种展示模式使用
                return {'raw': yaml_output.strip(), 'dict': dict_msg}
            except Exception:
                # yaml格式化失败时返回原始文本
                return {'raw': str(msg).strip(), 'dict': None}
        except Exception as e:
            # 最终回退 - 返回错误文本和原始消息
            error_text = f"格式化消息时出错: {str(e)}\n\n原始消息:\n{str(msg)}"
            return {'raw': error_text, 'dict': None}

    def _load_ros_environment(self):
        """扫描用户home目录下各workspace的devel/setup.bash并source，快速加载环境"""
        scripts = ['/opt/ros/noetic/setup.bash']
        home = os.path.expanduser('~')
        for entry in os.listdir(home):
            script = os.path.join(home, entry, 'devel', 'setup.bash')
            if os.path.isfile(script):
                scripts.append(script)
        # 构造并执行source命令
        cmd = ' && '.join([f'source {s}' for s in scripts] + ['env'])
        try:
            result = subprocess.run(cmd, shell=True, executable='/bin/bash', capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f'Source脚本返回代码 {result.returncode}: {result.stderr.strip()}')
                return
            for line in result.stdout.splitlines():
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k] = v
            logger.info(f'已source脚本: {scripts}')
        except Exception as e:
            logger.error(f'Source setup脚本失败: {e}', exc_info=True)

