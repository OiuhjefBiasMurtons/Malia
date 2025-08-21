"""
⚙️ CONFIGURACIÓN GLOBAL DEL SISTEMA
===================================

Este módulo centraliza todas las configuraciones del sistema, cargando variables
de entorno y proporcionando valores por defecto seguros para desarrollo.

Autor: Sistema de Configuración Central
Fecha: 2025-08-21
Versión: 1.0

🎯 PROPÓSITO:
- Centralizar configuración de toda la aplicación
- Cargar variables de entorno desde archivo .env
- Proporcionar defaults seguros para desarrollo
- Organizar configuraciones por categorías

🏗️ CATEGORÍAS DE CONFIGURACIÓN:

📊 BASE DE DATOS:
- DATABASE_URL: PostgreSQL connection string
- Configuración para SQLAlchemy

🔗 REDIS (Caché):
- REDIS_URL: Conexión a Redis para caché de sesiones
- REDIS_ENABLED: Flag para habilitar/deshabilitar Redis

📱 TWILIO (WhatsApp):
- Account SID, Auth Token
- Números para SMS y WhatsApp Business
- Validación de webhooks

🤖 OPENAI:
- API Key para GPT
- Modelo predeterminado (gpt-4o-mini)

🛠️ APLICACIÓN:
- SECRET_KEY: Para JWT y seguridad
- DEBUG: Modo desarrollo/producción
- Validación de webhooks

🌐 DESARROLLO:
- NGROK_URL: Para túneles de desarrollo
- Rutas de archivos estáticos

📊 MONITOREO:
- SENTRY_DSN: Para logging en producción

🔒 SEGURIDAD:
- Carga desde variables de entorno
- Valores por defecto NO incluyen credenciales reales
- Separación entre desarrollo y producción

📝 USO:
    from config.settings import settings
    print(settings.OPENAI_MODEL)  # "gpt-4o-mini"
"""

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