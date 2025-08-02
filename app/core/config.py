from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    MONGO_URI: str
    MONGO_DB_NAME: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8')


settings = Settings()
