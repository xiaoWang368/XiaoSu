from langchain_openai import ChatOpenAI

from config.llm_config import llm_config

_llm_client_cache = {}

def get_llm_client(model: str|None = None, json_model: bool = False):
    m = model or llm_config.llm_model

    key = (m, json_model)

    if key in _llm_client_cache:
        return _llm_client_cache[key]

    client = ChatOpenAI(
        model = m,
        base_url = llm_config.base_url,
        api_key = llm_config.api_key,
        temperature = llm_config.temperature,
    )

    _llm_client_cache[key] = client
    return client
if __name__ == "__main__":
    client = get_llm_client()
    response = client.invoke("你好，请问你是谁")
    print(response.content)
