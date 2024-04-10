from langchain.prompts.chat import ChatPromptTemplate

deep_rooted_template = "你的名字是J.A.R.V.I.S。你是由友小任创建的微信平台AI助手，你致力于为用户提供辅助，提供真实有效易于理解的信息。现在你正在和{user}交流。"
user_template = "{text}"

chat_prompt = ChatPromptTemplate.from_messages([
        ("system",deep_rooted_template),
        ("human",user_template)
])

prompt = chat_prompt.format_messages(user="test",text="test")
print(prompt)