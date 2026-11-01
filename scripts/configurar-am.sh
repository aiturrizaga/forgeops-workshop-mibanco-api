#!/usr/bin/env bash
# Configura Access Management (Top Level Realm "/") para la demo por su API REST:
#   1. cliente público  mibanco-web           (SPA: Authorization Code + PKCE)
#   2. cliente confidencial mibanco-ig-introspect (IG: introspección de tokens)
#      y el Secret de Kubernetes mibanco-ig-introspect con su clave
#   3. (opcional) usuarios de prueba ana.torres, luis.quispe y carla.mendoza
#
# Uso (en la VM, con kubectl apuntando al clúster):
#   ./scripts/configurar-am.sh
#   PASSWORD_USUARIOS='<clave de prueba>' ./scripts/configurar-am.sh   # también crea usuarios
#
# Es idempotente: PUT crea o reemplaza los clientes, y la clave del cliente de
# introspección se reutiliza si el Secret ya existe.
# Formato del API: docs.pingidentity.com/pingam/8 (rest-api-oauth2-client-admin-endpoint).
set -euo pipefail

AM="${AM:-https://forgeops.arvislab.com/am}"
NS="${NS:-lab}"
REALM_PATH="realms/root"
WEB_ORIGENES=("https://mibanco.arvislab.com" "http://localhost:5173")

for cmd in curl jq kubectl openssl; do
  command -v "$cmd" >/dev/null || { echo "Falta el comando: $cmd" >&2; exit 1; }
done

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# --- Sesión de administrador (la clave se lee del Secret; no se imprime) ---
ADMIN_PASS=$(kubectl -n "$NS" get secret am-env-secrets \
  -o jsonpath='{.data.AM_PASSWORDS_AMADMIN_CLEAR}' | base64 -d)
COOKIE=$(curl -fsS "$AM/json/serverinfo/*" | jq -r '.cookieName')
TOKEN=$(curl -fsS -X POST "$AM/json/$REALM_PATH/authenticate" \
  -H 'Content-Type: application/json' \
  -H 'Accept-API-Version: resource=2.0, protocol=1.0' \
  -H 'X-OpenAM-Username: amadmin' \
  -H "X-OpenAM-Password: $ADMIN_PASS" \
  -d '{}' | jq -r '.tokenId')
unset ADMIN_PASS
[[ -n "$TOKEN" && "$TOKEN" != "null" ]] || { echo "No se pudo autenticar como amadmin" >&2; exit 1; }
echo "✔ Sesión de amadmin iniciada (cookie $COOKIE)"

cerrar_sesion() {
  curl -fsS -o /dev/null -X POST "$AM/json/$REALM_PATH/sessions?_action=logout" \
    -H "$COOKIE: $TOKEN" -H 'Accept-API-Version: resource=3.1, protocol=1.0' || true
}
trap 'cerrar_sesion; rm -rf "$TMP"' EXIT

# PUT de un cliente OAuth2; muestra el error de AM si falla
put_cliente() {
  local id=$1 cuerpo=$2 codigo
  codigo=$(curl -sS -o "$TMP/resp.json" -w '%{http_code}' -X PUT \
    "$AM/json/$REALM_PATH/realm-config/agents/OAuth2Client/$id" \
    -H "$COOKIE: $TOKEN" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json' \
    -H 'Accept-API-Version: resource=1.0' \
    --data "$cuerpo")
  if [[ "$codigo" != 200 && "$codigo" != 201 ]]; then
    echo "✘ Error $codigo al guardar el cliente $id:" >&2
    jq . "$TMP/resp.json" >&2 || cat "$TMP/resp.json" >&2
    exit 1
  fi
  echo "✔ Cliente $id guardado (HTTP $codigo)"
}

# Valor de propiedad de agente: {"inherited": false, "value": ...}
# (formato documentado para realm-config/agents/OAuth2Client)
REDIRECTS=$(printf '%s/callback\n' "${WEB_ORIGENES[@]}" | jq -R . | jq -s .)
LOGOUTS=$(printf '%s/\n' "${WEB_ORIGENES[@]}" | jq -R . | jq -s .)

# --- 1. Cliente público de la SPA ---
WEB=$(jq -n --argjson redirects "$REDIRECTS" --argjson logouts "$LOGOUTS" '
  def v(x): {inherited: false, value: x};
  {
    coreOAuth2ClientConfig: {
      clientType: v("Public"),
      clientName: v(["Mibanco Web"]),
      redirectionUris: v($redirects),
      scopes: v(["openid", "profile", "cuentas.read"]),
      defaultScopes: v(["openid"]),
      status: v("Active")
    },
    advancedOAuth2ClientConfig: {
      grantTypes: v(["authorization_code"]),
      responseTypes: v(["code"]),
      tokenEndpointAuthMethod: v("none"),
      isConsentImplied: v(true)
    },
    coreOpenIDClientConfig: {
      postLogoutRedirectUri: v($logouts)
    }
  }')
put_cliente mibanco-web "$WEB"

# --- 2. Cliente confidencial para la introspección de IG ---
if kubectl -n "$NS" get secret mibanco-ig-introspect >/dev/null 2>&1; then
  SECRETO=$(kubectl -n "$NS" get secret mibanco-ig-introspect \
    -o jsonpath='{.data.MIBANCO_IG_INTROSPECT_SECRET}' | base64 -d)
  echo "✔ Se reutiliza la clave del Secret mibanco-ig-introspect"
else
  # Hexadecimal: sin caracteres que haya que codificar en client_secret_basic
  SECRETO=$(openssl rand -hex 24)
  kubectl -n "$NS" create secret generic mibanco-ig-introspect \
    --from-literal=MIBANCO_IG_INTROSPECT_SECRET="$SECRETO" >/dev/null
  kubectl -n "$NS" label secret mibanco-ig-introspect app.kubernetes.io/part-of=mibanco-demo >/dev/null
  echo "✔ Secret mibanco-ig-introspect creado en $NS"
fi

IG=$(jq -n --arg secreto "$SECRETO" '
  def v(x): {inherited: false, value: x};
  {
    coreOAuth2ClientConfig: {
      clientType: v("Confidential"),
      clientName: v(["Mibanco IG introspeccion"]),
      userpassword: $secreto,
      scopes: v(["am-introspect-all-tokens"]),
      defaultScopes: v(["am-introspect-all-tokens"]),
      status: v("Active")
    },
    advancedOAuth2ClientConfig: {
      grantTypes: v(["client_credentials"]),
      tokenEndpointAuthMethod: v("client_secret_basic")
    }
  }')
put_cliente mibanco-ig-introspect "$IG"

# --- 3. Usuarios de prueba (solo si se indica PASSWORD_USUARIOS) ---
if [[ -n "${PASSWORD_USUARIOS:-}" ]]; then
  while IFS='|' read -r usuario nombre apellido; do
    cuerpo=$(jq -n --arg u "$usuario" --arg p "$PASSWORD_USUARIOS" --arg g "$nombre" --arg s "$apellido" \
      '{username: $u, userpassword: $p, givenName: $g, sn: $s, cn: "\($g) \($s)",
        mail: "\($u)@example.com", inetUserStatus: "Active"}')
    codigo=$(curl -sS -o "$TMP/resp.json" -w '%{http_code}' -X POST \
      "$AM/json/$REALM_PATH/users?_action=create" \
      -H "$COOKIE: $TOKEN" \
      -H 'Content-Type: application/json' \
      -H 'Accept-API-Version: resource=3.0, protocol=2.1' \
      --data "$cuerpo")
    case "$codigo" in
      200 | 201) echo "✔ Usuario $usuario creado" ;;
      409) echo "• Usuario $usuario ya existía (no se modifica)" ;;
      *) echo "✘ Error $codigo al crear $usuario: $(jq -c . "$TMP/resp.json" 2>/dev/null)" >&2 ;;
    esac
  done <<'EOF'
ana.torres|Ana|Torres
luis.quispe|Luis|Quispe
carla.mendoza|Carla|Mendoza
EOF
else
  echo "• Usuarios no creados (define PASSWORD_USUARIOS para crearlos)"
fi

# --- Verificación ---
echo
echo "Configuración guardada en AM:"
for id in mibanco-web mibanco-ig-introspect; do
  curl -fsS "$AM/json/$REALM_PATH/realm-config/agents/OAuth2Client/$id" \
    -H "$COOKIE: $TOKEN" -H 'Accept-API-Version: resource=1.0' |
    jq --arg id "$id" '{
      cliente: $id,
      tipo: .coreOAuth2ClientConfig.clientType,
      redirects: .coreOAuth2ClientConfig.redirectionUris,
      scopes: .coreOAuth2ClientConfig.scopes,
      grantTypes: .advancedOAuth2ClientConfig.grantTypes,
      authMethod: .advancedOAuth2ClientConfig.tokenEndpointAuthMethod,
      consentimientoImplicito: .advancedOAuth2ClientConfig.isConsentImplied,
      postLogout: .coreOpenIDClientConfig.postLogoutRedirectUri
    }'
done

echo
echo "Prueba del cliente de introspección (se espera {\"active\":false}):"
curl -sS -u "mibanco-ig-introspect:$SECRETO" -d 'token=prueba' "$AM/oauth2/introspect"
echo
