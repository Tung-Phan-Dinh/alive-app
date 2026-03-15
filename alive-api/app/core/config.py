from urllib.parse import quote_plus
from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

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

    # Apple Sign-In
    APPLE_CLIENT_ID: str = "com.udead.app"  # iOS Bundle ID (e.g., com.yourapp.alive)
    APPLE_ISSUER: str = "https://appleid.apple.com"
    APPLE_JWKS_URL: str = "https://appleid.apple.com/auth/keys"
    APPLE_JWKS_CACHE_HOURS: int = 6

    # Apple Token Revocation (for account deletion - get from your Apple Developer account)
    APPLE_TEAM_ID: str = os.getenv("APPLE_TEAM_ID") # Your Apple Developer Team ID
    APPLE_KEY_ID: str = os.getenv("APPLE_KEY_ID")  # Key ID for Sign in with Apple private key
    APPLE_PRIVATE_KEY: str = os.getenv("APPLE_PRIVATE_KEY")  # Base64-encoded .p8 private key contents

    # Email settings (SMTP)
    SMTP_HOST: str = ""  # e.g., smtp.gmail.com
    SMTP_PORT: int = 587  # 587 for TLS, 465 for SSL
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    EMAIL_FROM: str = ""  # e.g., noreply@yourdomain.com
    EMAIL_FROM_NAME: str = "Alive App"
    EMAIL_USE_CONSOLE: bool = False  # Set True for dev (prints instead of sending)

    # Worker settings
    WORKER_BATCH_SIZE: int = 50  # Users to process per batch
    WORKER_EMAIL_DELAY_SECONDS: float = 0.5  # Delay between emails (rate limiting)

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"

settings = Settings()
