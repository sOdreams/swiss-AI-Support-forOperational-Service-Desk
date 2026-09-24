from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    CHAT_MODEL_DEPLOYMENT_NAME: str = "gpt-4o"
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_data"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()