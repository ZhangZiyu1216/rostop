# rostop包初始化文件
from .ros_utils.subscription_manager import SubscriptionManager

# 创建全局订阅管理器实例，供整个应用使用
sub_manager = SubscriptionManager()