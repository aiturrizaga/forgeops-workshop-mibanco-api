# MiBanco demo · API de cuentas (FastAPI)

Servicio de cuentas mock protegido por **PingGateway** (validación de token por
introspección en **Access Management**) dentro de ForgeOps 2026.3.2.

```
Navegador ──Bearer──▶ ingress-nginx ──/ig (se quita)──▶ PingGateway ──X-Usuario──▶ mibanco-cuentas-api (ClusterIP)
                                                         │ introspección
                                                         ▼
                                                         AM (realm raíz /)
```

> **Seguridad:** el servicio **no valida tokens**. Confía en la cabecera `X-Usuario` que
> agrega IG después de validar el token. Esto solo es seguro porque el servicio no tiene
> Ingress ni es accesible desde Internet, y porque la ruta de IG borra cualquier `X-Usuario`
> que envíe el cliente.

## Endpoints

| Método y ruta | Descripción |
|---|---|
| `GET /api/cuentas` | Cuentas del usuario de `X-Usuario` (401 si falta la cabecera) |
| `GET /api/cuentas/{id}/movimientos` | Cuenta y movimientos, del más reciente al más antiguo. Una cuenta de otro usuario o inexistente da **404** |
| `GET /health` | Probe de Kubernetes (no se expone por IG) |

## Estructura

```
app/
  main.py                 app, routers y manejo de errores
  core/config.py          configuración (variables CUENTAS_*)
  core/exceptions.py      errores de dominio
  api/dependencies.py     usuario actual (X-Usuario) y servicio
  api/routers/            cuentas.py, health.py
  models/                 entidades de dominio (dataclasses)
  schemas/                modelos Pydantic de salida
  services/               lógica de negocio
  repositories/           interfaz (Protocol), SQLite y carga de plantillas
data/plantillas.json      plantillas de datos demo (personal, familiar, negocio)
var/cuentas.db            base SQLite (se crea sola; no se versiona)
tests/                    pytest (servicios y endpoints)
ig/                       ruta de PingGateway e imagen derivada de IG
k8s/                      PVC (SQLite), Deployment, Service, NetworkPolicy opcional y plantilla de Secret
docs/                     DESPLIEGUE, CONFIG_AM, PRUEBAS y DIAGNOSTICO
pyproject.toml, uv.lock   dependencias (uv) y configuración de pytest
```

## Desarrollo local

Las dependencias se gestionan con **uv**: `pyproject.toml` (dependencias de runtime y
grupo `dev`) y `uv.lock` (versiones exactas). Para añadir una: `uv add <paquete>`, o
`uv add --dev <paquete>` si es solo para desarrollo.

```bash
# Requiere uv (https://docs.astral.sh/uv/). Crea .venv e instala según uv.lock
uv sync
uv run pytest -q
uv run uvicorn app.main:app --reload
# Cualquier valor sirve como usuario: el primer acceso lo crea con datos demo
curl -H 'X-Usuario: usuario-prueba-1' http://localhost:8000/api/cuentas
```

| Variable | Valor por defecto |
|---|---|
| `CUENTAS_PLANTILLAS_PATH` | `data/plantillas.json` |
| `CUENTAS_DATABASE_PATH` | `var/cuentas.db` (en la imagen: `/srv/var/cuentas.db`) |
| `CUENTAS_USUARIO_HEADER` | `X-Usuario` |
| `CUENTAS_LOG_LEVEL` | `INFO` |

## Usuarios y datos (SQLite)

El backend no tiene una lista fija de usuarios. En cada llamada, `get_usuario_actual` registra
el acceso del `sub` que llega en `X-Usuario`:

- **Primer acceso:** crea el usuario y le copia una plantilla de `data/plantillas.json`, elegida
  de forma determinista por su `sub`, con identificadores y números de cuenta nuevos y fechas
  recientes. Todo en una transacción `BEGIN IMMEDIATE`, así dos peticiones simultáneas no
  duplican datos.
- **Siguientes accesos:** actualiza `ultimo_acceso` y el contador `accesos`; las cuentas no cambian.

Así, cualquier usuario nuevo creado en AM puede entrar sin tocar el backend. SQLite es solo para
la demo (una réplica). Para usar otra base, implementa `CuentasRepository`
(`app/repositories/base.py`) y úsala en `get_cuentas_service`.

## Despliegue

Ver [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md). El frontend está en el repositorio hermano
`forgeops-workshop-frontend`.
