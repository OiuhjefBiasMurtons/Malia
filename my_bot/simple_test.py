import asyncio
from database.connection import SessionLocal
from app.services.bot_service import BotService

async def simple_test():
    """Prueba simple y directa"""
    db = SessionLocal()
    bot = BotService(db)
    
    # Tu mensaje de prueba
    query = input("¿Qué quieres preguntarle al bot? ")
    
    print(f"\n🤖 Enviando: '{query}'")
    result = await bot.process_message('+573001234567', query)
    
    print(f"\n📋 RESPUESTA:")
    print(f"Tipo: {result.get('type')}")
    
    # Manejo explícito por tipo de respuesta
    response_type = result.get('type')
    
    if response_type == 'text':
        print(f"\n💬 Mensaje de texto:")
        print(result.get('text_message', 'Sin mensaje'))
        
    elif response_type == 'images':
        print(f"\n🖼️ Solo imágenes:")
        images = result.get('images', [])
        print(f"Total de imágenes: {len(images)}")
        for i, img in enumerate(images, 1):
            print(f"  {i}. {img.get('caption', 'Sin descripción')}")
            print(f"     URL: {img.get('url', 'Sin URL')}")
            
    elif response_type == 'combined':
        print(f"\n� Respuesta combinada (texto + imágenes):")
        
        # Parte de texto
        if result.get('text_message'):
            print(f"\n💬 Texto:")
            print(result.get('text_message'))
        
        # Parte de imágenes
        if result.get('images'):
            images = result.get('images', [])
            print(f"\n🖼️ Imágenes ({len(images)}):")
            for i, img in enumerate(images, 1):
                print(f"  {i}. {img.get('caption', 'Sin descripción')}")
                print(f"     URL: {img.get('url', 'Sin URL')}")
        
    else:
        print(f"\n⚠️ Tipo de respuesta desconocido: {response_type}")
        
    # Debug completo
    print(f"\n🔍 Debug - Campos presentes:")
    print(f"  - text_message: {'✓' if result.get('text_message') else '✗'}")
    print(f"  - images: {'✓' if result.get('images') else '✗'}")

    db.close()

if __name__ == "__main__":
    asyncio.run(simple_test())
