# sandbox-worker

A QEMU-based dynamic analysis node for IoT malware. Each worker claims malware samples from the sandbox-manager, boots the appropriate virtual machine for the binary's architecture, runs the malware under monitoring tools (strace, sar, tshark), and returns a result archive containing the captured data.

## Network isolation warning

> **QEMU virtual machines have live internet access by design.**

Each worker bridges its tap interface to the container's network. The malware VM gets a routable IP and can make real outbound connections — capturing C2 communication, DNS lookups, and download attempts is part of the analysis. This means malware will generate real network traffic on your host's connection.

**Run this only on an isolated research network.** See the [root README](../README.md#network-isolation-warning) for full details and recommended precautions.

## How analysis works

Analysis runs in two phases to ensure all captured data is flushed to the virtual disk before collection.

**Phase 1 — Capture**

1. The worker detects the ELF architecture of the malware binary (`ARM`, `MIPS`, `MIPSEL`, or `x86`).
2. The matching QEMU VM is booted from the bundled disk image.
3. Network is configured inside the VM (IP, gateway, DNS).
4. The malware binary is downloaded into the VM over the tap network.
5. Three monitors are started in parallel:
   - `tshark` on the host tap interface — captures network traffic to `network.pcap`
   - `sar` inside the VM — records system resource usage to `sar.out`
   - `strace` inside the VM — traces all syscalls to `strace.log`
6. The malware runs for `ANALYSIS_DURATION` seconds, then all monitors are stopped.
7. `POST_ANALYSIS_WAIT` seconds are waited to allow the VM OS to flush files to the virtual disk.
8. The VM is shut down.

**Phase 2 — Exfiltration**

1. The same VM is booted again. The virtual disk retains all files written in Phase 1.
2. Network is reconfigured.
3. `strace.log` and `sar.out` are uploaded from inside the VM to the worker's REST API via `curl`.
4. The VM is shut down.

The worker then packages all captured files (`strace.log`, `sar.out`, `network.pcap`, `qemu.log`) into a zip archive and submits it to the manager.

## Supported architectures

| Architecture | QEMU system | VM images |
|---|---|---|
| ARM (little-endian) | `qemu-system-arm` | `ARM/image.zip` |
| MIPS (big-endian) | `qemu-system-mips` | `MIPS/image.zip` |
| MIPSEL (little-endian) | `qemu-system-mipsel` | `MIPSEL/image.zip` |
| x86 (32-bit) | `qemu-system-i386` | `x86/image.zip` |

Architecture is detected automatically from the ELF binary using the `file` command — no manual configuration required.

## Operating modes

The worker supports two modes that are meant to run side by side:

| Script | Mode | Description |
|--------|------|-------------|
| `poller.py` | Pull | Continuously polls the manager for new tasks and runs analysis |
| `server.py` | Push | FastAPI server that accepts tasks pushed directly to it |

In the typical deployment both are run simultaneously. `poller.py` handles the normal workflow; `server.py` exposes internal endpoints that the VM uses during analysis to fetch the malware binary and upload captured log files.

## API endpoints (server.py)

All routes are prefixed with `APP_BASE_URL` (default `/api/v1/sandbox-worker`).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/submit-task/{task_id}` | Push a task directly to this worker (push mode) |
| `GET` | `/get-task/{task_id}/file` | Serve the malware binary to the VM during analysis |
| `POST` | `/update-task/{task_id}/strace` | Receive strace log uploaded from inside the VM |
| `POST` | `/update-task/{task_id}/sar` | Receive sar output uploaded from inside the VM |
| `GET` | `/health` | Health check |

## Project structure

```
sandbox-worker/
├── ARM/
│   ├── image/
│   │   ├── zImage          # ARM kernel
│   │   └── root.ext4       # ARM root filesystem
│   └── image.zip           # Packaged image (extracted at analysis time)
├── MIPS/                   # Same structure as ARM/
├── MIPSEL/                 # Same structure as ARM/
├── x86/                    # Same structure as ARM/
├── config/
│   └── settings.py         # Pydantic-settings configuration
├── router/
│   ├── sandbox_router.py   # Push-mode API endpoints
│   └── healthcheck.py      # Health check endpoint
├── service/
│   └── analysis.py         # QEMU automation, arch detection, two-phase analysis
├── util/
│   └── lifespan_handlers.py
├── server.py               # FastAPI entry point (push mode)
├── poller.py               # Polling loop entry point (pull mode)
├── run.sh                  # Runs both server.py and poller.py together
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Configuration

Copy `.env.example` to `.env` and fill in the required values.

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | — | Port the worker API listens on |
| `APP_BASE_URL` | — | URL prefix for all routes (e.g. `/api/v1/sandbox-worker`) |
| `HOST` | `0.0.0.0` | Bind address |
| `APP_NAME` | `sandbox-worker-1` | Unique name for this worker instance |
| `APP_LIMIT_CONCURRENCY` | `None` | Max concurrent connections (unset = unlimited) |
| `APP_BACKLOG` | `2048` | TCP backlog size |
| `APP_TIMEOUT_KEEP_ALIVE` | `5` | Keep-alive timeout in seconds |
| `DATA_DIR` | `./data/` | Working directory for in-progress task files |
| `QEMU_LOG_PATH` | `/qemu.log` | Path inside the task directory for QEMU console output |
| `SANDBOX_MANAGER_URI` | — | Full base URL of the sandbox-manager (e.g. `http://manager:8011/api/v1/sandbox-manager`) |
| `ANALYSIS_DURATION` | `30` | Seconds to let the malware run inside the VM |
| `POST_ANALYSIS_WAIT` | `30` | Seconds to wait after stopping monitors before shutting down the VM (filesystem flush) |

## Running

### Docker Compose (recommended)

```bash
cp .env.example .env
# Fill in PORT, APP_BASE_URL, APP_NAME, SANDBOX_MANAGER_URI

docker compose up --build
```

The container requires `--privileged` (set in the compose file) to create tap network interfaces for QEMU.

### Locally

Requires: `qemu-system-arm`, `qemu-system-mips`, `qemu-system-mipsel`, `qemu-system-i386`, `tshark`, `sar`, `uml-utilities` (`tunctl`), `file`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in values
./run.sh              # starts both server.py and poller.py
```

## Scaling

Each worker instance is independent. To run multiple workers, duplicate the service block in `docker-compose.yml` (an example is included as a comment) and assign each a unique `APP_NAME`, host port, and IP address on the `sandboxnet` network.

The manager distributes tasks across however many workers are polling — no additional configuration is needed on the manager side.
