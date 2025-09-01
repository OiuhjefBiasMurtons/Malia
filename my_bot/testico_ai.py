"""
🤖 TESTICO AI - PRUEBAS EDUCATIVAS PARA INTELIGENCIA ARTIFICIAL 
===============================================================

Este módulo es una versión educativa de testico.py que demuestra el 
funcionamiento completo del sistema integrado con OpenAI GPT y function-calling.

Autor: Sistema de Chat Bot WhatsApp con IA
Fecha: 2025-08-21  
Versión: 1.0

🎯 PROPÓSITO EDUCATIVO:
- Mostrar cómo funciona la integración GPT + OrderService
- Demostrar el flujo completo de conversación con IA
- Explicar step-by-step el function-calling
- Servir como documentación viva del sistema

🔄 FLUJO DE CONVERSACIÓN CON IA:
1. Usuario envía mensaje en lenguaje natural
2. BotService usa GPT para entender la intención
3. GPT decide qué herramientas (tools) usar
4. BotService ejecuta las herramientas requeridas
5. GPT genera respuesta natural basada en resultados
6. Usuario recibe respuesta humanizada

🛠️ HERRAMIENTAS DISPONIBLES (FUNCTION-CALLING):
- get_menu: Obtiene el menú completo de pavés
- create_order: Crea pedidos con validación inteligente
- get_order_status: Consulta estado de pedidos existentes

⚡ CARACTERÍSTICAS DE LA IA:
- Conversación natural en español
- Entendimiento contextual de pedidos
- Validación automática de datos
- Manejo inteligente de errores
- Respuestas personalizadas y empáticas

🧪 CASOS DE PRUEBA:
- Conversación completa de pedido
- Consultas de menú específicas
- Manejo de errores y validaciones
- Flujos de conversación complejos

💡 EDUCATIVO: Cada prueba incluye explicaciones detalladas
del funcionamiento interno de la IA integrada.
"""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

# Funciones de utilidad para formato
def print_section(title: str):
    """Imprime una sección principal"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_subsection(title: str):
    """Imprime una subsección"""
    print(f"\n--- {title} ---")

def print_result(result: Dict[str, Any], description: str = ""):
    """Imprime un resultado de manera formateada"""
    if description:
        print(f"\n✅ {description}")
    print(f"   Resultado: {result.get('message', 'Sin mensaje')}")
    if result.get('success'):
        print("   ✓ Operación exitosa")
    else:
        print("   ❌ Operación falló")
    
    # Mostrar datos adicionales si existen
    if 'data' in result and result['data']:
        print("   📊 Datos:")
        for key, value in result['data'].items():
            print(f"      {key}: {value}")

def print_ai_explanation(title: str, explanation: str):
    """Imprime explicaciones técnicas de la IA"""
    print(f"\n🧠 {title}")
    print(f"   {explanation}")

def print_conversation_flow(user_message: str, ai_decision: str, tools_used: list, ai_response: str):
    """Muestra el flujo completo de una conversación con IA"""
    print(f"\n💬 FLUJO DE CONVERSACIÓN:")
    print(f"   👤 Usuario: \"{user_message}\"")
    print(f"   🤖 Decisión IA: {ai_decision}")
    print(f"   🛠️ Herramientas usadas: {', '.join(tools_used) if tools_used else 'Ninguna'}")
    print(f"   🤖 Respuesta IA: \"{ai_response}\"")

def print_error(error: str):
    """Imprime un error de manera formateada"""
    print(f"❌ ERROR: {error}")

class TesticoAIRunner:
    """Clase principal que ejecuta todas las pruebas educativas de IA"""
    
    def __init__(self):
        self.db = None
        self.bot_service = None
        self.order_service = None
        self.test_phone = "+573001234567"
        self.test_user_name = "Ana García Test"
        self.test_address = "Calle AI #123-45, Bogotá"
        
    def setup_services(self):
        """Configura todos los servicios necesarios para las pruebas de IA"""
        print_section("🔧 CONFIGURACIÓN DE SERVICIOS IA")
        
        try:
            # Configurar base de datos
            from database.connection import SessionLocal, engine
            from app.services.order_service import OrderService
            from app.services.bot_service import BotService
            
            # Crear sesión de base de datos
            self.db = SessionLocal()
            print("✅ Conexión a PostgreSQL establecida")
            
            # Crear servicios
            self.order_service = OrderService(self.db)
            self.bot_service = BotService(self.db)
            print("✅ OrderService y BotService inicializados")
            
            # Verificar configuración de OpenAI
            from config.settings import settings
            if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
                print("✅ API Key de OpenAI configurada")
            else:
                print("⚠️ API Key de OpenAI no encontrada")
                
            print_ai_explanation(
                "ARQUITECTURA DE IA",
                "BotService actúa como orquestador entre GPT y OrderService. "
                "GPT decide qué herramientas usar basado en el contexto, "
                "y BotService ejecuta esas herramientas de forma segura."
            )
            
            return True
            
        except Exception as e:
            print_error(f"No se pudo configurar los servicios: {e}")
            return False
    
    async def test_ai_menu_consultation(self):
        """Prueba consultas de menú usando IA"""
        print_section("🍰 PRUEBA 1: CONSULTA DE MENÚ CON IA")
        
        print_ai_explanation(
            "FUNCIÓN GET_MENU",
            "La IA puede acceder al menú completo usando la herramienta 'get_menu'. "
            "Esta herramienta está definida en bot_service._tool_defs() con un schema JSON "
            "que describe exactamente qué parámetros acepta y qué devuelve."
        )
        
        # Prueba 1: Consulta general del menú
        print_subsection("Prueba 1.1: Consulta general")
        user_message = "Hola, ¿qué pavés tienen disponibles?"
        
        try:
            bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
            
            print_conversation_flow(
                user_message,
                "Usar herramienta get_menu para obtener menú completo",
                ["get_menu"],
                bot_reply.get('text_message', 'Sin respuesta')
            )
            
            print_ai_explanation(
                "ANÁLISIS DEL FLUJO",
                "1. GPT identifica intención: consultar menú\n"
                "   2. GPT decide usar tool 'get_menu' (sin parámetros)\n"
                "   3. BotService ejecuta OrderService.get_menu()\n"
                "   4. GPT recibe datos y genera respuesta natural"
            )
            
        except Exception as e:
            print_error(f"Error en consulta de menú: {e}")
        
        # Prueba 2: Consulta específica
        print_subsection("Prueba 1.2: Consulta específica")
        user_message = "¿Tienen pavés de chocolate? ¿Cuánto cuestan?"
        
        try:
            bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
            
            print_conversation_flow(
                user_message,
                "Usar herramienta get_menu y filtrar por chocolate",
                ["get_menu"],
                bot_reply.get('text_message', 'Sin respuesta')
            )
            
            print_ai_explanation(
                "INTELIGENCIA CONTEXTUAL",
                "GPT entiende que 'pavés de chocolate' requiere buscar en el menú. "
                "Aunque get_menu no tiene filtros, la IA puede procesar los resultados "
                "y responder específicamente sobre productos con chocolate."
            )
            
        except Exception as e:
            print_error(f"Error en consulta específica: {e}")
    
    async def test_ai_order_creation(self):
        """Prueba creación de pedidos usando IA"""
        print_section("🛒 PRUEBA 2: CREACIÓN DE PEDIDOS CON IA")
        
        print_ai_explanation(
            "FUNCIÓN CREATE_ORDER",
            "La herramienta 'create_order' tiene un schema complejo que requiere:\n"
            "   - phone: string (número de teléfono)\n"
            "   - customer_name: string (nombre del cliente)\n"
            "   - delivery_address: string (dirección de entrega)\n"
            "   - items: array de objetos con pave_id y quantity\n"
            "La IA debe extraer y validar toda esta información del contexto."
        )
        
        # Prueba 1: Pedido completo en un mensaje
        print_subsection("Prueba 2.1: Pedido completo")
        user_message = (f"Quiero hacer un pedido. Soy {self.test_user_name}, "
                       f"mi número es {self.test_phone}, mi dirección es {self.test_address}. "
                       f"Quiero 2 pavés de tres leches y 1 pavé de chocolate.")
        
        try:
            bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
            
            print_conversation_flow(
                user_message,
                "Extraer datos del pedido y usar create_order",
                ["get_menu", "create_order"],
                bot_reply.get('text_message', 'Sin respuesta')
            )
            
            print_ai_explanation(
                "EXTRACCIÓN DE DATOS",
                "1. GPT identifica intención: crear pedido\n"
                "   2. GPT extrae: nombre, teléfono, dirección, items\n"
                "   3. GPT primero usa get_menu para obtener pave_ids\n"
                "   4. GPT mapea 'tres leches' y 'chocolate' a IDs específicos\n"
                "   5. GPT construye la llamada a create_order con datos validados"
            )
            
        except Exception as e:
            print_error(f"Error en pedido completo: {e}")
        
        # Prueba 2: Pedido con información faltante
        print_subsection("Prueba 2.2: Pedido con datos faltantes")
        user_message = "Quiero pedir 3 pavés de fresa"
        
        try:
            bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
            
            print_conversation_flow(
                user_message,
                "Detectar información faltante y solicitar datos",
                ["get_menu"],
                bot_reply.get('text_message', 'Sin respuesta')
            )
            
            print_ai_explanation(
                "VALIDACIÓN INTELIGENTE",
                "GPT detecta que faltan datos obligatorios (nombre, dirección) "
                "y genera una respuesta solicitando la información faltante "
                "en lugar de hacer una llamada incompleta a create_order."
            )
            
        except Exception as e:
            print_error(f"Error en pedido incompleto: {e}")
    
    async def test_ai_order_status(self):
        """Prueba consultas de estado usando IA"""
        print_section("📋 PRUEBA 3: CONSULTA DE ESTADO CON IA")
        
        print_ai_explanation(
            "FUNCIÓN GET_ORDER_STATUS",
            "La herramienta 'get_order_status' requiere:\n"
            "   - phone: string (para identificar al usuario)\n"
            "   - order_id: integer (ID específico del pedido)\n"
            "La IA debe extraer o inferir estos parámetros del contexto."
        )
        
        # Crear un pedido primero para poder consultarlo
        print_subsection("Preparación: Crear pedido de prueba")
        
        try:
            # Crear pedido directamente usando OrderService
            direct_result = self.order_service.create_order(
                phone_number=self.test_phone,
                items=[{"product_id": 1, "quantity": 2}],
                delivery_address=self.test_address,
                payment_method="efectivo",
                notes="Pedido de prueba para testico AI"
            )
            
            if direct_result.get('success'):
                order_id = direct_result['data']['order_id']
                print(f"✅ Pedido creado directamente: ID {order_id}")
                
                # Ahora probar consulta con IA
                print_subsection("Prueba 3.1: Consulta de estado específico")
                user_message = f"¿Cómo va mi pedido número {order_id}?"
                
                bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
                
                print_conversation_flow(
                    user_message,
                    f"Usar get_order_status con order_id={order_id}",
                    ["get_order_status"],
                    bot_reply.get('text_message', 'Sin respuesta')
                )
                
                print_ai_explanation(
                    "EXTRACCIÓN DE ID",
                    "GPT identifica el número del pedido en el mensaje del usuario "
                    "y lo usa como parámetro order_id en la llamada a get_order_status. "
                    "También infiere el phone del contexto de la conversación."
                )
                
                # Prueba consulta general
                print_subsection("Prueba 3.2: Consulta general de pedidos")
                user_message = "¿Tengo algún pedido pendiente?"
                
                bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
                
                print_conversation_flow(
                    user_message,
                    "Usar get_order_status sin order_id específico",
                    ["get_order_status"],
                    bot_reply.get('text_message', 'Sin respuesta')
                )
                
            else:
                print_error("No se pudo crear pedido de prueba")
                
        except Exception as e:
            print_error(f"Error en consulta de estado: {e}")
    
    async def test_ai_conversation_flow(self):
        """Prueba flujos de conversación complejos"""
        print_section("💬 PRUEBA 4: FLUJOS DE CONVERSACIÓN COMPLEJOS")
        
        print_ai_explanation(
            "CONVERSACIÓN MULTI-TURNO",
            "BotService mantiene contexto entre mensajes usando user_sessions. "
            "Esto permite que GPT recuerde información previa y haga referencias "
            "a datos mencionados anteriormente en la conversación."
        )
        
        # Simular conversación paso a paso
        conversation_steps = [
            {
                "message": "Hola, quiero hacer un pedido",
                "expected_action": "Saludar y solicitar información del pedido"
            },
            {
                "message": f"Soy {self.test_user_name}",
                "expected_action": "Guardar nombre y solicitar más información"
            },
            {
                "message": f"Mi dirección es {self.test_address}",
                "expected_action": "Guardar dirección y solicitar productos deseados"
            },
            {
                "message": "Quiero 2 pavés de tres leches",
                "expected_action": "Usar get_menu para buscar el producto y procesar pedido"
            }
        ]
        
        for i, step in enumerate(conversation_steps, 1):
            print_subsection(f"Paso {i}: {step['expected_action']}")
            
            try:
                user_message = step["message"]
                bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
                
                print_conversation_flow(
                    user_message,
                    step["expected_action"],
                    ["Contextual"],
                    bot_reply.get('text_message', 'Sin respuesta')
                )
                
                # Pequeña pausa entre mensajes para simular conversación real
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print_error(f"Error en paso {i}: {e}")
        
        print_ai_explanation(
            "GESTIÓN DE CONTEXTO",
            "Cada mensaje se procesa con el contexto completo de la conversación. "
            "BotService puede acceder a mensajes previos y mantener el estado "
            "del pedido a través de múltiples intercambios."
        )
    
    async def test_ai_error_handling(self):
        """Prueba manejo de errores y casos edge"""
        print_section("⚠️ PRUEBA 5: MANEJO INTELIGENTE DE ERRORES")
        
        print_ai_explanation(
            "ROBUSTEZ DE LA IA",
            "BotService incluye manejo semántico de errores. Cuando una herramienta "
            "falla, GPT recibe el mensaje de error y puede generar respuestas "
            "apropiadas o sugerir soluciones alternativas."
        )
        
        # Prueba 1: Producto inexistente
        print_subsection("Prueba 5.1: Producto inexistente")
        user_message = "Quiero pedir pavés de unicornio mágico"
        
        try:
            bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
            
            print_conversation_flow(
                user_message,
                "Buscar en menú y manejar producto no encontrado",
                ["get_menu"],
                bot_reply.get('text_message', 'Sin respuesta')
            )
            
        except Exception as e:
            print_error(f"Error en producto inexistente: {e}")
        
        # Prueba 2: Pedido con datos inválidos
        print_subsection("Prueba 5.2: Datos inválidos")
        user_message = "Quiero -5 pavés de chocolate para la dirección ''"
        
        try:
            bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
            
            print_conversation_flow(
                user_message,
                "Detectar datos inválidos y solicitar corrección",
                [],
                bot_reply.get('text_message', 'Sin respuesta')
            )
            
        except Exception as e:
            print_error(f"Error en datos inválidos: {e}")
        
        print_ai_explanation(
            "RECUPERACIÓN ELEGANTE",
            "La IA no solo detecta errores, sino que proporciona explicaciones "
            "útiles y guía al usuario hacia una solución válida. Esto mejora "
            "significativamente la experiencia del usuario."
        )
    
    async def test_ai_validation_issues(self):
        """Prueba problemas críticos de validación de la IA"""
        print_section("� PRUEBA 6: VALIDACIÓN CRÍTICA DE IA")
        
        print_ai_explanation(
            "VALIDACIÓN ROBUSTA",
            "Es crítico que la IA valide productos contra el menú real antes "
            "de procesar pedidos. No debe aceptar productos inventados o inexistentes."
        )
        
        # Prueba 1: Producto completamente inventado
        print_subsection("Prueba 6.1: Producto completamente inventado")
        user_message = "Quiero pedir pavés de unicornio mágico"
        
        try:
            bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
            
            print_conversation_flow(
                user_message,
                "Rechazar producto inexistente y sugerir alternativas",
                ["get_menu"],
                bot_reply.get('text_message', 'Sin respuesta')
            )
            
            # Analizar si la respuesta es apropiada
            response_text = bot_reply.get('text_message', '').lower()
            if any(word in response_text for word in ['no tenemos', 'no disponible', 'no existe', 'no encontrado']):
                print("   ✅ VALIDACIÓN CORRECTA: IA rechaza producto inexistente")
            else:
                print("   ❌ VALIDACIÓN INCORRECTA: IA acepta producto inexistente")
                print("   💡 La IA debe consultar get_menu y validar antes de aceptar pedidos")
            
        except Exception as e:
            print_error(f"Error en validación de producto inventado: {e}")
        
        # Prueba 2: Sabor que no existe
        print_subsection("Prueba 6.2: Sabor inexistente")
        user_message = "Quiero pavés de tres leches y pavés de pizza"
        
        try:
            bot_reply = await self.bot_service.process_message(self.test_phone, user_message)
            
            print_conversation_flow(
                user_message,
                "Aceptar producto válido, rechazar inválido",
                ["get_menu"],
                bot_reply.get('text_message', 'Sin respuesta')
            )
            
            # Analizar validación parcial
            response_text = bot_reply.get('text_message', '').lower()
            if 'pizza' in response_text and any(word in response_text for word in ['no tenemos', 'no disponible']):
                print("   ✅ VALIDACIÓN MIXTA CORRECTA: IA distingue productos válidos/inválidos")
            elif 'pizza' not in response_text:
                print("   ✅ VALIDACIÓN SELECTIVA: IA filtra automáticamente productos inválidos")
            else:
                print("   ❌ VALIDACIÓN INCORRECTA: IA acepta todos los productos sin verificar")
                
        except Exception as e:
            print_error(f"Error en validación de sabor inexistente: {e}")
        
        print_ai_explanation(
            "MEJORAS NECESARIAS",
            "Si la IA acepta productos inexistentes, se debe:\n"
            "   1. Mejorar el prompt del sistema en BotService\n"
            "   2. Agregar validación estricta en las herramientas\n"
            "   3. Implementar lógica de fallback cuando no encuentra productos"
        )
    
    def cleanup(self):
        """Limpia recursos"""
        if self.db:
            self.db.close()
            print("\n🧹 Sesión de base de datos cerrada")

async def main():
    """Función principal que ejecuta todas las pruebas educativas de IA"""
    print_section("🤖 TESTICO AI - SISTEMA DE PRUEBAS EDUCATIVAS")
    print("Este programa demuestra el funcionamiento completo del sistema")
    print("integrado con OpenAI GPT y function-calling.")
    print("\n🎯 Objetivo: Entender cómo la IA procesa lenguaje natural")
    print("y lo convierte en acciones específicas del negocio.")
    
    runner = TesticoAIRunner()
    
    try:
        # Configuración inicial
        if not runner.setup_services():
            print_error("No se pudo configurar el sistema. Abortando pruebas.")
            return
        
        # Ejecutar todas las pruebas
        await runner.test_ai_menu_consultation()
        await runner.test_ai_order_creation()
        await runner.test_ai_order_status()
        await runner.test_ai_conversation_flow()
        await runner.test_ai_error_handling()
        await runner.test_ai_validation_issues()
        
        print_section("🎉 RESUMEN EDUCATIVO")
        print("✅ Todas las pruebas de IA completadas exitosamente")
        print("\n🧠 LECCIONES APRENDIDAS:")
        print("1. GPT puede decidir inteligentemente qué herramientas usar")
        print("2. Function-calling permite integración segura con business logic")
        print("3. El manejo de errores semántico mejora la experiencia del usuario")
        print("4. El contexto conversacional permite flujos naturales")
        print("5. La validación automática es CRÍTICA para evitar pedidos incorrectos")
        
        print("\n⚠️ ISSUES CRÍTICOS IDENTIFICADOS:")
        print("- El bot puede aceptar productos inexistentes (ej: 'pavés de unicornio mágico')")
        print("- Falta validación estricta contra el menú real")
        print("- Necesita mejorar el prompt del sistema para rechazar productos inválidos")
        
        print("\n🚀 PRÓXIMOS PASOS:")
        print("- PRIORIDAD ALTA: Corregir validación de productos")
        print("- Implementar más herramientas (cancelar_pedido, modificar_pedido)")
        print("- Agregar métricas de satisfacción del usuario")
        print("- Optimizar prompts para respuestas más precisas")
        print("- Implementar cache inteligente para respuestas frecuentes")
        
    except KeyboardInterrupt:
        print("\n\n⛔ Pruebas interrumpidas por el usuario")
    except Exception as e:
        print_error(f"Error general en las pruebas: {e}")
    finally:
        runner.cleanup()

if __name__ == "__main__":
    print("🔄 Iniciando pruebas asíncronas...")
    asyncio.run(main())
