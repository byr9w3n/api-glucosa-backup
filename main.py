import os
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client, ClientOptions
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional

### source venv/bin/activate
### uvicorn main:app --reload

load_dotenv()

# --- CONFIGURACIÓN DE SUPABASE ---
SUPABASE_URL: str = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_KEY") 
SUPABASE_SERVICE_ROLE: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") 

# Cliente global de administrador (SALTA EL RLS - Usar con cuidado)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)

app = FastAPI(title="API Control Glucosa Med2Gestion")

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
    notas: Optional[str] = "Sin observaciones"

class Medicamento(BaseModel):
    nombre: str
    dosis: str
    instrucciones: Optional[str] = ""
    foto_url: Optional[str] = ""

class RegistroDependiente(BaseModel):
    email: EmailStr
    password: str
    nombre: str

# --- DEPENDENCIAS (AUTH) ---
def get_user_client(authorization: str = Header(...)) -> Client:
    try:
        token = authorization.replace("Bearer ", "")
        # ¡LA MAGIA AQUÍ! Las cabeceras se inyectan al crear las opciones
        opciones = ClientOptions(headers={"Authorization": f"Bearer {token}"})

        # Pasamos las opciones en el mismo instante en que nace el cliente
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=opciones)
        return client
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido o no proporcionado")

def get_current_user_id(authorization: str = Header(...)) -> str:
    token = authorization.replace("Bearer ", "")
    client = get_user_client(authorization)
    try:
        user_response = client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Usuario no autenticado")
        return user_response.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Usuario no autenticado: {str(e)}")

# --- RUTAS DE ADMINISTRACIÓN (TUTORES) ---
@app.post("/admin/crear-dependiente")
def crear_dependiente(
    datos: RegistroDependiente, 
    tutor_id: str = Depends(get_current_user_id)
):
    try:
        user = supabase_admin.auth.admin.create_user({
            "email": datos.email,
            "password": datos.password,
            "email_confirm": True
        })
        
        nuevo_id = user.user.id
        
        supabase_admin.table('perfiles').update({
            "rol": "dependiente",
            "tutor_id": tutor_id,
            "nombre_completo": datos.nombre
        }).eq("id", nuevo_id).execute()
        
        return {"mensaje": "Cuenta de dependiente creada con éxito", "dependiente_id": nuevo_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- RUTAS DE GLUCOSA ---
@app.post("/registro")
def crear_registro(
    registro: RegistroGlucosa, 
    user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_user_client)
):
    try:
        # CORRECCIÓN: Guardar el objeto de respuesta entero
        respuesta = db.table('registros_glucosa').insert({
            "valor": registro.valor,
            "etiqueta": registro.etiqueta,
            "notas": registro.notas,
            "user_id": user_id 
        }).execute()
        
        return {"mensaje": "Registro guardado exitosamente", "datos": respuesta.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/estadisticas")
def obtener_estadisticas(db: Client = Depends(get_user_client)):
    try:
        # CORRECCIÓN: Acceder directamente a .data
        respuesta = db.table('registros_glucosa').select('*').order('created_at', desc=True).execute()
        return respuesta.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- RUTAS DE MEDICAMENTOS ---
@app.get("/medicamentos")
def obtener_medicamentos(db: Client = Depends(get_user_client)):
    try:
        # CORRECCIÓN: Acceder directamente a .data
        respuesta = db.table('medicamentos').select('*').order('id').execute()
        return respuesta.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/medicamentos")
def agregar_medicamento(
    med: Medicamento, 
    user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_user_client)
):
    try:
        # CORRECCIÓN: Guardar el objeto de respuesta entero
        respuesta = db.table('medicamentos').insert({
            "nombre": med.nombre,
            "dosis": med.dosis,
            "instrucciones": med.instrucciones,
            "foto_url": med.foto_url,
            "user_id": user_id
        }).execute()
        return {"mensaje": "Medicamento agregado", "datos": respuesta.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/medicamentos/{med_id}")
def actualizar_medicamento(med_id: int, med: Medicamento, db: Client = Depends(get_user_client)):
    try:
        respuesta = db.table('medicamentos').update({
            "nombre": med.nombre,
            "dosis": med.dosis,
            "instrucciones": med.instrucciones,
            "foto_url": med.foto_url
        }).eq("id", med_id).execute()
        return {"mensaje": "Actualizado", "datos": respuesta.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/medicamentos/{med_id}")
def eliminar_medicamento(med_id: int, db: Client = Depends(get_user_client)):
    try:
        db.table('medicamentos').delete().eq("id", med_id).execute()
        return {"mensaje": "Eliminado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- RUTAS DE ARCHIVOS ---
@app.post("/upload-foto")
async def upload_foto(
    file: UploadFile = File(...),
    db: Client = Depends(get_user_client)
):
    try:
        contents = await file.read()
        extension = file.filename.split(".")[-1]
        nombre_unico = f"{uuid.uuid4()}.{extension}"
        
        db.storage.from_("fotos_medicinas").upload(
            path=nombre_unico, 
            file=contents, 
            file_options={"content-type": file.content_type}
        )
        
        url_publica = db.storage.from_("fotos_medicinas").get_public_url(nombre_unico)
        return {"url": url_publica}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))