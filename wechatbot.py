#功能  查看时间

characters = "你是一个微信中的人工智能助手，你致力于为人提供帮助，永远提供真实准确的信息。"
agent_react_promp_template = """###Instractions:

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

#LangSmith ls__199cc6f340634602ab02391937a65f07
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


# from langchain_openai.chat_models.base import _convert_dict_to_message,_convert_message_to_dict
from LLM.chat_anywhere_gpt import ChatAnywhereGPT
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain.memory import ChatMessageHistory
from langchain.memory import ConversationBufferMemory,ConversationSummaryMemory,ConversationSummaryBufferMemory
from langchain.memory.chat_memory import BaseChatMemory
from langchain.agents import AgentExecutor, create_react_agent,create_openai_tools_agent
from langchain.agents import Tool

from abc import ABC,abstractmethod
from langchain_core.messages import BaseMessage
from configuration import Config
#TODO 实现Prompt选择器 
#TODO 实现本地知识库搭建 
## 
#TODO 实现发送微信信息工具化


class Monitor:
    LOG = logging.getLogger("Robot")

import signal
class WeChatBehavior(Monitor,ABC):
    def __init__(self):
        wcf = Wcf(debug=True)
        def handler(sig, frame):
            wcf.cleanup()  # 退出前清理环境
            exit(0)
        signal.signal(signal.SIGINT, handler)

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
            self.sendTextMsg(f"Hi {nickName[0]}，我是J.A.R.V.I.S。您的微信AI助手。我致力于提供帮助。我现在还处于早期开发阶段，希望听到您宝贵的意见。请问有什么可以帮助您的吗？", msg.sender)

    def getAllContacts(self) -> dict:
        """
        获取联系人（包括好友、公众号、服务号、群成员……）
        
        return 格式: {"wxid": "NickName"}
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
                    self.process_message(msg)
                except Empty:
                    continue  # Empty message
                except Exception as e:
                    self.LOG.error(f"Receiving message error: {e}")

        self.wcf.enable_receiving_msg()
        Thread(target=innerProcessMsg, name="GetMessage", args=(self.wcf,), daemon=True).start()

    
    def update_announcement(self,announcement:str):
        """当自身有功能更新后发布更新功能"""
        self.send_text_to_all(announcement)
    
    def send_text_to_all(self,text):
        """对所有人群发消息"""
        friends:List[Dict] = self.wcf.get_friends()
        for fri in friends:
            wxid = fri["wxid"]
            self.wcf.send_text(text,wxid)



class WeChatMessageHandler(WeChatBehavior,ABC):
    def process_message(self, msg: WxMsg):
        if msg.from_group():
            return self.handle_group_message(msg)
        elif msg.type == 37:  # 好友请求
            self.autoAcceptFriendRequest(msg)
        elif msg.type == 10000:  # 系统信息
            self.sayHiToNewFriend(msg)
        elif msg.type == 0x01:  # 文本消息
            # 让配置加载更灵活，自己可以更新配置。也可以利用定时任务更新。
            if msg.from_self():
                self.handle_private_message(msg)
            else:
                self.toChitchat(msg)  # 闲聊
        else:
            print(f"暂时无法处理的信息类型{msg.type}\nxml:{msg.xml}\ncontent:{msg.content}\nextra:{msg.extra}\nid:{msg.id}")

    def handle_group_message(self, msg: WxMsg):
        # 群消息处理逻辑
        # 如果在群里被 @
        # if msg.roomid not in self.config.GROUPS:  # 不在配置的响应的群列表里，忽略
        #     return
        if msg.is_at(self.wxid):  # 被@
            self.toAt(msg)
        else:  # 其他消息
            pass
        return  # 处理完群聊信息，后面就不需要处理了

    def handle_private_message(self, msg: WxMsg):
        # 私聊消息处理逻辑
        update_prefix = "/update"
        if msg.content == "^更新$":
            self.config.reload()
            self.LOG.info("已更新")
        elif msg.content.startswith(update_prefix):
            announcement = msg.content[len(update_prefix):]
            self.update_announcement(announcement)
    
    def toChitchat(self, msg: WxMsg) -> bool:
        """闲聊，接入 ChatGPT
        """
        
        rsp = self.process_msg_start_point(msg)

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
    def process_msg_start_point(self,msg):
        q = re.sub(r"@.*?[\u2005|\s]", "", msg.content).replace(" ", "")
        sender = (msg.roomid if msg.from_group() else msg.sender)
        pass



class Bot:
    def __init__(self):
        self.config=Config()
        chat_anywhere_config:Dict = self.config.chat_anywhere
        self.llm = ChatAnywhereGPT(model_name=chat_anywhere_config.get("model_name"),
                                   openai_api_key=chat_anywhere_config.get("api_key"),
                                   openai_api_base=chat_anywhere_config.get("api_base"),
                                   temperature=0.1) #初始化大模型 减少随机性为了稳定实现Agent功能
          
        deep_rooted_template = """
                    你是J.A.R.V.I.S。用第一人称的口吻对话。
                    你是微信平台AI助手，致力于为用户提供帮助。
                    你要提供真实有效易于理解的信息。你现在正在和{user}交流。
                    
                    
                    """
        information_toolkit = InformationToolkit()
        self.tools:List[Tool] = information_toolkit.get_tools()
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



from Toolkit.information_toolkit import InformationToolkit
from langchain_core.chat_history import BaseChatMessageHistory
class WeChatBot(WeChatMessageHandler,Bot): #HACK 将WeChatBehavior和WechatBot作为独立平等的类示例进行交互
    """
    高级封装好的智能体
    """
    def __init__(self):
        WeChatMessageHandler.__init__(self)
        Bot.__init__(self)
        self.enableReceivingMsg()
        self.conversation_memory_list:Dict[str, BaseChatMessageHistory] = {}#{微信号:[Memory]}

    def process_msg_start_point(self,msg) -> str:
        question = re.sub(r"@.*?[\u2005|\s]", "", msg.content).replace(" ", "")
        wxid = (msg.roomid if msg.from_group() else msg.sender)
        # wxid或者roomid,个人时为微信id，群消息时为群id
        self._update_message(wxid, question, "user")
        memory:ConversationSummaryBufferMemory = self.conversation_memory_list[wxid]
        memory.prune()#修理记忆
        rsp = self._main_chat_process_pipline(memory,wxid)
        self._update_message(wxid, rsp, "assistant")
        return rsp


    def _main_chat_process_pipline(self,memory:ConversationSummaryBufferMemory,wxid:str,)->str:
        
        rsp=""
        try:
            agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)
            agent_excutor = AgentExecutor(agent=agent,tools=self.tools,verbose=True)#TODO 做成ReAct形式

            rsp:BaseMessage = agent_excutor.invoke({"history":memory.buffer,
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
        return rsp["output"]


    def _update_message(self, wxid: str, question: str, role: str) -> None:
        # 初始化聊天记录,组装系统信息
        if wxid not in self.conversation_memory_list.keys():
            memory = ConversationSummaryBufferMemory(return_messages=True,
                                                     input_key="history",
                                                     output_key="history",
                                                     llm=self.llm)
            memory.chat_memory.add_user_message(question)
            self.conversation_memory_list[wxid] = memory
        memory:BaseChatMemory = self.conversation_memory_list[wxid]
        if role == "user":
            memory.chat_memory.add_user_message(question)
        elif role == "ai" or role == "assistant":
            memory.chat_memory.add_ai_message(question)
        else:
            self.LOG.error(f"发生错误,Chat信息发起者角色错误")


    def keepRunningAndBlockProcess(self) -> None:
        """
        保持机器人运行，不让进程退出
        """
        while True:
            schedule.run_pending()
            time.sleep(1)