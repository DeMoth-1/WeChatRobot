
from langchain_community.agent_toolkits.ainetwork.toolkit import AINetworkToolkit
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain.tools import BaseTool, StructuredTool, tool
from typing import TYPE_CHECKING, List, Literal, Optional



from datetime import datetime
def get_time_fn():
    return str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

get_time_tool = StructuredTool.from_function(
    func = get_time_fn,
    name = "get_current_time",
    description = "当你需要获取时间时调用，返回当前时刻时间",
)

class InformationToolkit(BaseToolkit):

    def get_tools(self) -> List[BaseTool]:
        """Get the tools in the toolkit."""
        return [get_time_tool,
                ]
