# Por defecto, la imagen del Deployment ig verificada en la VM; se puede sobrescribir con --build-arg
ARG IG_BASE_IMAGE=us-docker.pkg.dev/forgeops-public/images/ig:2026.3.2-1722
FROM ${IG_BASE_IMAGE}


COPY --chown=forgerock:root routes/01-mibanco-cuentas-api.json /var/gateway/config/routes-service/01-mibanco-cuentas-api.json
