# Pruebas con curl

```bash
API=https://forgeops.arvislab.com/ig/api/cuentas
AM=https://forgeops.arvislab.com/am/oauth2      # realm raíz /
ORIGEN=https://mibanco.arvislab.com
```

## 1. Obtener un token de prueba

El cliente `mibanco-web` es público y usa PKCE, así que no se puede pedir un token con un
solo `curl`. Hay dos opciones.

**A. Recomendada: copiarlo desde el navegador.** Inicia sesión en la app, abre DevTools →
*Application* → *Session Storage* → `https://mibanco.arvislab.com`, busca la clave
`oidc.user:<authority>:mibanco-web` y copia `access_token`. También puedes ejecutar esto en la
consola:

```js
JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k => k.startsWith('oidc.user:')))).access_token
```

```bash
TOKEN='<pegar aquí>'
```

**B. Cliente temporal con contraseña (solo laboratorio).** Crea en el realm raíz un cliente
confidencial `mibanco-cli-pruebas` con el grant *Resource Owner Password Credentials* y el
scope `cuentas.read`. Bórralo después.

```bash
TOKEN=$(curl -s -u 'mibanco-cli-pruebas:<secret>' \
  -d grant_type=password -d username=ana.torres -d 'password=<clave>' \
  -d 'scope=openid cuentas.read' \
  "$AM/access_token" | jq -r .access_token)
```

## 2. Confirmar el campo del usuario en la introspección

✅ **Verificado (01/11/2026):** la ruta copia `info.sub` en `X-Usuario`. En este AM, `sub`
(igual que `user_id`, `username` y `subname`) es el UUID del usuario, no su nombre. Para
comprobarlo con tu token:

```bash
curl -s -u 'mibanco-ig-introspect:<secret>' -d "token=$TOKEN" "$AM/introspect" | jq '{active, scope, client_id, sub}'
```

- Espera `"active": true`, `"scope"` con `cuentas.read` y `"sub"` con un UUID.
- Si responde `"active": false` con un token recién emitido, al cliente de introspección le
  falta el scope `am-introspect-all-tokens`.
- Prueba rápida antes de crear `mibanco-ig-introspect`: el cliente `resource-server` de la
  ruta de ejemplo de forgeops usa como clave el valor de `agent.password` de `config.json`
  (`-u 'resource-server:<clave>'`). Si AM lo rechaza, ese cliente no existe o tiene otra
  clave, y no afecta a la demo.

## 3. Preflight CORS (sin token): espera 200 y cabeceras CORS

```bash
curl -si -X OPTIONS "$API" \
  -H "Origin: $ORIGEN" \
  -H 'Access-Control-Request-Method: GET' \
  -H 'Access-Control-Request-Headers: authorization' | sed -n '1,20p'
```

Debe incluir `Access-Control-Allow-Origin: https://mibanco.arvislab.com` y
`Access-Control-Allow-Methods` con `GET`. No debe ser un 401: eso significaría que el
preflight llegó al filtro de OAuth2.

Con un origen no permitido (`-H 'Origin: https://evil.example'`) espera **403**, la
respuesta por defecto de `CorsFilter`.

## 4. Sin token: espera 401

```bash
curl -si "$API" -H "Origin: $ORIGEN" | sed -n '1,15p'
```

Espera `HTTP/1.1 401` y `WWW-Authenticate: Bearer realm="mibanco"`.

## 5. Token válido: espera 200 con solo los datos del usuario

```bash
curl -s "$API" -H "Authorization: Bearer $TOKEN" | jq
CUENTA=$(curl -s "$API" -H "Authorization: Bearer $TOKEN" | jq -r '.cuentas[0].id')
curl -s "$API/$CUENTA/movimientos" -H "Authorization: Bearer $TOKEN" | jq '.movimientos[:3]'
```

## 6. Token inválido o vencido: espera 401

```bash
curl -si "$API" -H 'Authorization: Bearer token-inventado' | sed -n '1,15p'
```

Espera 401 con `WWW-Authenticate: Bearer realm="mibanco", error="invalid_token"`. Un token
vencido da el mismo resultado. Ten en cuenta que IG cachea tokens válidos hasta 5 minutos
(`cache.maxTimeout`), así que un token **revocado** puede seguir aceptándose ese tiempo.

## 7. Controles extra

```bash
# Cuenta de otro usuario: espera 404 (usa un id de cuenta obtenido con el token de otro usuario)
curl -si "$API/<id-de-cuenta-de-otro-usuario>/movimientos" -H "Authorization: Bearer $TOKEN" | head -1

# Suplantar X-Usuario no sirve: IG borra la cabecera del cliente. Espera tus propias cuentas
curl -s "$API" -H "Authorization: Bearer $TOKEN" -H 'X-Usuario: otro-usuario' | jq '.cuentas[].id'
```

Un token **sin** el scope `cuentas.read` recibe **403** (`insufficient_scope`), según la
documentación de `OAuth2ResourceServerFilter`. No es un 401.

## 8. Confirmar que el backend no recibió las peticiones rechazadas

```bash
kubectl -n lab logs deploy/mibanco-cuentas-api --since=10m | grep 'GET /api'
```

Solo deben aparecer las peticiones de los pasos 5 y 7. Las de los pasos 3, 4 y 6 no deben
figurar.

## 9. Pruebas unitarias del backend (local)

```bash
uv sync
uv run pytest -q
```
