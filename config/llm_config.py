import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()
@dataclass
class LLmConfig:
    api_key: str
    base_url: str
    llm_model: str
    temperature: float
    vl_model: str
    item_model: str
llm_config = LLmConfig(
    api_key = os.getenv("OPENAI_API_KEY"),
    base_url= os.getenv("OPENAI_API_BASE"),
    llm_model = os.getenv("LLM_DEFAULT_MODEL"),
    temperature = float(os.getenv("LLM_DEFAULT_TEMPERATURE")),
    vl_model = os.getenv("VL_MODEL"),
    item_model = os.getenv("ITEM_MODEL")
)
