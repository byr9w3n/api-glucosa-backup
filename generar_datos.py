import os
import argparse
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
# Usamos el Service Role para poder insertar fechas personalizadas (históricas) sin que RLS nos bloquee
SUPABASE_SERVICE_ROLE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE:
    print("❌ Error: Faltan credenciales de Supabase en el archivo .env")
    exit(1)

supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)

def generar_datos(user_id: str, dias: int):
    print(f"🚀 Iniciando simulación para el usuario: {user_id}")
    print(f"📅 Generando historial de {dias} días...\n")
    
    etiquetas_base = ["Ayunas", "Pre-Merienda", "Post-Comida", "Antes de dormir"]
    fecha_actual = datetime.now()
    registros_insertados = 0

    for dia_hacia_atras in range(dias, -1, -1):
        fecha_simulada = fecha_actual - timedelta(days=dia_hacia_atras)
        
        # Simularemos entre 2 y 4 mediciones por día
        num_mediciones = random.randint(2, 4)
        etiquetas_dia = random.sample(etiquetas_base, num_mediciones)
        
        for etiqueta in etiquetas_dia:
            # Lógica para generar valores realistas según el momento
            if etiqueta == "Ayunas":
                valor = random.randint(75, 130)
            elif etiqueta == "Post-Comida":
                valor = random.randint(110, 210)  # Picos más altos
            else:
                valor = random.randint(90, 160)
            
            # Agregamos algunas notas aleatorias ocasionalmente
            notas = ""
            if random.random() > 0.8: # 20% de probabilidad de tener nota
                notas = random.choice([
                    "Me siento un poco cansado", 
                    "Comí un postre", 
                    "Día de mucho estrés", 
                    "Hice ejercicio en la mañana", 
                    "Todo normal"
                ])
            else:
                notas = "Sin observaciones"

            # Variar un poco las horas para que no todas sean a la misma hora exacta
            hora_simulada = fecha_simulada.replace(
                hour=random.randint(6, 22), 
                minute=random.randint(0, 59)
            )

            # Insertar en Supabase
            try:
                supabase_admin.table('registros_glucosa').insert({
                    "user_id": user_id,
                    "valor": valor,
                    "etiqueta": etiqueta,
                    "notas": notas,
                    "created_at": hora_simulada.isoformat() # Forzamos la fecha histórica
                }).execute()
                registros_insertados += 1
            except Exception as e:
                print(f"Error insertando dato: {e}")

    print(f"✅ ¡Éxito! Se insertaron {registros_insertados} registros simulados.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de historial de glucosa simulado.")
    parser.add_argument("-u", "--user", required=True, help="El ID (UUID) del usuario en Supabase.")
    parser.add_argument("-d", "--dias", type=int, default=90, help="Cantidad de días de historial a generar (por defecto: 90).")
    
    args = parser.parse_args()
    
    generar_datos(args.user, args.dias)