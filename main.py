import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI(title="API Control Glucosa")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DATOS ---
class RegistroGlucosa(BaseModel):
    valor: int
    etiqueta: str
    notas: Optional[str] = ""

class Medicamento(BaseModel):
    nombre: str
    dosis: str
    instrucciones: Optional[str] = ""

# --- RUTAS DE SALUD Y GLUCOSA ---
@app.get("/")
def health_check():
    return {"status": "online", "mensaje": "El servidor está despierto"}

@app.post("/registro")
def crear_registro(registro: RegistroGlucosa):
    try:
        data, count = supabase.table('registros_glucosa').insert({
            "valor": registro.valor,
            "etiqueta": registro.etiqueta,
            "notas": registro.notas
        }).execute()
        return {"mensaje": "Registro guardado exitosamente", "datos": data[1]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/estadisticas")
def obtener_estadisticas():
    try:
        data, count = supabase.table('registros_glucosa').select('*').order('created_at', desc=True).execute()
        return data[1]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- NUEVAS RUTAS DE MEDICAMENTOS ---

@app.get("/medicamentos")
def obtener_medicamentos():
    try:
        data, count = supabase.table('medicamentos').select('*').order('id').execute()
        return data[1]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/medicamentos")
def agregar_medicamento(med: Medicamento):
    try:
        data, count = supabase.table('medicamentos').insert({
            "nombre": med.nombre,
            "dosis": med.dosis,
            "instrucciones": med.instrucciones
        }).execute()
        return {"mensaje": "Medicamento agregado", "datos": data[1]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/medicamentos/{id}")
def actualizar_medicamento(id: int, med: Medicamento):
    try:
        data, count = supabase.table('medicamentos').update({
            "nombre": med.nombre,
            "dosis": med.dosis,
            "instrucciones": med.instrucciones
        }).eq('id', id).execute()
        return {"mensaje": "Medicamento actualizado", "datos": data[1]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/medicamentos/{id}")
def eliminar_medicamento(id: int):
    try:
        data, count = supabase.table('medicamentos').delete().eq('id', id).execute()
        return {"mensaje": "Medicamento eliminado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))