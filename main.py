import os
import uuid
import random
import requests
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client, ClientOptions
from dotenv import load_dotenv
from typing import Optional

load_dotenv('.env.prod')

### source venv/bin/activate
### uvicorn main:app --reload

# --- CONFIGURACIÓN DE SUPABASE ---
SUPABASE_URL: str = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_KEY") 
SUPABASE_SERVICE_ROLE: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") 

if not all([SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE]):
    raise RuntimeError("Faltan variables de entorno de Supabase.")

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
    user_id: Optional[str] = None

class HorarioNotificacion(BaseModel):
    hora: str
    zona_horaria: str = "America/Guayaquil"
    activo: bool = True

class RegistroDependiente(BaseModel):
    email: EmailStr
    password: str
    nombre: str

class EnviarCodigoRequest(BaseModel):
    email: EmailStr
    nombre: str
    password: str
    rol: str = "usuario"

class VerificarCodigoRequest(BaseModel):
    email: EmailStr
    codigo: str

# --- DEPENDENCIAS (AUTH OPTIMIZADAS) ---
def get_user_client(authorization: str = Header(...)) -> Client:
    try:
        token = authorization.replace("Bearer ", "")
        opciones = ClientOptions(headers={"Authorization": f"Bearer {token}"})
        return create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=opciones)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido o no proporcionado")

# Ahora reutiliza get_user_client para no duplicar peticiones a Supabase
def get_current_user_id(authorization: str = Header(...), client: Client = Depends(get_user_client)) -> str:
    token = authorization.replace("Bearer ", "")
    try:
        user_response = client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Usuario no autenticado")
        return user_response.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Usuario no autenticado: {str(e)}")

# --- RUTAS DE AUTENTICACIÓN (VERIFICACIÓN DE CORREO) ---
@app.post("/auth/enviar-codigo")
def enviar_codigo(datos: EnviarCodigoRequest):
    try:
        codigo = f"{random.randint(0, 9999):04d}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        supabase_admin.table('codigos_verificacion').insert({
            "email": datos.email,
            "codigo": codigo,
            "nombre": datos.nombre,
            "password": datos.password,
            "rol": datos.rol,
            "expires_at": expires_at.isoformat()
        }).execute()

        brevo_key = os.environ.get("BREVO_API_KEY")
        brevo_from = os.environ.get("BREVO_FROM_EMAIL")
        if brevo_key and brevo_from:
            brevo_response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": brevo_key,
                    "Content-Type": "application/json",
                },
                json={
                    "sender": {"email": brevo_from},
                    "to": [{"email": datos.email}],
                    "subject": "Tu código de verificación",
                    "htmlContent": f"<p>Tu código de verificación es: <strong>{codigo}</strong></p><p>Vence en 10 minutos.</p>",
                },
            )

        return {"mensaje": "Código enviado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/verificar-codigo")
def verificar_codigo(datos: VerificarCodigoRequest):
    try:
        # 1. Buscar el código de verificación
        response = supabase_admin.table('codigos_verificacion').select('*').eq('email', datos.email).eq('codigo', datos.codigo).execute()
        
        if not response.data:
            raise HTTPException(status_code=400, detail="Código o email incorrecto.")

        codigo_entry = response.data[0]
        
        # 2. Validar expiración y estado de verificación
        if datetime.now(timezone.utc) > datetime.fromisoformat(codigo_entry['expires_at']):
            raise HTTPException(status_code=400, detail="Código expirado.")

        if codigo_entry['verificado']:
            raise HTTPException(status_code=400, detail="Código ya verificado.")

        # 3. Marcar código como verificado
        supabase_admin.table('codigos_verificacion').update({"verificado": True}).eq('id', codigo_entry['id']).execute()

        # 4. Crear usuario en Supabase Auth y perfil
        try:
            user = supabase_admin.auth.admin.create_user({
                "email": codigo_entry['email'],
                "password": codigo_entry['password'],
                "email_confirm": True,
                "user_metadata": {  # <--- Agrega esto para alimentar el Trigger de la DB
                    "nombre_completo": codigo_entry['nombre'],
                    "rol": codigo_entry['rol']
                    }
                    })
            nuevo_id = user.user.id
        except Exception as create_err:
            err_str = str(create_err)
            # Si el usuario ya existe, lo buscamos via API REST de GoTrue
            if "Database error creating new user" in err_str:
                resp = requests.get(
                    f"{SUPABASE_URL}/auth/v1/admin/users",
                    headers={
                        "apikey": SUPABASE_SERVICE_ROLE,
                        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE}"
                    },
                    params={"filter": codigo_entry['email']}
                )
                users_data = resp.json()
                users_list = users_data.get("users", [])
                if users_list:
                    nuevo_id = users_list[0]["id"]
                    print(f"DEBUG: Usuario ya existía, usando ID: {nuevo_id}")
                else:
                    raise HTTPException(status_code=400, detail=f"No se pudo crear ni encontrar el usuario: {err_str}")
            else:
                raise HTTPException(status_code=400, detail=f"Error al crear usuario: {err_str}")
        
        supabase_admin.table('perfiles').upsert({
            "id": nuevo_id,
            "email": codigo_entry['email'],
            "rol": codigo_entry['rol'],
            "nombre_completo": codigo_entry['nombre']
        }).execute()

        return {"mensaje": "Email verificado y usuario registrado con éxito", "user_id": nuevo_id}

    except Exception as e:
        print(f"DEBUG ERROR al verificar código: {e}")
        raise HTTPException(status_code=400, detail=f"Database error verifying code/creating user: {str(e)}")

# --- RUTAS DE ADMINISTRACIÓN (TUTORES) ---
@app.post("/admin/crear-dependiente")
def crear_dependiente(
    datos: RegistroDependiente, 
    tutor_id: str = Depends(get_current_user_id)
):
    try:
        # 1. Crear usuario en Auth
        user = supabase_admin.auth.admin.create_user({
            "email": datos.email,
            "password": datos.password,
            "email_confirm": True
        })
        
        nuevo_id = user.user.id
        
        # 2. Usar UPSERT mapeando la columna correcta: nombre_completo
        supabase_admin.table('perfiles').upsert({
            "id": nuevo_id,
            "email": datos.email,
            "rol": "dependiente",
            "tutor_id": tutor_id,
            "nombre_completo": datos.nombre
        }).execute()
        
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
def obtener_estadisticas(
    user_id: Optional[str] = None,
    current_user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_user_client)
):
    try:
        target_user = user_id if user_id else current_user_id
        respuesta = db.table('registros_glucosa').select('*').eq('user_id', target_user).order('created_at', desc=True).execute()
        return respuesta.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- RUTAS DE MEDICAMENTOS ---
@app.get("/medicamentos")
def obtener_medicamentos(
    user_id: Optional[str] = None,
    current_user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_user_client)
):
    try:
        target_user = user_id if user_id else current_user_id
        respuesta = db.table('medicamentos').select('*').eq('user_id', target_user).order('id').execute()
        return respuesta.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/medicamentos")
def agregar_medicamento(
    med: Medicamento,
    current_user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_user_client)
):
    try:
        target_user = med.user_id if med.user_id else current_user_id
        respuesta = db.table('medicamentos').insert({
            "nombre": med.nombre,
            "dosis": med.dosis,
            "instrucciones": med.instrucciones,
            "foto_url": med.foto_url,
            "user_id": target_user
        }).execute()
        return {"mensaje": "Medicamento agregado", "datos": respuesta.data}
    except Exception as e:
        print(f"DEBUG POST /medicamentos error: {e}")
        raise HTTPException(status_code=400, detail=f"Medicamento error: {str(e)}")

@app.put("/medicamentos/{med_id}")
def actualizar_medicamento(
    med_id: int,
    med: Medicamento,
    current_user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_user_client)
):
    try:
        target_user = med.user_id if med.user_id else current_user_id
        respuesta = db.table('medicamentos').update({
            "nombre": med.nombre,
            "dosis": med.dosis,
            "instrucciones": med.instrucciones,
            "foto_url": med.foto_url,
            "user_id": target_user
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

# --- RUTAS DE NOTIFICACIONES ---
@app.get("/notificaciones")
def obtener_notificaciones(
    user_id: Optional[str] = None,
    current_user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_user_client)
):
    try:
        target_user = user_id if user_id else current_user_id
        respuesta = db.table('horarios_notificacion').select('*').eq('user_id', target_user).order('hora').execute()
        return respuesta.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/notificaciones")
def crear_notificacion(horario: HorarioNotificacion, user_id: str = Depends(get_current_user_id), db: Client = Depends(get_user_client)):
    try:
        respuesta = db.table('horarios_notificacion').insert({
            "user_id": user_id,
            "hora": horario.hora,
            "zona_horaria": horario.zona_horaria,
            "activo": horario.activo
        }).execute()
        return {"mensaje": "Horario de notificación creado", "datos": respuesta.data}
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
        print(f"DEBUG upload-foto error: {e}")
        raise HTTPException(status_code=400, detail=f"Upload error: {str(e)}")