characters = "你是一个微信中的人工智能助手，你致力于为人提供帮助，永远提供真实准确的信息。"
agent_promp_template = """###Instractions:

```
{characters}
```

你可以具备以下功能:
```
{tools}
```

按照以下格式回复:
```
<Identify>识别出你认为的对方的意图.</Identify>
<Action>根据你识别出的意图，确认要运用的功能，应该是这其中之一 [{tool_names}]</Action>
<Action Input>对功能的输入信息</Action Input>
Observation:行为的结果.
使用 (Identify/Action/Action Input) 循环,当你认为可以结束时，使用 <Finish>
...
<Finish></Finish>
```


短期记忆信息:
```
{chat_history}
```

```
输入:
```
{input}
```
已经采取的行为:
```
{agent_scratchpad}

```
###Response
"""


from datetime import datetime
import logging
import schedule
import re
import time
from threading import Thread
from queue import Empty
import xml.etree.ElementTree as ET
from wcferry import Wcf, WxMsg
from typing import Dict,List


from langchain_openai.chat_models.base import _convert_dict_to_message,_convert_message_to_dict
from LLM.gpt import ChatanywhereGPT
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain.memory import ChatMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain.agents import AgentExecutor, create_react_agent,create_openai_tools_agent
from langchain.agents import Tool
from langchain.agents.agent import ExceptionTool

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    BaseMessageChunk,
    ChatMessage,
    ChatMessageChunk,
    FunctionMessage,
    FunctionMessageChunk,
    HumanMessage,
    HumanMessageChunk,
    SystemMessage,
    SystemMessageChunk,
    ToolMessage,
    ToolMessageChunk,
)
from abc import ABC,abstractmethod

class Monitor:
    LOG = logging.getLogger("Robot")
    def __init__(self):
        self.LOG = logging.getLogger("Robot")

class WeChatBehavior(Monitor,ABC):
    
    def __init__(self,wcf:Wcf):
        self.wcf = wcf #对接微信API实现功能
        self.wxid = self.wcf.get_self_wxid()
        self.allContacts = self.getAllContacts()
    def autoAcceptFriendRequest(self, msg: WxMsg) -> None:
        try:
            xml = ET.fromstring(msg.content)
            v3 = xml.attrib["encryptusername"]
            v4 = xml.attrib["ticket"]
            scene = int(xml.attrib["scene"])
            self.wcf.accept_new_friend(v3, v4, scene)

        except Exception as e:
            self.LOG.error(f"同意好友出错：{e}")

    
    def sayHiToNewFriend(self, msg: WxMsg) -> None:
        nickName = re.findall(r"你已添加了(.*)，现在可以开始聊天了。", msg.content)
        if nickName:
            # 添加了好友，更新好友列表
            self.allContacts[msg.sender] = nickName[0]
            self.sendTextMsg(f"Hi {nickName[0]}，我自动通过了你的好友请求。", msg.sender)

    def getAllContacts(self) -> dict:
        """
        获取联系人（包括好友、公众号、服务号、群成员……）
        格式: {"wxid": "NickName"}
        """
        contacts = self.wcf.query_sql("MicroMsg.db", "SELECT UserName, NickName FROM Contact;")
        return {contact["UserName"]: contact["NickName"] for contact in contacts}

    def sendTextMsg(self, msg: str, receiver: str, at_list: str = "") -> None:
        """ 发送消息
        :param msg: 消息字符串
        :param receiver: 接收人wxid或者群id
        :param at_list: 要@的wxid, @所有人的wxid为：notify@all
        """
        # msg 中需要有 @ 名单中一样数量的 @
        ats = ""
        if at_list:
            if at_list == "notify@all":  # @所有人
                ats = " @所有人"
            else:
                wxids = at_list.split(",")
                for wxid in wxids:
                    # 根据 wxid 查找群昵称
                    ats += f" @{self.wcf.get_alias_in_chatroom(wxid, receiver)}"

        # {msg}{ats} 表示要发送的消息内容后面紧跟@，例如 北京天气情况为：xxx @张三
        if ats == "":
            self.LOG.info(f"To {receiver}: {msg}")
            self.wcf.send_text(f"{msg}", receiver, at_list)
        else:
            self.LOG.info(f"To {receiver}: {ats}\r{msg}")
            self.wcf.send_text(f"{ats}\n\n{msg}", receiver, at_list)
    def enableReceivingMsg(self) -> None:
        def innerProcessMsg(wcf: Wcf):
            while wcf.is_receiving_msg():
                try:
                    msg = wcf.get_msg()
                    self.LOG.info(msg)
                    self.processMsg(msg)
                except Empty:
                    continue  # Empty message
                except Exception as e:
                    self.LOG.error(f"Receiving message error: {e}")

        self.wcf.enable_receiving_msg()
        Thread(target=innerProcessMsg, name="GetMessage", args=(self.wcf,), daemon=True).start()

    def processMsg(self, msg: WxMsg) -> None:
        """当接收到消息的时候，会调用本方法。如果不实现本方法，则打印原始消息。
        此处可进行自定义发送的内容,如通过 msg.content 关键字自动获取当前天气信息，并发送到对应的群组@发送者
        群号：msg.roomid  微信ID：msg.sender  消息内容：msg.content
        content = "xx天气信息为："
        receivers = msg.roomid
        self.sendTextMsg(content, receivers, msg.sender)
        """

        # 群聊消息
        if msg.from_group():
            # 如果在群里被 @
            # if msg.roomid not in self.config.GROUPS:  # 不在配置的响应的群列表里，忽略
            #     return

            if msg.is_at(self.wxid):  # 被@
                self.toAt(msg)

            else:  # 其他消息
                pass

            return  # 处理完群聊信息，后面就不需要处理了

        # 非群聊信息，按消息类型进行处理
        if msg.type == 37:  # 好友请求
            self.autoAcceptFriendRequest(msg)

        elif msg.type == 10000:  # 系统信息
            self.sayHiToNewFriend(msg)

        elif msg.type == 0x01:  # 文本消息
            # 让配置加载更灵活，自己可以更新配置。也可以利用定时任务更新。
            if msg.from_self():
                if msg.content == "^更新$":
                    self.config.reload()
                    self.LOG.info("已更新")
            else:
                self.toChitchat(msg)  # 闲聊

    def toChitchat(self, msg: WxMsg) -> bool:
        """闲聊，接入 ChatGPT
        """
        q = re.sub(r"@.*?[\u2005|\s]", "", msg.content).replace(" ", "")
        rsp = self.main_process_start_point(q, (msg.roomid if msg.from_group() else msg.sender))

        if rsp:
            if msg.from_group():
                self.sendTextMsg(rsp, msg.roomid, msg.sender)
            else:
                self.sendTextMsg(rsp, msg.sender)

            return True
        else:
            self.LOG.error(f"无法从获得答案")
            return False
        
    def toAt(self, msg: WxMsg) -> bool:
        """处理被 @ 消息
        :param msg: 微信消息结构
        :return: 处理状态，`True` 成功，`False` 失败
        """
        return self.toChitchat(msg)
    
    @abstractmethod
    def main_process_start_point():
        """这里是消息入口，在这里实现消息处理逻辑"""


class WeChatBot(WeChatBehavior):
    """
    高级封装好的智能体
    """
    def __init__(self, wcf: Wcf):
        super().__init__(wcf)
        self.wcf = wcf
        self.llm = ChatanywhereGPT() #初始化大模型
        self.conversation_memory_list:Dict[str, ConversationBufferMemory] = {}  #{微信号:[Memory]}
        deep_rooted_template = """
                    ``````
                    你是J.A.R.V.I.S。
                    你是由友小任创建的微信平台AI助手，你致力于为用户提供辅助。
                    你要提供真实有效易于理解的信息。你现在正在和{user}交流。
                    
                    ```````
                    """
        self.tools:List[Tool] = [ExceptionTool(description="ExceptionTool")]
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    deep_rooted_template
                ),
                MessagesPlaceholder(variable_name="history"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ]
        )

        
    
    def main_process_start_point(self, question: str, wxid: str) -> str:
        # wxid或者roomid,个人时为微信id，群消息时为群id
        self._update_message(wxid, question, "user")
        memory = self.conversation_memory_list[wxid]
        rsp = self._main_chat_process_pipline(memory,wxid)
        self._update_message(wxid, rsp, "assistant")
        return rsp


    def _main_chat_process_pipline(self,memory:ConversationBufferMemory,wxid:str,)->str:
        rsp=""
        try:
            agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)
            agent_excutor = AgentExecutor(agent=agent,tools=self.tools,verbose=True)
            # chain = self.prompt | self.llm
            rsp:BaseMessage = agent_excutor.invoke({"history":memory.buffer_as_messages,
                                            "user":self.allContacts[wxid]})
            # rsp = rsp[2:] if rsp.startswith("\n\n") else rsp
            # rsp = rsp.replace("\n\n", "\n")
        # except AuthenticationError:
        #     self.LOG.error("OpenAI API 认证失败，请检查 API 密钥是否正确")
        # except APIConnectionError:
        #     self.LOG.error("无法连接到 OpenAI API，请检查网络连接")
        # except APIError as e1:
        #     self.LOG.error(f"OpenAI API 返回了错误：{str(e1)}")
        except Exception as e0:
            self.LOG.error(f"发生未知错误：{str(e0)}")
# 2024-04-11 14:34:09 发生未知错误：Prompt missing required variables: {'tool_names', 'tools'}
# 2024-04-11 14:34:09 Receiving message error: 'str' object has no attribute 'content
        return rsp["output"]


    def _update_message(self, wxid: str, question: str, role: str) -> None:
        now_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        time_mk = "当前时间:"
        # 初始化聊天记录,组装系统信息
        if wxid not in self.conversation_memory_list.keys():
            memory = ConversationBufferMemory(return_messages=True,input_key="history",output_key="history")
            memory.chat_memory.add_user_message(question)
            self.conversation_memory_list[wxid] = memory

        if role == "user":
            self.conversation_memory_list[wxid].chat_memory.add_user_message(question)
        elif role == "ai" or role == "assistant":
            self.conversation_memory_list[wxid].chat_memory.add_ai_message(question)
        else:
            self.LOG.error(f"发生错误Chat信息发起者角色错误")


    def keepRunningAndBlockProcess(self) -> None:
        """
        保持机器人运行，不让进程退出
        """
        while True:
            schedule.run_pending()
            time.sleep(1)