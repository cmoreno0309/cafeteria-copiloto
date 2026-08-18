# Levantar Langfuse local (tarea 1.19)

Instrucciones para levantar el contenedor de Langfuse que trazará el
grafo. Esto lo hacés vos (necesita Docker); el código ya está
instrumentado del lado del proyecto — ver `core/tracing.py`.

## 1. Bajar el docker-compose oficial

Langfuse (versión actual) se autohospeda con varios servicios (web,
worker, Postgres, ClickHouse, Redis, MinIO) — no hay una versión de un
solo contenedor. En vez de copiar ese archivo a mano acá (con el riesgo
de transcribirlo mal), clonalo directo del repo oficial, en una carpeta
aparte de este proyecto (es infraestructura, no código de la app):

```bash
cd ~
git clone https://github.com/langfuse/langfuse.git
cd langfuse
```

## 2. Generar los secretos

El `docker-compose.yml` de ese repo trae varias variables marcadas
`# CHANGEME` (`SALT`, `ENCRYPTION_KEY`, `NEXTAUTH_SECRET`,
`CLICKHOUSE_PASSWORD`, `REDIS_AUTH`, credenciales de MinIO). Generalas
antes de levantar el stack, por ejemplo:

```bash
openssl rand -hex 32   # para ENCRYPTION_KEY
openssl rand -hex 16   # para el resto de los secretos CHANGEME
```

Reemplazá cada `# CHANGEME` del `docker-compose.yml` (o de un `.env` al
lado, si esa versión del repo lo usa así) con un valor generado.

## 3. Levantar el stack

```bash
docker compose up -d
```

Esperá a que los servicios estén healthy (`docker compose ps`) y abrí
http://localhost:3000.

## 4. Crear proyecto y claves de API

1. En http://localhost:3000, creá una cuenta local (autohospedado: el
   primer usuario se crea ahí mismo, no hace falta nada externo) y una
   organización/proyecto.
2. Project Settings → API Keys → Create new API key. Te da un par
   `pk-lf-...` / `sk-lf-...`.

## 5. Conectarlo a este proyecto

En el `.env` de **este** repo (`cafeteria-copilot/.env`, no el de
Langfuse), completá:

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

`LANGFUSE_HOST` es opcional (cae a `http://localhost:3000` si la dejás
vacía), pero ponela igual si tu Langfuse corre en otro puerto/host.

## 6. Confirmar que anda

Avisame cuando esté arriba y las claves estén en `.env`. Corro:

```bash
py -m evals.run_evals
```

Si las trazas están activas, al final va a imprimir un `session_id` y el
comando exacto para pedirte el costo total y el promedio por consulta:

```bash
py -m evals.costo_langfuse <session_id>
```

## Apagar el contenedor

Desde la carpeta donde clonaste Langfuse:

```bash
docker compose down          # apaga, conserva los datos
docker compose down -v       # apaga y borra los datos (empieza de cero)
```
