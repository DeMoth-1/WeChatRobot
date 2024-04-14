from langchain_openai import OpenAIEmbeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-large",
                            #  base_url="https://api.chatanywhere.com.cn",
                             api_key= "sk-doRa7yB9Yp7mGzJcdCpXJWyqU13v4N1SceHWDF3ruTWVt5DX")
text = "test"
query_result = embeddings.embed_query(text)
# openai_api_key="sk-doRa7yB9Yp7mGzJcdCpXJWyqU13v4N1SceHWDF3ruTWVt5DX"
# openai_api_base="https://api.chatanywhere.com.cn"
print(query_result[:5])