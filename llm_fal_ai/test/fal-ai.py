import fal_client
import time
import asyncio
from typing import Dict, Any

# ===== CONFIGURACIÓN =====
# Asegúrate de configurar tu API key como variable de entorno:
# export FAL_KEY="tu_api_key_aqui"
import os


class FalClientTester:
    def __init__(self):
        self.endpoint = "fal-ai/flux/dev"
        self.default_arguments = {
            "prompt": "a majestic cat sitting on a throne, digital art, highly detailed",
            "seed": 6252023,
            "image_size": "landscape_4_3",
            "num_images": 2
        }

    def on_queue_update(self, update):
        """Callback para recibir actualizaciones de la cola"""
        if isinstance(update, fal_client.InProgress):
            print(f"🔄 Estado: En progreso")
            for log in update.logs:
                print(f"📝 Log: {log['message']}")
        elif hasattr(update, 'status'):
            print(f"📊 Estado de la cola: {update.status}")

    def ejemplo_1_subscribe_simple(self):
        """Ejemplo 1: Uso básico con subscribe (recomendado)"""
        print("\n" + "=" * 50)
        print("🚀 EJEMPLO 1: Subscribe (Método recomendado)")
        print("=" * 50)

        try:
            result = fal_client.subscribe(
                self.endpoint,
                arguments=self.default_arguments,
                with_logs=True,
                on_queue_update=self.on_queue_update,
            )

            print("✅ Resultado obtenido:")
            print(f"📸 Número de imágenes generadas: {len(result.get('images', []))}")

            # Mostrar URLs de las imágenes
            for i, image in enumerate(result.get('images', [])):
                print(f"🖼️  Imagen {i + 1}: {image.get('url', 'No URL')}")

            return result

        except Exception as e:
            print(f"❌ Error en subscribe: {e}")
            return None

    def ejemplo_2_queue_management(self):
        """Ejemplo 2: Gestión manual de cola"""
        print("\n" + "=" * 50)
        print("⚙️  EJEMPLO 2: Gestión manual de cola")
        print("=" * 50)

        try:
            # Paso 1: Enviar trabajo a la cola
            print("📤 Enviando trabajo a la cola...")
            handler = fal_client.submit(
                self.endpoint,
                arguments={
                    **self.default_arguments,
                    "prompt": "a futuristic robot in a cyberpunk city, neon lights"
                }
            )

            request_id = handler.request_id
            print(f"🆔 Request ID: {request_id}")

            # Paso 2: Monitorear el estado
            print("🔍 Monitoreando estado...")
            while True:
                status = fal_client.status(self.endpoint, request_id, with_logs=True)
                print(f"📊 Estado actual: {status.get('status', 'unknown')}")

                if status.get('status') == 'COMPLETED':
                    print("✅ Trabajo completado!")
                    break
                elif status.get('status') == 'FAILED':
                    print("❌ Trabajo falló!")
                    return None

                # Mostrar logs si están disponibles
                if 'logs' in status:
                    for log in status['logs']:
                        print(f"📝 Log: {log.get('message', '')}")

                time.sleep(2)  # Esperar 2 segundos antes de verificar de nuevo

            # Paso 3: Obtener el resultado
            print("📥 Obteniendo resultado...")
            result = fal_client.result(self.endpoint, request_id)

            print("✅ Resultado obtenido:")
            for i, image in enumerate(result.get('images', [])):
                print(f"🖼️  Imagen {i + 1}: {image.get('url', 'No URL')}")

            return result

        except Exception as e:
            print(f"❌ Error en gestión de cola: {e}")
            return None

    def ejemplo_3_file_upload(self):
        """Ejemplo 3: Subida de archivos"""
        print("\n" + "=" * 50)
        print("📁 EJEMPLO 3: Subida de archivos")
        print("=" * 50)

        try:
            # Crear un archivo de prueba (imagen pequeña)
            import base64
            from io import BytesIO

            # Imagen de prueba en base64 (1x1 pixel transparente PNG)
            test_image_data = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU"
                "t6WAAAAABJRU5ErkJggg=="
            )

            # Guardar archivo temporal
            with open("test_image.png", "wb") as f:
                f.write(test_image_data)

            # Subir archivo
            print("📤 Subiendo archivo...")
            file_url = fal_client.upload_file("test_image.png")
            print(f"🔗 URL del archivo subido: {file_url}")

            # Limpiar archivo temporal
            import os
            os.remove("test_image.png")

            return file_url

        except Exception as e:
            print(f"❌ Error en subida de archivo: {e}")
            return None

    def ejemplo_4_streaming(self):
        """Ejemplo 4: Streaming"""
        print("\n" + "=" * 50)
        print("🌊 EJEMPLO 4: Streaming")
        print("=" * 50)

        try:
            print("🔄 Iniciando stream...")
            stream = fal_client.stream(
                self.endpoint,
                arguments={
                    **self.default_arguments,
                    "prompt": "a peaceful landscape with mountains and lake"
                }
            )

            event_count = 0
            for event in stream:
                event_count += 1
                print(f"📦 Evento {event_count}: {type(event).__name__}")

                # Mostrar contenido del evento según su tipo
                if hasattr(event, 'status'):
                    print(f"   Estado: {event.status}")
                if hasattr(event, 'logs'):
                    for log in event.logs:
                        print(f"   📝 Log: {log.get('message', '')}")
                if hasattr(event, 'images'):
                    print(f"   🖼️  Imágenes: {len(event.images)}")

                # Limitar eventos para no saturar la salida
                if event_count > 10:
                    print("... (limitando salida)")
                    break

            print("✅ Stream completado")

        except Exception as e:
            print(f"❌ Error en streaming: {e}")

    def ejemplo_5_run_directo(self):
        """Ejemplo 5: Ejecución directa (no recomendado para producción)"""
        print("\n" + "=" * 50)
        print("⚡ EJEMPLO 5: Ejecución directa (bloqueante)")
        print("=" * 50)
        print("⚠️  Nota: Este método bloquea hasta obtener respuesta")

        try:
            print("🔄 Ejecutando directamente...")
            result = fal_client.run(
                self.endpoint,
                arguments={
                    **self.default_arguments,
                    "prompt": "a simple drawing of a house",
                    "num_images": 1
                }
            )

            print("✅ Resultado obtenido:")
            for i, image in enumerate(result.get('images', [])):
                print(f"🖼️  Imagen {i + 1}: {image.get('url', 'No URL')}")

            return result

        except Exception as e:
            print(f"❌ Error en ejecución directa: {e}")
            return None

    def ejemplo_comparacion_metodos(self):
        """Ejemplo 6: Comparación de métodos"""
        print("\n" + "=" * 50)
        print("📊 EJEMPLO 6: Comparación de métodos")
        print("=" * 50)

        metodos = [
            ("Subscribe (Recomendado)", self.ejemplo_1_subscribe_simple),
            ("Gestión de Cola Manual", self.ejemplo_2_queue_management),
            ("Ejecución Directa", self.ejemplo_5_run_directo)
        ]

        resultados = {}

        for nombre, metodo in metodos:
            print(f"\n🧪 Probando: {nombre}")
            start_time = time.time()

            resultado = metodo()

            end_time = time.time()
            tiempo_transcurrido = end_time - start_time

            resultados[nombre] = {
                'tiempo': tiempo_transcurrido,
                'exitoso': resultado is not None
            }

            print(f"⏱️  Tiempo: {tiempo_transcurrido:.2f} segundos")
            print(f"✅ Exitoso: {'Sí' if resultado else 'No'}")

        # Mostrar resumen
        print("\n" + "=" * 30)
        print("📈 RESUMEN DE COMPARACIÓN")
        print("=" * 30)
        for metodo, datos in resultados.items():
            estado = "✅" if datos['exitoso'] else "❌"
            print(f"{estado} {metodo}: {datos['tiempo']:.2f}s")


def main():
    """Función principal para ejecutar todos los ejemplos"""
    print("🎯 INICIANDO PRUEBAS DE FAL-CLIENT API")
    print("=" * 60)

    # Verificar que la API key está configurada
    import os
    if not os.getenv('FAL_KEY'):
        print("⚠️  ADVERTENCIA: Variable de entorno FAL_KEY no configurada")
        print("   Configúrala con: export FAL_KEY='tu_api_key'")
        print("   O crea un archivo .env con: FAL_KEY=tu_api_key")

    tester = FalClientTester()

    # Ejecutar ejemplos individuales
    ejemplos = [
        ("Ejemplo Subscribe", tester.ejemplo_1_subscribe_simple),
        ("Ejemplo Gestión Cola", tester.ejemplo_2_queue_management),
        ("Ejemplo File Upload", tester.ejemplo_3_file_upload),
        ("Ejemplo Streaming", tester.ejemplo_4_streaming),
        ("Ejemplo Run Directo", tester.ejemplo_5_run_directo),
    ]

    for nombre, ejemplo in ejemplos:
        try:
            print(f"\n🚀 Ejecutando: {nombre}")
            ejemplo()
            print(f"✅ {nombre} completado")
        except Exception as e:
            print(f"❌ Error en {nombre}: {e}")

        # Pausa entre ejemplos
        time.sleep(1)

    # Ejecutar comparación final
    print("\n🏁 EJECUTANDO COMPARACIÓN FINAL...")
    tester.ejemplo_comparacion_metodos()

    print("\n🎉 TODAS LAS PRUEBAS COMPLETADAS")


if __name__ == "__main__":
    main()