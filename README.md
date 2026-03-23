# CIC-YNU-IoTMal-Sandbox

A dynamic malware analysis sandbox for IoT binaries. Malware samples are automatically executed inside QEMU virtual machines matching their CPU architecture (ARM, MIPS, MIPSEL, x86), with syscall traces, system resource usage, and network traffic captured simultaneously.

## Components

```
CIC-YNU-IoTMal-Sandbox/
├── sandbox-manager/    # Orchestration service — task queue, result storage
├── sandbox-worker/     # Analysis node — QEMU automation, data capture
└── docker-compose.yml  # Full-stack deployment
```

### sandbox-manager

A FastAPI service backed by MongoDB. It maintains a persistent queue of malware tasks, distributes them to workers on demand, and stores the resulting analysis archives. See [sandbox-manager/README.md](sandbox-manager/README.md) for full documentation.

### sandbox-worker

A QEMU-based analysis node. Each worker claims a task from the manager, detects the ELF architecture of the binary, boots the matching VM image, runs the malware under `strace`, `sar`, and `tshark`, and returns a zip containing all captured data. Workers are architecture-agnostic — the same image handles ARM, MIPS, MIPSEL, and x86 binaries. See [sandbox-worker/README.md](sandbox-worker/README.md) for full documentation.

## How it works

```
  ┌──────────────────────────────────────────────────────┐
  │                    sandboxnet                        │
  │                                                      │
  │  ┌─────────────────┐       ┌──────────────────────┐  │
  │  │ sandbox-manager │◀──────│   sandbox-worker-N   │  │
  │  │   (+ MongoDB)   │       │                      │  │
  │  └─────────────────┘       │  ┌────────────────┐  │  │
  │         ▲                  │  │   QEMU VM      │  │  │
  │         │ result zip       │  │  (tap network) │  │  │
  │         └──────────────────│  └────────────────┘  │  │
  └──────────────────────────────────────────────────────┘
```

1. Files are added to the queue via the manager API (`/init-queue` for bulk or `/submit-file` for individual files).
2. Each worker polls the manager, claims a task, and runs a two-phase analysis:
   - **Phase 1**: Boot VM → configure network → run malware under `strace`/`sar`/`tshark` → shut down.
   - **Phase 2**: Reboot VM → exfiltrate `strace.log` and `sar.out` to the worker → shut down.
3. The worker packages all captured files into a zip and submits it to the manager.
4. Results are retrievable via the manager API.

The two-phase approach ensures log files written inside the VM are fully flushed to the virtual disk before collection.

## Network isolation warning

> **The QEMU virtual machines have live internet access by design.**

Each worker bridges its tap interface directly to the container's network. The malware VM gets a routable IP and can make outbound connections — this is intentional, as capturing real C2 communication, DNS lookups, and exfiltration attempts is a core part of the analysis.

**What this means in practice:**

- Malware running inside the VM **can reach the public internet**. C2 beacons, DNS queries, and download attempts will go out over your host's network connection. Ensure you are running this on an isolated research network or a machine whose internet traffic is monitored and acceptable for this purpose.
- Malware running inside the VM **can reach other containers on `sandboxnet`** (the manager, other workers). This is a known limitation of the bridge network model. Do not run sensitive services on the same Docker network as the workers.
- All outbound traffic from the VM is captured in `network.pcap` per task, which is the primary network artefact of the analysis.

**Recommended precautions before running:**

1. Run on a dedicated, isolated research machine or network segment (air-gapped, VLAN, or a VM with restricted routing) — not on shared academic or institutional infrastructure.
2. Inform your institution's network administrator before running, particularly in a university or lab environment — the sandbox will generate anomalous traffic (port scans, C2 beacons, exploit attempts) that may trigger network monitoring systems.
3. If your research dataset does not require observing live C2 or DNS behaviour, consider disabling internet access for the VMs — see [Disabling VM internet access](#disabling-vm-internet-access) below.

## Quick start

### 1. Configure

```bash
cp .env.example .env
```

Edit `.env` and set `MONGO_USERNAME` and `MONGO_PASSWORD`.

### 2. Set the malware directory

Edit `docker-compose.yml` and update the malware volume mount under `sandbox-manager`:

```yaml
volumes:
  - /path/to/your/malware:/malware:ro
```

### 3. Build and run

```bash
docker compose up --build
```

This starts MongoDB, the manager (port `8011`), and one worker.

### 4. Initialise the queue

Once everything is running, tell the manager to scan the malware directory and enqueue all samples:

```bash
curl http://localhost:8011/api/v1/sandbox-manager/init-queue
```

Or submit an individual file:

```bash
curl -X POST http://localhost:8011/api/v1/sandbox-manager/submit-file \
     -F "file=@/path/to/sample"
```

### 5. Monitor progress

```bash
curl http://localhost:8011/api/v1/sandbox-manager/status
```

### 6. Retrieve results

```bash
# List completed tasks
curl http://localhost:8011/api/v1/sandbox-manager/results

# Download a result zip
curl -O http://localhost:8011/api/v1/sandbox-manager/results/{task_id}
```

## Disabling VM internet access

By default, QEMU VMs can reach the public internet. To block this while still allowing the VM to communicate with its worker (required for binary download and log upload), set `ALLOW_VM_INTERNET=false` in your `.env`:

```env
ALLOW_VM_INTERNET=false
```

When this is set, each worker inserts two `iptables` FORWARD rules at startup:

1. **Allow** `tap0 → worker IP` — the VM can still reach `server.py` on the same container.
2. **Drop** `tap0 → everything else` — internet and other containers on `sandboxnet` are unreachable.

The poller process communicates with the manager over the container's own network stack and is unaffected by these rules.

> **Note:** With internet access disabled, any malware that depends on reaching a C2 server or downloading a second stage will not behave as it would in the wild. `network.pcap` will still be captured but will only contain connection attempts, not responses. This is acceptable for syscall-focused research but will produce incomplete network artefacts.

## Scaling workers

To run multiple workers in parallel, duplicate the `sandbox-worker-1` block in `docker-compose.yml` (a commented example is included) and assign each a unique `APP_NAME`, host port, and IP address on the `192.168.40.0/24` subnet.

Each worker requires a fixed IP because QEMU creates a tap network interface using the worker's container IP to route traffic between the host and the VM.

## Result archive contents

Each completed task produces a `.zip` containing:

| File | Description |
|------|-------------|
| `strace.log` | Full syscall trace of the malware execution |
| `sar.out` | System resource usage (CPU, memory, I/O) sampled every second |
| `network.pcap` | Raw network traffic captured on the tap interface |
| `qemu.log` | QEMU console output for both analysis phases |

## Requirements

- Docker and Docker Compose
- Host kernel with TUN/TAP support (standard on most Linux distributions)
- Workers run as `privileged` containers to create tap interfaces

## Citation

This sandbox was developed as part of the **CIC-YNU-IoTMal Dataset 2026** research. If you use this tool or the dataset in your work, please cite:

> S. Dadkhah, O. D. Okey, S. A. Maret, Y. Lo, A. Firouzia, R. Kuki, T. Sasaki, K. Yoshioka, T. Ban, S. Ozawa, A. A. Ghorbani, "CIC-YNU-IoTMal: A Comprehensive Multilayer Dataset for Static and Dynamic Analysis of IoT Malware Behavior," submitted to *Expert Systems with Applications*, 2026.

Dataset page: https://www.unb.ca/cic/datasets/ynu-iot-2026.html
