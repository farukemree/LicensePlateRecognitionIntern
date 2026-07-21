# Yerel Kurulum

## Backend

Backend ve PostgreSQL Docker Compose ile calisir.

```bash
cd backend
copy .env.example .env
docker compose up -d --build
```

Saglik kontrolu:

```bash
curl http://localhost:8080/healthz
```

Not: `.env` icindeki `AUTH_JWKS_URL` ve `AUTH_ISSUER` su an ornek Keycloak adresleriyle dolu. `/healthz` calisir; korumali `/api/v1/*` endpointleri icin gercek Keycloak/JWT kurulumu gerekir.

## Frontend

```bash
cd frontend
npm install
npm run dev -- --host=0.0.0.0
```

Frontend adresi:

```text
http://localhost:5173
```

Vite proxy ayari sayesinde frontend icinden `/api/*` ve `/healthz` istekleri backend'e gider.

## Dogrulama

```bash
cd frontend
npm run build
```

```bash
cd backend
docker compose ps
```
