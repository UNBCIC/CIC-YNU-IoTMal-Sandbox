# sandbox-manager

The orchestration service for the IoT malware sandbox. It maintains a persistent task queue backed by MongoDB, distributes malware samples to workers, and collects the resulting analysis archives.

## Architecture overview

```
  ┌─────────────────────────────────────────────────┐
  │                sandbox-manager                  │
  │                                                 │
  │  ┌──────────────┐     ┌──────────────────────┐  │
  │  │   FastAPI    │────▶│  In-memory Queue +   │  │
  │  │   REST API   │     │  MongoDB persistence │  │
  │  └──────────────┘     └──────────────────────┘  │
  └─────────────────────────────────────────────────┘
          │                          ▲
          │ GET /get-file/{worker}   │ POST /submit-result/{id}
          ▼                          │
  ┌───────────────────┐   ┌───────────────────┐
  │  sandbox-worker-1 │   │  sandbox-worker-2 │  ...
  └───────────────────┘   └───────────────────┘
```

Workers poll the manager for tasks, run analysis inside QEMU VMs, and return a result zip.

## API endpoints

All routes are prefixed with `APP_BASE_URL` (default `/api/v1/sandbox-manager`).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/status` | Task counts grouped by status and current queue depth |
| `GET` | `/init-queue` | Scan `MALWARE_DIRECTORY` and enqueue new files |
| `POST` | `/submit-file` | Upload a single malware binary for analysis |
| `GET` | `/get-file/{worker_id}` | Dequeue the next task and stream the file to a worker |
| `POST` | `/submit-result/{task_id}` | Receive completed analysis zip from a worker |
| `GET` | `/results` | List all completed tasks |
| `GET` | `/results/{task_id}` | Download the result zip for a completed task |
| `GET` | `/health` | Health check |

### Queue lifecycle

1. Files enter the queue via `/init-queue` (bulk) or `/submit-file` (single).
2. Each file is assigned a UUID task ID and persisted to MongoDB with status `QUEUED`.
3. Workers claim tasks via `/get-file/{worker_id}` — status moves to `PROCESSING`.
4. Workers return results via `/submit-result/{task_id}` — status moves to `COMPLETED`.
5. On manager restart, any `PROCESSING` tasks are reset to `QUEUED` and re-enqueued automatically.

## Project structure

```
sandbox-manager/
├── config/
│   └── settings.py          # Pydantic-settings configuration
├── router/
│   ├── sandbox_router.py    # All task queue endpoints
│   └── healthcheck.py       # Health check endpoint
├── util/
│   └── lifespan_handlers.py # Startup/shutdown: MongoDB connect, queue recovery
├── main.py                  # Entry point — configures FastAPI and uvicorn
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Configuration

Copy `.env.example` to `.env` and fill in the required values.

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | — | Port the API listens on |
| `APP_BASE_URL` | — | URL prefix for all routes (e.g. `/api/v1/sandbox-manager`) |
| `HOST` | `0.0.0.0` | Bind address |
| `APP_NAME` | `sandbox-manager` | Instance name |
| `APP_LIMIT_CONCURRENCY` | `None` | Max concurrent connections (unset = unlimited) |
| `APP_BACKLOG` | `2048` | TCP backlog size |
| `APP_TIMEOUT_KEEP_ALIVE` | `5` | Keep-alive timeout in seconds |
| `MONGO_HOST` | `localhost:27017` | MongoDB host:port |
| `MONGO_USERNAME` | — | MongoDB username (required) |
| `MONGO_PASSWORD` | — | MongoDB password (required) |
| `MONGO_DB` | `sandbox` | MongoDB database name |
| `MALWARE_DIRECTORY` | — | Path to the directory of malware samples (required) |
| `OUTPUT_DIR` | `./output/` | Where result zips from workers are saved |
| `UPLOAD_DIR` | `./uploads/` | Where individually submitted files are saved |

## Running

### Docker Compose (recommended)

```bash
cp .env.example .env
# Fill in MONGO_USERNAME, MONGO_PASSWORD, and update the malware volume path in docker-compose.yml

docker compose up --build
```

The `docker-compose.yml` starts both MongoDB and the manager. Update the malware volume mount in the compose file to point to your local malware directory:

```yaml
volumes:
  - /path/to/your/malware:/malware:ro
```

### Locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in values
python3 main.py
```

Requires a running MongoDB instance accessible at `MONGO_HOST`.

## Scaling workers

The manager is stateless with respect to workers — any number of workers can connect and poll concurrently. See the `sandbox-worker` README for how to run and scale workers.
