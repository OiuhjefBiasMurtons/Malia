import asyncio
from database.connection import SessionLocal
from app.services.bot_service import BotService

async def test_menu_query():
    db = SessionLocal()
    bot = BotService(db)
    
    print('Testing: ¿Qué pavés tienen disponibles?')
    result = await bot.process_message('+573001234567', '¿Qué pavés tienen disponibles?')
    
    print(f"\n📊 RESPUESTA COMPLETA:")
    print(f"Tipo: {result.get('type', 'undefined')}")
    
    if result.get('text_message'):
        print(f"Texto: {result.get('text_message')}")
    
    if result.get('images'):
        print(f"Imágenes: {len(result.get('images', []))} encontradas")
        for i, img in enumerate(result.get('images', []), 1):
            print(f"  {i}. URL: {img.get('url', 'No URL')}")
            print(f"     Caption: {img.get('caption', 'No caption')}")
    
    # Mostrar toda la respuesta para debug
    print(f"\n🔍 DEBUG - Respuesta completa:")
    print(result)
    
    db.close()

# Probar diferentes consultas
async def test_multiple_queries():
    db = SessionLocal()
    bot = BotService(db)
    
    queries = [
        "¿Qué pavés tienen disponibles?"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n{'='*50}")
        print(f"PRUEBA {i}: {query}")
        print('='*50)
        
        result = await bot.process_message('+573001234567', query)
        
        print(f"Tipo de respuesta: {result.get('type')}")
        
        if result.get('text_message'):
            print(f"Mensaje: {result.get('text_message')}")
        else:
            print("❌ No hay text_message")
            
        if result.get('images'):
            print(f"Imágenes: {len(result.get('images'))} encontradas")
        
        # Pausa pequeña entre consultas
        await asyncio.sleep(0.5)
    
    db.close()

if __name__ == "__main__":
    print("🔄 Ejecutando prueba simple...")
    asyncio.run(test_menu_query())
    
    print("\n\n🔄 Ejecutando pruebas múltiples...")
    asyncio.run(test_multiple_queries())