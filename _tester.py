from langchain_community.embeddings.huggingface import HuggingFaceBgeEmbeddings
from configuration import Config
from typing import Dict
bge_embeddings_config:Dict = Config().bge_embeddings
# model_name = "BAAI/bge-large-zh"
# model_kwargs = {"device": "cpu"}
# encode_kwargs = {"normalize_embeddings": True}
hf = HuggingFaceBgeEmbeddings(
    model_name=bge_embeddings_config.get("model_name"), 
    model_kwargs=bge_embeddings_config.get("model_kwargs"), 
    encode_kwargs=bge_embeddings_config.get("encode_kwargs"),
    cache_folder=bge_embeddings_config.get("cache_folder")
)

print(hf)