# Diagnóstico

## Logs

```bash
# PingGateway: carga de rutas al arrancar y errores de introspección
kubectl -n lab logs deploy/ig --tail=200
kubectl -n lab logs deploy/ig -f | grep -i -E 'mibanco|introspect|error|exception'

# Access Management
kubectl -n lab logs deploy/am --tail=200      # en algunos despliegues es un StatefulSet: kubectl -n lab get pods | grep am

# Backend (access log de uvicorn y avisos de cuentas ajenas)
kubectl -n lab logs deploy/mibanco-cuentas-api -f

# Frontend (nginx) y certificado
kubectl -n lab logs deploy/mibanco-web
kubectl -n lab describe certificate mibanco-web-tls

# Controlador de Ingress que atiende el tráfico (ingress-nginx, addon de Minikube)
kubectl -n ingress-nginx logs deploy/ingress-nginx-controller --tail=100
```

La imagen de IG no tiene curl ni wget. Para llamar al backend desde dentro del clúster,
usa un Pod temporal:

```bash
kubectl -n lab run tmp-curl --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- \
  curl -s -H 'X-Usuario: prueba-interna' http://mibanco-cuentas-api.lab.svc.cluster.local:8000/api/cuentas
```

Rutas cargadas en IG (puerto de administración 8085; ⚠️ verifica la URL exacta del
endpoint):

```bash
kubectl -n lab port-forward deploy/ig 8085:8085 &
curl -s 'http://localhost:8085/openig/api/system/objects/router-service/routes?_queryFilter=true' | jq '.result[]._id'
```

## Errores típicos

| Síntoma | Causa probable | Solución |
|---|---|---|
| AM muestra *redirect_uri_mismatch* o «invalid redirect URI» | `VITE_OIDC_REDIRECT_URI` no coincide **exactamente** con *Redirection URIs* del cliente (barra final, http/https) | Igualar los valores. Si cambias la variable, reconstruye la imagen del frontend |
| AM devuelve `invalid_scope` | `cuentas.read` (u `openid` o `profile`) no está en *Scope(s)* de `mibanco-web` | Añadirlo (CONFIG_AM.md, paso 2) |
| Error de CORS en la consola del navegador al llamar a `forgeops.arvislab.com/am/...` | Falta CORS en AM para el origen de la app | Revisar la configuración CORS de AM (discovery, token, end_session) |
| Error de CORS al llamar a `/ig/api/cuentas` y el preflight devuelve 403 | El `Origin` no coincide con `acceptedOrigins` | Revisar el origen exacto, sin barra final |
| El preflight devuelve 401 o una respuesta de IDM | La ruta no cargó, o la condición no coincide y la petición cae en `50-reverseproxy` (IDM) | Ver «ruta que no carga» |
| La API siempre responde 401 `invalid_token` con un token recién emitido | Introspección rechazada: secret incorrecto, variable `MIBANCO_IG_INTROSPECT_SECRET` ausente, o falta `am-introspect-all-tokens` (`active:false`) | Probar la introspección a mano (PRUEBAS.md, paso 2). `kubectl -n lab exec deploy/ig -- env \| grep MIBANCO` (sin imprimir el valor en sitios compartidos) |
| El log de IG dice que no encuentra el secret `mibanco.ig.introspect.secret` | El Deployment no tiene la variable de entorno | DESPLIEGUE.md, paso 6 (`set env --from=secret`) |
| API 403 `insufficient_scope` | El token no trae `cuentas.read` | Revisar el scope del cliente y `VITE_OIDC_SCOPE`. Hay que volver a iniciar sesión |
| **Ruta que no carga:** 404 o respuesta de IDM en `/ig/api/cuentas` | (a) La imagen `ig-mibanco` no está desplegada, o el Pod no se reinició (`scanInterval: disabled`). (b) El JSON está en `routes-pod/`. (c) La condición no coincide (por ejemplo, si cambia el Ingress `ig` y deja de quitar `/ig`). (d) Error de sintaxis en el JSON | `kubectl -n lab get deploy ig -o jsonpath='{..image}'`; `kubectl -n lab exec deploy/ig -- ls /var/gateway/config/routes-service`; buscar la excepción en el log de IG al arrancar; ver DESPLIEGUE.md, paso 1 |
| API 401 «Usuario no identificado» (cuerpo JSON del backend) | IG reenvió `X-Usuario` vacío: el campo `sub` no llegó en la introspección | Revisar la introspección (PRUEBAS.md, paso 2) y la expresión `info.sub` de la ruta |
| 200 con `"cuentas": []` y la app dice «No encontramos cuentas» | No debería pasar: el primer acceso crea las cuentas. Puede ocurrir si se borraron filas de la base a mano | Ver el log del backend (`Usuario nuevo <sub>: plantilla …`) o borrar el usuario de la base para que se vuelva a crear |
| Backend en `CrashLoopBackOff` con `unable to open database file` o `readonly database` | El volumen no está montado en `/srv/var`, o no tiene permisos de escritura para el UID 10001 | `kubectl -n lab describe pod -l app.kubernetes.io/name=mibanco-cuentas-api`; revisar el PVC `mibanco-cuentas-db` (Bound) y `fsGroup: 10001` |
| API 502 o 504 | El backend no responde: Pod caído, nombre DNS mal escrito, o la NetworkPolicy bloquea a IG | `kubectl -n lab get pods,svc -l app.kubernetes.io/part-of=mibanco-demo`; borrar la NetworkPolicy para descartarla |
| La app muestra «Configuración incompleta» | La imagen del frontend se construyó sin algún `--build-arg` | Reconstruir pasando todas las variables |
| La app muestra «Tu sesión venció» justo después de iniciar sesión | IG responde 401 con un token válido: casi siempre es la introspección | Ver las filas anteriores sobre introspección |
| El certificado de `mibanco.arvislab.com` no queda listo (READY=False) | DNS, puerto 80 cerrado, o el solver HTTP-01 de `letsencrypt-prod` usa otra clase de Ingress | `kubectl -n lab describe challenge`; revisar `ingressClassName` |
| El Pod nuevo sigue con la imagen vieja | Con `IfNotPresent` y el mismo tag, no se vuelve a descargar | Subir el tag o ejecutar `kubectl rollout restart` |
| `ErrImageNeverPull` o `ImagePullBackOff` | La imagen se construyó fuera del Docker de Minikube | `eval $(minikube docker-env)` y reconstruir, o `minikube image load` |
