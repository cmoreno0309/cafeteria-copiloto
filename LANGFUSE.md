# Levantar Langfuse local (tarea 1.19)

`docker-compose.langfuse.yml`, en la raíz del repo, levanta los 6
servicios que necesita Langfuse autohospedado (web, worker, Postgres,
ClickHouse, Redis, MinIO). El código de la app ya está instrumentado —
ver `core/tracing.py`.

## 1. Levantar el stack

```bash
docker compose -f docker-compose.langfuse.yml up -d
```

Los defaults del compose funcionan tal cual para uso local (no expuesto a
internet). Si preferís generar tus propios secretos en vez de los
defaults, copiá `.env.langfuse.example` a `.env.langfuse` (gitignored),
completalo (instrucciones adentro) y agregá `--env-file .env.langfuse` al
comando de arriba.

Esperá a que los servicios estén healthy:

```bash
docker compose -f docker-compose.langfuse.yml ps
```

y abrí http://localhost:3000.

**Nota sobre Postgres:** el servicio `postgres` de este compose no mapea
el puerto 5432 al host a propósito — lo usan solo los contenedores de
Langfuse por la red interna de Docker. Si tenés un Postgres local propio
escuchando en 5432 (como en esta máquina), no hay conflicto. No hace
falta reabrir ese puerto para nada de lo que pide esta tarea.

## 2. Crear proyecto y claves de API

1. En http://localhost:3000, creá una cuenta local (autohospedado: el
   primer usuario se crea ahí mismo) y una organización/proyecto.
2. Project Settings → API Keys → Create new API key. Te da un par
   `pk-lf-...` / `sk-lf-...`.

## 3. Conectarlo a este proyecto

En el `.env` de **este** repo (`cafeteria-copilot/.env`, no
`.env.langfuse`), completá:

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

`LANGFUSE_HOST` es opcional (cae a `http://localhost:3000` si la dejás
vacía), pero ponela igual si tu Langfuse corre en otro puerto/host.

## 4. Confirmar que anda

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

```bash
docker compose -f docker-compose.langfuse.yml down          # apaga, conserva los datos
docker compose -f docker-compose.langfuse.yml down -v       # apaga y borra los datos (empieza de cero)
```
