import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

# Cargar variables de entorno desde el archivo .env
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE:
    print("❌ Error: Faltan credenciales de Supabase en el archivo .env")
    exit(1)

# Cliente con Service Role para saltarse políticas RLS al definir fechas históricas
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)

def generar_datos_usuario_especifico():
    # Configuración requerida por el usuario
    USER_ID = "a70ebd29-0dd4-4da6-b743-6ab7a513005a"
    FECHA_FINAL = datetime(2026, 7, 8)  # Límite estricto: 8 de julio de 2026
    DIAS_HISTORIAL = 60                # 2 meses de antigüedad (~60 días)
    
    print(f"🚀 Iniciando simulación de glucosa para el usuario independiente: {USER_ID}")
    fecha_inicio = FECHA_FINAL - timedelta(days=DIAS_HISTORIAL)
    print(f"📅 Período: Desde {fecha_inicio.strftime('%Y-%m-%d')} hasta {FECHA_FINAL.strftime('%Y-%m-%d')} ({DIAS_HISTORIAL} días)\n")
    
    etiquetas_base = ["Ayunas", "Pre-Merienda", "Post-Comida", "Antes de dormir"]
    registros_a_insertar = []

    # Recorremos desde los 60 días atrás hasta el día objetivo (8 de Julio)
    for dia_hacia_atras in range(DIAS_HISTORIAL, -1, -1):
        fecha_simulada = FECHA_FINAL - timedelta(days=dia_hacia_atras)
        
        # Cada día tendrá entre 2 y 4 mediciones aleatorias
        num_mediciones = random.randint(2, 4)
        etiquetas_dia = random.sample(etiquetas_base, num_mediciones)
        
        for etiqueta in etiquetas_dia:
            # 1. Valores de glucosa lógicos y ventanas de tiempo adecuadas
            if etiqueta == "Ayunas":
                valor = random.randint(75, 130)
                hora_min, hora_max = 6, 9       # Mañana temprano
            elif etiqueta == "Post-Comida":
                valor = random.randint(110, 210) # Picos postprandiales
                hora_min, hora_max = 14, 16     # Después de comer
            elif etiqueta == "Pre-Merienda":
                valor = random.randint(90, 160)
                hora_min, hora_max = 18, 20     # Tarde / Atardecer
            else:  # Antes de dormir
                valor = random.randint(90, 150)
                hora_min, hora_max = 21, 23     # Noche
            
            # 2. Notas ocasionales realistas (20% de probabilidad)
            if random.random() > 0.8:
                notas = random.choice([
                    "Me siento un poco cansado", 
                    "Comí un postre", 
                    "Día de mucho estrés", 
                    "Hice ejercicio en la mañana", 
                    "Todo normal"
                ])
            else:
                notas = "Sin observaciones"

            # 3. Forzar hora coherente con la etiqueta del momento del día
            hora_exacta = fecha_simulada.replace(
                hour=random.randint(hora_min, hora_max), 
                minute=random.randint(0, 59),
                second=0,
                microsecond=0
            )

            # 4. Estructura exacta alineada con la tabla public.registros_glucosa
            registros_a_insertar.append({
                "user_id": USER_ID,                          # uuid -> FK a public.perfiles
                "valor": valor,                              # bigint
                "etiqueta": etiqueta,                        # text
                "notas": notas,                              # text
                "created_at": hora_exacta.isoformat()        # timestamp with time zone (forzado)
            })

    # Inserción masiva en un solo lote eficiente (Bulk Insert)
    if registros_a_insertar:
        try:
            print(f"📦 Preparados {len(registros_a_insertar)} registros de glucosa.")
            print("⏳ Enviando lote completo a Supabase...")
            
            # Ejecuta la inserción masiva en la tabla correspondiente
            supabase_admin.table('registros_glucosa').insert(registros_a_insertar).execute()
            
            print(f"\n✅ ¡Éxito absoluto! Se poblaron {len(registros_a_insertar)} registros en 'registros_glucosa'.")
            print(f"👤 Vinculados al usuario ID: {USER_ID}")
        except Exception as e:
            print(f"\n❌ Error crítico durante la inserción en la base de datos: {e}")
            print("💡 Nota técnica: Asegúrate de que el registro del usuario con ese UUID ya exista previamente en la tabla 'public.perfiles' debido a la restricción Foreign Key.")

if __name__ == "__main__":
    generar_datos_usuario_especifico()