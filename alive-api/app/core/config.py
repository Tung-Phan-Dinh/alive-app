from urllib.parse import quote_plus
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "U dead ??"
    JWT_SECRET: str
    JWT_ALG: str = "HS256"
    JWT_EXPIRE_DAYS: int = 30

    DB_HOST: str
    DB_PORT: int = 3306
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_IOS_CLIENT_ID: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"

settings = Settings()
