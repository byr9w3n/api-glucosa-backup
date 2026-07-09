import os
from supabase import create_client, Client
# Opcional: Para cargar variables desde un archivo .env si lo tienes en la carpeta
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 1. Configura tus credenciales de Supabase desde las variables de entorno
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

def limpiar_tablas():
    # Validación simple para que no falle silenciosamente si faltan las variables
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Error: SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no están configuradas.")
        return

    try:
        # Inicializar el cliente de Supabase
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        print("⏳ Conectando y vaciando tablas en Supabase de forma automática...")
        
        # Borrado por API (De abajo hacia arriba para respetar las llaves foráneas)
        # Usamos .is_("not.null", True) o .neq() numérico para evitar conflictos de tipos
        supabase.table("registros_glucosa").delete().neq("id", -1).execute()
        supabase.table("horarios_notificacion").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        supabase.table("codigos_verificacion").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        supabase.table("perfiles").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

        print("✅ ¡Tablas limpiadas por completo con éxito!")
        
    except Exception as e:
        print(f"❌ Ocurrió un error al intentar limpiar las tablas: {e}")

if __name__ == "__main__":
    # Se ejecuta directamente sin preguntar nada en la terminal
    limpiar_tablas()