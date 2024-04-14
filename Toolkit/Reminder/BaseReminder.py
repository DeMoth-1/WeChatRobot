import time
import threading
from datetime import datetime, timedelta
import re
from typing import *


# NOTE 并没完全确认定时提醒的实现方法，待编写

class TimeParser:
    @staticmethod  # 使用静态方法，因为解析时间的功能不依赖于类的实例，而是直接通过输入的时间字符串来进行操作，这样可以直接通过类名调用，无需创建实例
    def parse_time(time_str):
        # 定义时间单位与timedelta关键字参数的映射
        units = {"秒": "seconds", "分钟": "minutes", "小时": "hours", "天": "days"}
        # 使用正则表达式匹配输入的时间字符串，提取数字和单位
        match = re.match(r"(\d+)\s*(秒|分钟|小时|天)", time_str)
        # 如果匹配失败，说明输入格式不正确，抛出异常
        if not match:
            raise ValueError("时间格式错误，请按照格式输入（例如：10 秒、2 小时）。")
        # 从匹配结果中提取时间的数值和单位
        value, unit = match.groups()
        # 根据提取的单位，构造timedelta函数的关键字参数字典
        kwargs = {units[unit]: int(value)}
        # 使用关键字参数字典，创建并返回一个timedelta对象
        return timedelta(**kwargs)

class BaseReminder:
    def __init__(self, _uid, content, remind_time:timedelta):
        self.content = content
        self.remind_time = remind_time
        self.timer = None
        self._uid = _uid
    def start(self):
        """开始计时"""
        wait_time = (self.remind_time - datetime.now()).total_seconds()
        self.timer = threading.Timer(wait_time, self.remind)
        self.timer.start()

    def remind(self):
        """最基础的显示方式，需要子类覆盖这个方法"""
        print(f"提醒: {self.content} - 时间到了！")

    def cancel(self):
        """取消提醒"""
        if self.timer:
            self.timer.cancel()
    
    def get_uid(self):
        return self._uid

class BaseReminderManager:
    """用来管理多个Reminder"""
    def __init__(self):
        self.reminders:Dict[str,BaseReminder] = {}

    def add_reminder(self, id, content, time_str):
        remind_time_delta = TimeParser.parse_time(time_str)
        if remind_time_delta is None:
            return
        remind_time = datetime.now() + remind_time_delta
        if id in self.reminders:
            raise ValueError("提醒ID已存在，请使用不同的ID。")
        reminder = BaseReminder(id,content, remind_time)
        self.reminders[id] = reminder
        reminder.start()
        print(f"已添加提醒: {id}")

    def delete_reminder(self, id):
        if id in self.reminders:
            self.reminders[id].cancel()
            del self.reminders[id]
            print(f"已删除提醒: {id}")
        else:
            raise ValueError("找不到指定的提醒ID。")

    def update_reminder(self, id, content=None, time_str=None):
        if id not in self.reminders:
            raise ValueError("找不到指定的提醒ID。")
            
        if content:
            self.reminders[id].content = content
        if time_str:
            remind_time_delta = TimeParser.parse_time(time_str)
            if remind_time_delta is None:
                return
            remind_time = datetime.now() + remind_time_delta
            self.reminders[id].cancel()  # 取消旧的提醒
            self.reminders[id].remind_time = remind_time
            self.reminders[id].start()  # 开始新的提醒
        print(f"已更新提醒: {id}")

    def list_reminders(self):
        if not self.reminders:
            raise ValueError("当前没有提醒。")
            
        for id, reminder in self.reminders.items():
            print(f"ID: {id}, 内容: {reminder.content}, 提醒时间: {reminder.remind_time}")

# from langchain.pydantic_v1 import BaseModel, Field
# from langchain.tools import BaseTool
# class ReminderInput(BaseModel):
#   query: str = Field(desciption="待设置的提醒指令")

# class ReminderAgent(BaseTool):
#   name = "定时提醒"
#   description = "用来在指定时间之后提醒指定内容
#   args_schema: Type[BaseModel] = ReminderInput
#   
#   all_reminder:Dic[str:BaseReminderManager] = {}  #{微信ID:此人的提醒管理器}
#   
#   def _run(
#       self,query : str,run_mannager:Optional=None,
# ) -> str:
# 
#   async def _arun(
#       self, query:str,runmanager=None,
# ) -> str:
#       

# 示例使用
if __name__ == "__main__":
    manager = BaseReminderManager()
    manager.add_reminder("1", "这是第一个提醒", "3 秒")
    manager.add_reminder("2", "这是第二个提醒", "1 分钟")
    time.sleep(15)
    manager.list_reminders()
    manager.update_reminder("2", "更新第二个提醒的内容", "1秒")
    manager.delete_reminder("1")
    manager.list_reminders()