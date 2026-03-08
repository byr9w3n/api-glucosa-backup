import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional

# 1. Cargar las variables ocultas del archivo .env
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# 2. Inicializar la aplicación FastAPI
app = FastAPI(title="API Control Glucosa")

# 3. Configurar CORS (Vital para que tu web en Vue se pueda comunicar con este backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Cuando subas a producción, cambiaremos el "*" por la URL de tu web
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Crear el modelo de datos esperado desde el celular de tu mamá
class RegistroGlucosa(BaseModel):
    valor: int
    etiqueta: str
    notas: Optional[str] = ""

# 5. RUTA 1: El "Despertador" (Para que Cron-job.org lo mantenga gratis 24/7)
@app.get("/")
def health_check():
    return {"status": "online", "mensaje": "El servidor está despierto"}

# 6. RUTA 2: Guardar un nuevo registro (Lo que usará tu mamá)
@app.post("/registro")
def crear_registro(registro: RegistroGlucosa):
    try:
        # Insertamos en la tabla de Supabase
        data, count = supabase.table('registros_glucosa').insert({
            "valor": registro.valor,
            "etiqueta": registro.etiqueta,
            "notas": registro.notas
            # No enviamos 'created_at' porque Supabase lo pone solo con now()
        }).execute()
        
        return {"mensaje": "Registro guardado exitosamente", "datos": data[1]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 7. RUTA 3: Obtener estadísticas (Para tu vista de control)
@app.get("/estadisticas")
def obtener_estadisticas():
    try:
        # Traemos todos los registros ordenados desde el más reciente
        data, count = supabase.table('registros_glucosa').select('*').order('created_at', desc=True).execute()
        return data[1]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))