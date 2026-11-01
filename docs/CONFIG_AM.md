# Configuración de Access Management (guía; no ejecutada)

Todo se configura en el **realm raíz (`/`, *Top Level Realm*)**. Nada de esto lo ejecuté
yo; son pasos a seguir.

## Opción recomendada: script por terminal (API REST de AM)

`scripts/configurar-am.sh` hace los pasos 2, 4 y 5 en una sola ejecución:

- crea o reemplaza los clientes `mibanco-web` y `mibanco-ig-introspect`;
- crea el Secret de Kubernetes `mibanco-ig-introspect`, o reutiliza su clave si ya existe;
- opcionalmente, crea los usuarios de prueba;
- al final muestra la configuración guardada y prueba la introspección.

Inicia sesión como `amadmin` con la clave que lee de `am-env-secrets` (no la imprime) y
cierra la sesión al terminar.

La Platform UI no sirve para crear estos clientes en el realm raíz: *OAuth2 Clients* solo
lista, y *Applications* exige un *Owner* que no existe en este realm.

```bash
cd ~/mibanco/forgeops-workshop-backend
bash scripts/configurar-am.sh                                   # solo clientes y Secret
PASSWORD_USUARIOS='<clave de prueba>' bash scripts/configurar-am.sh   # además, usuarios
```

Requiere `curl`, `jq`, `kubectl` y `openssl` en la VM. ⚠️ Usa el formato
`{"inherited": false, "value": ...}` documentado para `realm-config/agents/OAuth2Client`
(PingAM 8). Si AM rechaza alguna propiedad, el script muestra el error y se detiene.
Revisa la sección «Configuración guardada en AM» de su salida.

Las secciones siguientes describen los mismos pasos en la consola web
(`https://forgeops.arvislab.com/am/ui-admin/`), por si prefieres hacerlo a mano o quieres
revisar lo que hizo el script.

| Estado | Significado |
|---|---|
| ✅ Verificado | Confirmado en la VM, en el repositorio forgeops 2026.3.2 o en la documentación de PingGateway 2026 |
| ⚠️ Supuesto | Basado en el comportamiento habitual de AM; hay que confirmarlo en el entorno |

## 1. Realm y discovery ✅

El realm `alpha` no existe en este despliegue (`Realm not found`). Se usa el realm raíz:

```bash
curl -s https://forgeops.arvislab.com/am/oauth2/.well-known/openid-configuration | jq '{issuer, introspection_endpoint, end_session_endpoint, code_challenge_methods_supported}'
```

| Dato | Valor (verificado en la VM) |
|---|---|
| `issuer` = `VITE_OIDC_AUTHORITY` | `https://forgeops.arvislab.com/am/oauth2` |
| Introspección pública | `https://forgeops.arvislab.com/am/oauth2/introspect` |
| Introspección desde IG (interna) | `&{am.url}/oauth2/introspect` → `http://am/am/oauth2/introspect` |
| `end_session_endpoint` | `https://forgeops.arvislab.com/am/oauth2/connect/endSession` |

Comprueba también que `code_challenge_methods_supported` incluya `S256`.

## 2. Cliente público de la SPA: `mibanco-web`

**Consola de AM** → *Top Level Realm* → *Applications* → *OAuth 2.0* → *Clients* → *Add Client*:

| Campo | Valor |
|---|---|
| Client ID | `mibanco-web` |
| Client secret | (vacío) |
| Redirection URIs | `https://mibanco.arvislab.com/callback` (y `http://localhost:5173/callback` si vas a desarrollar en local) |
| Scope(s) | `openid`, `profile`, `cuentas.read` |
| Default Scope(s) | `openid` |

Después de crearlo:

- **Core** → *Client type*: `Public`.
- **Advanced** → *Grant Types*: `Authorization Code` (opcional: `Refresh Token`).
- **Advanced** → *Response Types*: `code`.
- **Advanced** → *Token Endpoint Authentication Method*: `none`.
- **Advanced** → *Implied consent*: activado, para que no aparezca la pantalla de consentimiento.
- **OpenID Connect** → *Post Logout Redirect URIs*: `https://mibanco.arvislab.com/`.
- PKCE: en *Services* → *OAuth2 Provider* → *Advanced* → *Code Verifier Parameter Required*,
  usa `public` (o `all`). Con `false` funciona igual, porque la SPA siempre envía PKCE, pero
  AM no lo exigiría.

CORS para `https://mibanco.arvislab.com`: ya está configurado en AM según el enunciado
(⚠️ no lo verifiqué). Lo necesitan el discovery, el endpoint de token y `endSession`.

## 3. Scope `cuentas.read`

En AM basta con añadirlo a *Scope(s)* del cliente (paso 2). Comprueba que el *OAuth2
Provider* del realm **no** tenga activado *Use Policy Engine for Scope decisions*; si lo
tiene, hace falta además una política que permita el scope. (⚠️ supuesto: valor por defecto
desactivado.)

## 4. Cliente de introspección para IG: `mibanco-ig-introspect`

La ruta de IG llama a `&{am.url}/oauth2/introspect` con autenticación *client_secret_basic*
(filtro `ClientSecretBasicAuthenticationFilter`, el mismo que usa la ruta de ejemplo
`03-rs-tokenintrospect.json` de forgeops ✅).

**Consola de AM** → *Top Level Realm* → *OAuth 2.0* → *Clients* → *Add Client*:

| Campo | Valor |
|---|---|
| Client ID | `mibanco-ig-introspect` |
| Client secret | uno largo y aleatorio, por ejemplo `openssl rand -base64 32` |
| Scope(s) | `am-introspect-all-tokens` |

- **Core** → *Client type*: `Confidential`.
- **Advanced** → *Grant Types*: `Client Credentials`.
- **Advanced** → *Token Endpoint Authentication Method*: `client_secret_basic`.

⚠️ El scope `am-introspect-all-tokens` permite a este cliente introspeccionar tokens
emitidos para **otros** clientes (aquí, `mibanco-web`). Sin él, AM responde
`{"active": false}` y la API devuelve 401 siempre. Confírmalo en la documentación de AM de
tu versión.

> ℹ️ La ruta de ejemplo de forgeops usa el cliente `resource-server`, con la clave
> `agent.password` de `config.json`, contra este mismo realm. No lo reutilizo porque esa
> clave es pública y la pide el enunciado que el secret esté en un Secret de Kubernetes.
> Para una prueba rápida de introspección sí sirve (ver PRUEBAS.md, paso 2).

Guarda el secret en Kubernetes (nunca en el repositorio):

```bash
kubectl -n lab create secret generic mibanco-ig-introspect \
  --from-literal=MIBANCO_IG_INTROSPECT_SECRET='<secret del paso anterior>'
```

IG lo lee con `SystemAndEnvSecretStore` en formato `PLAIN`. El id
`mibanco.ig.introspect.secret` se busca como variable `MIBANCO_IG_INTROSPECT_SECRET` (puntos
convertidos en guiones bajos y en mayúsculas ✅ documentación PingGateway 2026). La variable
llega al Pod con `envFrom` (DESPLIEGUE.md, paso 6).

## 5. Usuarios de prueba

Cualquier usuario del Top Level Realm puede usar la demo: el backend lo da de alta con datos
demo en su primer acceso (SQLite; ver README del backend). Los usuarios `ana.torres`,
`luis.quispe` y `carla.mendoza` ya se crearon por REST (✅ 01/11/2026).

Para crear otro usuario de prueba: *Top Level Realm* → *Identities* → *Add Identity* en la
consola nativa, o el comando REST del paso 9 de la guía por terminal. Rellena *First Name* y
*Last Name*: el frontend muestra `name`, o `given_name` + `family_name`, del perfil OIDC.

✅ **Verificado (01/11/2026):** en este AM, la introspección devuelve **el mismo UUID** en
`user_id`, `username`, `sub` y `subname` (por ejemplo `f71ef34c-…` para `ana.torres`); el
nombre de usuario no aparece. Por eso la ruta envía `info.sub` en `X-Usuario`, y el backend
usa ese UUID como identificador estable del usuario.
