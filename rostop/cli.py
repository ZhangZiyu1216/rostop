# rostop命令行入口模块
import rospy
import curses
from .app import App

def cli_main():
    """命令行主入口函数"""
    try:
        rospy.init_node('rostop', anonymous=True)
        curses.wrapper(lambda stdscr: App(stdscr).run())
    except rospy.ROSInterruptException:
        print("rostop被ROS关闭中断。")
    except Exception as e:
        print(f"\nrostop遇到错误: {e}")
    finally:
        pass