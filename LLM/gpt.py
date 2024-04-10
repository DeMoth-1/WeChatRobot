from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel, SimpleChatModel
from langchain_core.language_models.chat_models import generate_from_stream,agenerate_from_stream
from langchain_core.messages import AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import run_in_executor
#接口项目https://github.com/chatanywhere/GPT_API_free

from langchain_core.pydantic_v1 import SecretStr
from openai import APIConnectionError, APIError, AuthenticationError, OpenAI
from langchain_openai.chat_models.base import _convert_dict_to_message,_convert_message_to_dict
from langchain_openai import ChatOpenAI
import logging


model_name ="gpt-3.5-turbo-instruct"
openai_api_key="sk-doRa7yB9Yp7mGzJcdCpXJWyqU13v4N1SceHWDF3ruTWVt5DX"
openai_api_base="https://api.chatanywhere.com.cn"

class ChatanywhereGPT(ChatOpenAI):
    model_name ="gpt-3.5-turbo"
    openai_api_key:SecretStr="sk-doRa7yB9Yp7mGzJcdCpXJWyqU13v4N1SceHWDF3ruTWVt5DX"
    openai_api_base="https://api.chatanywhere.com.cn"
    LOG = logging.getLogger("ChatGPT")
    @property
    def _llm_type(self) -> str:
        return "chatanywhere"

    def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> ChatResult:
            if self.streaming:
                stream_iter = self._stream(
                    messages, stop=stop, run_manager=run_manager, **kwargs
                )
                return generate_from_stream(stream_iter)
            message_dicts, params = self._create_message_dicts(messages, stop)
            params = {**params, **kwargs}
            response = self.client.create(messages=message_dicts, **params)
            return self._create_chat_result(response)


if __name__ == "__main__" : 
    chat = ChatanywhereGPT()
    # print(chat.invoke("111"))
    from langchain.prompts.chat import ChatPromptTemplate
    deep_rooted_template = "你的名字是J.A.R.V.I.S。你是由友小任创建的微信平台AI助手，你致力于为用户提供辅助，提供真实有效易于理解的信息。现在你正在和{user}交流。"
    user_template = "{text}"
    chat_prompt = ChatPromptTemplate.from_messages([
            ("system",deep_rooted_template),
            ("human",user_template)
    ])
    prompt = chat_prompt.format_messages(user="test",text="你是谁？你是谁创作的？你是什么模型。")
    print(chat.invoke(prompt))
