# Despliegue en la VM (Minikube + ForgeOps, namespace `lab`)

Orden recomendado: **verificar → AM → imágenes → backend → IG (⚠️ cambia ForgeOps) →
frontend → pruebas**. Todos los recursos nuevos llevan la etiqueta
`app.kubernetes.io/part-of=mibanco-demo`.

## Verificado y supuesto

| Tema | Estado | Fuente |
|---|---|---|
| **Realm raíz `/`** (el realm `alpha` no existe). `issuer` = `https://forgeops.arvislab.com/am/oauth2`; introspección `…/am/oauth2/introspect`; `endSession` `…/am/oauth2/connect/endSession` | ✅ | discovery con curl en la VM |
| El tráfico externo lo atiende **ingress-nginx** (addon de Minikube, NodePort). Todos los Ingress de `lab` usan la clase `nginx`. Traefik está instalado (LoadBalancer `<pending>`), pero ningún recurso de `lab` lo usa | ✅ | `kubectl get ingressclass`, `kubectl get svc -A`, `kubectl -n lab get ingress` |
| El Ingress `ig` (`/ig(/\|$)(.*)` con `rewrite-target: /$2`) **quita `/ig`**: IG recibe `/api/cuentas/...`. Por eso la condición de la ruta es `^/api/cuentas` y no hace falta `UriPathRewriteFilter` | ✅ | `curl /ig/rs-tokenintrospect` → `401 Bearer realm="OpenIG"` |
| `letsencrypt-prod` resuelve HTTP-01 con un Ingress de clase `nginx`, la misma clase que usa el Ingress del frontend | ✅ | `kubectl get clusterissuer letsencrypt-prod -o yaml` |
| IG elige el router por host: las peticiones por Service/Ingress van a `routes-service/`; `routes-pod/` (`99-kube-probe.json`) es solo para la IP del Pod | ✅ | `config.json` del Pod |
| Los routers tienen `"scanInterval": "disabled"`: las rutas **solo se cargan al arrancar el Pod** | ✅ | `config.json` del Pod |
| `50-reverseproxy.json` no tiene condición y reenvía todo a IDM; las rutas se evalúan por orden de nombre, así que la nuestra se llama `01-…` | ✅ | `routes-service/` del Pod y repositorio forgeops |
| El Deployment `ig` lo gestiona **Helm** (release `ping-gateway`, chart `ping-gateway-2026.3.2`), con la imagen `us-docker.pkg.dev/forgeops-public/images/ig:2026.3.2-1722`, `IfNotPresent`, la etiqueta `app: ig` y sin volúmenes ni Secrets | ✅ | `kubectl -n lab get deploy ig -o yaml` |
| El chart acepta `ig.image.repository`, `ig.image.tag`, `ig.env` e `ig.envFrom` | ✅ los values / ⚠️ que la plantilla aplique `envFrom` | `helm -n lab get values ping-gateway -a` |
| Sintaxis de `CorsFilter`, `OAuth2ResourceServerFilter`, `TokenIntrospectionAccessTokenResolver`, `SystemAndEnvSecretStore` y `HeaderFilter`, y el contexto `contexts.oauth2.accessToken.info` | ✅ | docs.pingidentity.com/pinggateway/2026 |
| `ClientSecretBasicAuthenticationFilter` (`clientId`, `clientSecretId`, `secretsProvider`) | ✅ | `03-rs-tokenintrospect.json` en forgeops |
| `CorsFilter` responde el preflight sin llamar al resto del chain | ⚠️ | La documentación dice que arma la respuesta del preflight, pero no lo afirma de forma explícita. Lo comprueba la prueba 3 de PRUEBAS.md |
| La introspección trae el **UUID** del usuario en `user_id`, `username`, `sub` y `subname` (no el nombre). La ruta envía `info.sub` en `X-Usuario` y el backend da de alta a cada `sub` nuevo con datos demo (SQLite) | ✅ | Introspección real de `ana.torres` en la VM |
| `soTimeout` en `ReverseProxyHandler` | ⚠️ | No lo verifiqué; si IG lo rechaza al cargar la ruta, bórralo |
| Scope `am-introspect-all-tokens` en AM | ⚠️ | Comportamiento habitual de AM |
| El DNS de `mibanco.arvislab.com` apunta a la VM y los puertos 80 y 443 llegan a ingress-nginx | ⚠️ | Se asume que funciona igual que para `forgeops.arvislab.com` |

## 1. Verificaciones previas (solo lectura)

Ya hechas (resultados en la tabla). Para repetirlas:

```bash
curl -s https://forgeops.arvislab.com/am/oauth2/.well-known/openid-configuration | jq .issuer
curl -si https://forgeops.arvislab.com/ig/rs-tokenintrospect | head -3    # 401 realm="OpenIG" => /ig se quita
kubectl -n lab get deploy ig -o jsonpath='{.spec.template.spec.containers[0].image}{"
"}'
kubectl -n lab exec deploy/ig -- ls /var/gateway/config/routes-service
helm -n lab list
```

## 2. Copiar el código a la VM

```bash
# Desde tu equipo (o git clone si los subes a un repositorio)
gcloud compute scp --recurse forgeops-workshop-backend forgeops-workshop-frontend <vm>:~/mibanco/ --zone <zona>
```

No copies `.venv/` ni `node_modules/`: se ignoran en el build y pesan mucho.

## 3. Configurar AM

Por terminal, con el script (detalles en [CONFIG_AM.md](CONFIG_AM.md)):

```bash
cd ~/mibanco/forgeops-workshop-backend
PASSWORD_USUARIOS='<clave de prueba>' bash scripts/configurar-am.sh
```

Crea el cliente `mibanco-web`, el cliente `mibanco-ig-introspect` con su Secret
`mibanco-ig-introspect` en `lab`, y los usuarios de prueba.

## 4. Construir imágenes dentro de Minikube (sin registry)

Con `minikube docker-env` el cliente `docker` de la VM apunta al daemon **interno** de
Minikube: la imagen queda disponible para los Pods sin registry ni `image load`.

```bash
eval $(minikube docker-env)       # solo afecta a esta terminal
docker images | head              # deberías ver las imágenes de ForgeOps (am, idm, ig, ...)
```

- Usa `imagePullPolicy: IfNotPresent` (o `Never`) y **tags fijos** (`1.0.0`). Con `latest`,
  Kubernetes usa `Always` por defecto e intentaría descargar la imagen de Docker Hub.
- Con `IfNotPresent`, reconstruir el **mismo tag** no actualiza el Pod. Sube el tag
  (`1.0.1`) y actualiza el manifiesto, o ejecuta `kubectl rollout restart`.
- Alternativa: `docker build` normal y luego `minikube image load mibanco-cuentas-api:1.0.0`
  (copia un tar; es más lenta).

```bash
cd ~/mibanco/forgeops-workshop-backend
docker build -t mibanco-cuentas-api:1.0.0 .

cd ~/mibanco/forgeops-workshop-frontend
docker build -t mibanco-web:1.0.0 \
  --build-arg VITE_OIDC_AUTHORITY=https://forgeops.arvislab.com/am/oauth2 \
  --build-arg VITE_OIDC_CLIENT_ID=mibanco-web \
  --build-arg VITE_OIDC_REDIRECT_URI=https://mibanco.arvislab.com/callback \
  --build-arg VITE_OIDC_POST_LOGOUT_REDIRECT_URI=https://mibanco.arvislab.com/ \
  --build-arg "VITE_OIDC_SCOPE=openid profile cuentas.read" \
  --build-arg VITE_API_BASE_URL=https://forgeops.arvislab.com/ig \
  .
```

## 5. Desplegar el backend (no toca ForgeOps)

```bash
cd ~/mibanco/forgeops-workshop-backend
kubectl apply -k k8s/
kubectl -n lab rollout status deploy/mibanco-cuentas-api

# Prueba interna (simula a IG enviando X-Usuario)
kubectl -n lab port-forward svc/mibanco-cuentas-api 8000:8000 &
curl -s -H 'X-Usuario: prueba-interna' http://localhost:8000/api/cuentas | jq   # crea el usuario con datos demo
kill %1
```

Opcional: `kubectl apply -f k8s/networkpolicy.yaml`. Lee antes los comentarios del archivo:
el CNI por defecto de Minikube podría no aplicar NetworkPolicies.

El backend está en `lab`, así que IG lo resuelve como
`mibanco-cuentas-api.lab.svc.cluster.local:8000` (`baseURI` de la ruta). Si algún día pasa a
otro namespace, solo cambia esa línea.

## 6. ⚠️ Cambios en el Deployment `ig` de ForgeOps (pide confirmación antes)

**Qué se cambia y por qué:**

1. **Imagen** `ig` → `ig-mibanco:1.0.0`: es la misma imagen más el archivo
   `routes-service/01-mibanco-cuentas-api.json`. Hace falta porque IG no vuelve a escanear
   las rutas (`scanInterval: disabled`) y el Pod no tiene volúmenes.
2. **Variable** `MIBANCO_IG_INTROSPECT_SECRET` desde el Secret `mibanco-ig-introspect`, para
   que la ruta pueda autenticarse en la introspección.

**Impacto:** el Pod de IG se reinicia una vez. Con una sola instancia, `/ig` no responde
durante unos segundos o minutos. AM, IDM, DS y las UIs no se tocan.

**Qué pasa si el Pod se reinicia:** la ruta va dentro de la imagen y la variable en el
Deployment, así que se mantiene. Lo que importa es **cómo** se aplica el cambio, porque
el Deployment es de Helm (release `ping-gateway`):

| Opción | Persistencia |
|---|---|
| **B. Helm (recomendada)** | El cambio queda en los values del release; un `helm upgrade --reuse-values` posterior lo conserva |
| **A. kubectl** (rápida, para probar) | Un `helm upgrade` o `helm rollback` de `ping-gateway` vuelve a escribir la imagen original y quita la variable |

### Construir la imagen derivada (común a A y B)

```bash
cd ~/mibanco/forgeops-workshop-backend
eval $(minikube docker-env)

# Base: la imagen que usa hoy el Deployment (ya está en el Docker de Minikube)
IG_IMAGE=$(kubectl -n lab get deploy ig -o jsonpath='{.spec.template.spec.containers[0].image}')
echo "$IG_IMAGE"     # us-docker.pkg.dev/forgeops-public/images/ig:2026.3.2-1722
docker build --build-arg IG_BASE_IMAGE="$IG_IMAGE" -t ig-mibanco:1.0.0 ig/

# Comprobar que la ruta quedó en la imagen
docker run --rm --entrypoint ls ig-mibanco:1.0.0 /var/gateway/config/routes-service

# Respaldo para revertir
kubectl -n lab get deploy ig -o yaml > ~/ig-deployment-backup.yaml
helm -n lab get values ping-gateway > ~/ping-gateway-values-backup.yaml
```

### Opción B: Helm (recomendada)

`k8s/ig-values-mibanco.yaml` cambia `ig.image.*` y añade `ig.envFrom` con el Secret. Con
`--reuse-values` se conservan los demás values del release.

```bash
helm -n lab list                     # chart ping-gateway-2026.3.2
# <chart>: la misma referencia con la que se instaló el release (por ejemplo la carpeta
# charts/ping-gateway del repositorio forgeops en el tag 2026.3.2). PENDIENTE: confirmarla.
helm -n lab upgrade ping-gateway <chart> --version 2026.3.2   --reuse-values -f k8s/ig-values-mibanco.yaml --dry-run=server | grep -E 'image:|secretRef' -A2

# Si el dry-run muestra la imagen ig-mibanco y envFrom con el secretRef, aplica:
helm -n lab upgrade ping-gateway <chart> --version 2026.3.2   --reuse-values -f k8s/ig-values-mibanco.yaml
kubectl -n lab rollout status deploy/ig
```

Revertir: `helm -n lab rollback ping-gateway` (a la revisión anterior).

### Opción A: kubectl (prueba rápida)

```bash
# Los dos cambios en un solo reinicio
kubectl -n lab rollout pause deploy/ig
kubectl -n lab set env deploy/ig --from=secret/mibanco-ig-introspect
kubectl -n lab set image deploy/ig ig=ig-mibanco:1.0.0
kubectl -n lab rollout resume deploy/ig
kubectl -n lab rollout status deploy/ig
```

Revertir:

```bash
kubectl -n lab rollout undo deploy/ig
# o, de forma explícita:
kubectl -n lab set image deploy/ig ig="$IG_IMAGE"
kubectl -n lab set env deploy/ig MIBANCO_IG_INTROSPECT_SECRET-
```

### Comprobar (A o B)

```bash
kubectl -n lab get deploy ig -o jsonpath='{..image}{"
"}'          # ig-mibanco:1.0.0
kubectl -n lab exec deploy/ig -- sh -c 'test -n "$MIBANCO_IG_INTROSPECT_SECRET" && echo secret-ok'
kubectl -n lab logs deploy/ig | grep -i -E 'mibanco|route|error' | tail -20
```

Para cambiar la ruta más adelante: edita el JSON, construye `ig-mibanco:1.0.1` y actualiza
el tag en `k8s/ig-values-mibanco.yaml` (opción B) o ejecuta
`kubectl -n lab set image deploy/ig ig=ig-mibanco:1.0.1` (opción A).

## 7. Desplegar el frontend

```bash
cd ~/mibanco/forgeops-workshop-frontend
kubectl apply -k k8s/
kubectl -n lab rollout status deploy/mibanco-web
kubectl -n lab get certificate mibanco-web-tls -w   # esperar READY=True
```

Requisitos: el DNS de `mibanco.arvislab.com` apunta a la IP pública de la VM, y el
puerto 80 llega a ingress-nginx para el desafío HTTP-01 de Let's Encrypt (⚠️ se asume que es
igual que para `forgeops.arvislab.com`).

## 8. Verificar

1. Abre `https://mibanco.arvislab.com/` y pulsa «Ingresar»: te lleva al login de AM.
2. Inicia sesión con un usuario del JSON: vuelves a «Mis cuentas» con tu nombre y tus saldos.
3. Entra a una cuenta: movimientos, filtros y consumos por categoría.
4. «Cerrar sesión»: vuelves al inicio y la sesión de AM queda cerrada.
5. Ejecuta las pruebas con curl de [PRUEBAS.md](PRUEBAS.md).

Si algo falla, consulta [DIAGNOSTICO.md](DIAGNOSTICO.md).

## Desinstalar la demo

```bash
kubectl -n lab delete -k ~/mibanco/forgeops-workshop-frontend/k8s/
kubectl -n lab delete -k ~/mibanco/forgeops-workshop-backend/k8s/   # incluye el PVC mibanco-cuentas-db (borra la base SQLite)
kubectl -n lab delete networkpolicy mibanco-cuentas-api-solo-ig --ignore-not-found
# Revertir IG (paso 6) y, al final:
kubectl -n lab delete secret mibanco-ig-introspect
```
