import os
from dotenv import load_dotenv

load_dotenv() # Carga las variables de entorno desde un archivo .env

class Settings:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://usuario:password@localhost:5432/pizzabot_db")
    
    # Redis (para caché de conversaciones)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_ENABLED = os.getenv("REDIS_ENABLED", "True").lower() == "true"
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")  # Para SMS
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")  # Para WhatsApp Business
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = "gpt-4o-mini"
    
    # App
    SECRET_KEY = os.getenv("SECRET_KEY", "tu_clave_secreta_aqui")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    DISABLE_WEBHOOK_VALIDATION = os.getenv("DISABLE_WEBHOOK_VALIDATION", "False").lower() == "true"
    
    # Ngrok (para desarrollo)
    NGROK_URL = os.getenv("NGROK_URL", "https://f943a7dcd528.ngrok-free.app")
    
    # Pizza Menu
    MENU_IMAGE_PATH = "app/static/images/menu.jpg"
    
    # Sentry (opcional para monitoreo en producción)
    SENTRY_DSN = os.getenv("SENTRY_DSN")

settings = Settings()