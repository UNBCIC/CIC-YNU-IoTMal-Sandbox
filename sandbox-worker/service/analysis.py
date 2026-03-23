import fcntl
import logging
import os
import signal
import subprocess
import time
import pexpect
import ipaddress
from dataclasses import dataclass
from zipfile import ZipFile

from config.settings import app_settings

logger = logging.getLogger(__name__)


@dataclass
class ArchConfig:
    qemu_cmd_template: str
    net_iface: str
    boot_ready_prompt: str
    qemu_timeout: int
    image_zip_path: str
    image_kernel_path: str
    image_rootfs_path: str
    cd_before_analysis: bool = True
    # MIPS/MIPSEL need an extra terminal poke after DNS setup in both phases
    extra_prompt_after_dns: bool = False
    # MIPS/MIPSEL need an extra terminal poke in the phase 2 boot before the network-ready prompt
    extra_boot_prompt_phase2: bool = False
    # Set True when the network-ready prompt may not appear (e.g. x86) — timeout is tolerated
    network_ready_prompt_optional: bool = False
    # Seconds to wait after network is up in phase 2 before exfiltrating.
    # Allows time for the filesystem from phase 1 to be fully accessible after reboot.
    exfiltrate_wait: int = 0


ARCH_CONFIGS = {
    "ARM": ArchConfig(
        qemu_cmd_template=(
            'qemu-system-arm -M virt-2.9 -kernel {kernel} -no-reboot -nographic'
            ' -device virtio-net-pci -netdev tap,id=net1,ifname=tap0,script=no,downscript=no'
            ' -device virtio-net-pci,netdev=net1 -drive file={rootfs},if=virtio,format=raw'
            ' -append "root=/dev/vda"'
        ),
        net_iface="eth1",
        boot_ready_prompt="br-lan: link becomes ready",
        qemu_timeout=100,
        image_zip_path="./ARM/image.zip",
        image_kernel_path="/image/zImage",
        image_rootfs_path="/image/root.ext4",
        cd_before_analysis=False,
        extra_prompt_after_dns=False,
        extra_boot_prompt_phase2=False,
        exfiltrate_wait=0,
    ),
    "MIPS": ArchConfig(
        qemu_cmd_template=(
            'qemu-system-mips -M malta -kernel {kernel} -hda {rootfs}'
            ' -append "root=/dev/sda" -nographic -no-reboot'
            ' -device pcnet,netdev=net0 -netdev tap,id=net0,ifname=tap0,script=no,downscript=no'
        ),
        net_iface="br-lan",
        boot_ready_prompt="entered forwarding state",
        qemu_timeout=30,
        image_zip_path="./MIPS/image.zip",
        image_kernel_path="/image/vmlinux",
        image_rootfs_path="/image/root.ext4",
        cd_before_analysis=True,
        extra_prompt_after_dns=True,
        extra_boot_prompt_phase2=True,
        exfiltrate_wait=10,
    ),
    "MIPSEL": ArchConfig(
        qemu_cmd_template=(
            'qemu-system-mipsel -m 512 -kernel {kernel} -hda {rootfs}'
            ' -append "root=/dev/sda" -nographic -no-reboot'
            ' -device pcnet,netdev=net0 -netdev tap,id=net0,ifname=tap0,script=no,downscript=no'
        ),
        net_iface="br-lan",
        boot_ready_prompt="entered forwarding state",
        qemu_timeout=30,
        image_zip_path="./MIPSEL/image.zip",
        image_kernel_path="/image/vmlinux",
        image_rootfs_path="/image/root.ext4",
        cd_before_analysis=True,
        extra_prompt_after_dns=True,
        extra_boot_prompt_phase2=True,
        exfiltrate_wait=10,
    ),
    "x86": ArchConfig(
        qemu_cmd_template=(
            'qemu-system-i386 -m 512 -kernel {kernel} -hda {rootfs}'
            ' -append "root=/dev/sda" -nographic -no-reboot'
            ' -device pcnet,netdev=net0 -netdev tap,id=net0,ifname=tap0,script=no,downscript=no'
        ),
        net_iface="br-lan",
        boot_ready_prompt="entered forwarding state",
        qemu_timeout=20,
        image_zip_path="./x86/image.zip",
        image_kernel_path="/image/vmlinux",
        image_rootfs_path="/image/root.ext4",
        cd_before_analysis=True,
        extra_prompt_after_dns=False,
        extra_boot_prompt_phase2=False,
        exfiltrate_wait=10,
        network_ready_prompt_optional=True,
    ),
}


def detect_arch(binary_path: str) -> str:
    """Detect the CPU architecture of an ELF binary using the file command.
    Reads ELF magic bytes, so works on stripped and statically linked binaries."""
    result = subprocess.run(['file', binary_path], capture_output=True, text=True)
    output = result.stdout
    logger.info(f"Binary type: {output.strip()}")

    # MIPS must be checked before ARM since MIPS output never contains "ARM"
    # Endianness distinguishes MIPS (MSB, big-endian) from MIPSEL (LSB, little-endian)
    if 'MIPS' in output and 'MSB' in output:
        return 'MIPS'
    if 'MIPS' in output and 'LSB' in output:
        return 'MIPSEL'
    if 'ARM' in output:
        return 'ARM'
    if '80386' in output:
        return 'x86'

    raise ValueError(f"Unsupported or unrecognized architecture: {output.strip()}")


class Analysis:
    def __init__(self, task_id, task_dir, qemu_ip, qemu_gw, kernel_path, rootfs_path, worker):
        self.task_id = task_id
        self.task_dir = task_dir
        self.qemu_ip = qemu_ip
        self.qemu_gw = qemu_gw
        self.kernel_path = kernel_path
        self.rootfs_path = rootfs_path
        self.worker = worker
        self.worker_base_url = (
            f"http://{worker['worker_ip']}:{app_settings.port}{app_settings.app_base_url}"
        )

    def _start_qemu(self, arch: ArchConfig) -> pexpect.spawn:
        qemu_cmd = arch.qemu_cmd_template.format(kernel=self.kernel_path, rootfs=self.rootfs_path)
        logger.info("Starting QEMU...")
        proc = pexpect.spawn(qemu_cmd, encoding='utf-8', timeout=arch.qemu_timeout)
        proc.logfile = open(self.task_dir + app_settings.qemu_log_path, 'w', encoding='utf-8')
        idx = proc.expect([pexpect.TIMEOUT, 'Please press Enter to activate this console.', pexpect.EOF])
        if idx == 0:
            raise RuntimeError("QEMU timed out waiting for boot prompt")
        proc.sendline("")
        idx = proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        if idx == 0:
            raise RuntimeError("QEMU timed out waiting for shell prompt after boot")
        logger.info("Started QEMU")
        return proc

    def _start_qemu_phase2(self, arch: ArchConfig) -> pexpect.spawn:
        """Boot QEMU for the exfiltration phase.
        MIPS/MIPSEL require an extra terminal poke after the initial prompt
        before the network-ready prompt appears."""
        proc = self._start_qemu(arch)
        if arch.extra_boot_prompt_phase2:
            proc.sendline("")
            proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        return proc

    def _configure_network(self, proc: pexpect.spawn, arch: ArchConfig):
        idx = proc.expect([pexpect.TIMEOUT, arch.boot_ready_prompt, pexpect.EOF])
        if idx == 0 and not arch.network_ready_prompt_optional:
            raise RuntimeError("QEMU timed out waiting for network-ready prompt")
        proc.sendline(f'ip addr add {self.qemu_ip}/24 brd + dev {arch.net_iface}')
        idx = proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        if idx == 0:
            raise RuntimeError("QEMU timed out after IP assignment")
        proc.sendline(f'route add default gw {self.qemu_gw} dev {arch.net_iface}')
        idx = proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        if idx == 0:
            raise RuntimeError("QEMU timed out after gateway setup")
        logger.info("Set IP in QEMU")
        proc.sendline('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
        proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        logger.info("Set DNS in QEMU")
        # MIPS/MIPSEL need an extra poke after DNS before the terminal is stable
        if arch.extra_prompt_after_dns:
            proc.sendline("")
            proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])

    def _run_analysis(self, proc: pexpect.spawn, arch: ArchConfig):
        if arch.cd_before_analysis:
            proc.sendline("cd /")
            proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])

        # Keep a backup of curl in case the malware overwrites or kills it
        proc.sendline("cp /usr/bin/curl /tmp/c")
        proc.sendline("ifconfig")
        proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])

        # Download the malware executable into the VM
        proc.sendline(
            f"/tmp/c --location '{self.worker_base_url}/get-task/{self.task_id}/file' -o exec"
        )
        idx = proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        if idx == 0:
            raise RuntimeError("QEMU timed out waiting for binary download")
        logger.debug(proc.before)
        proc.sendline("chmod +x ./exec")
        idx = proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        if idx == 0:
            raise RuntimeError("QEMU timed out after chmod")
        logger.debug(proc.before)
        logger.info("Got the executable inside QEMU")

        # Start network capture on the host
        net_proc = pexpect.spawn(
            f"tshark -i tap0 -w {self.task_dir}/network.pcap", encoding='utf-8', timeout=100
        )
        logger.info("Started network capture")

        # Start system resource monitor inside the VM
        proc.sendline("sar -o sar.out 1 >/dev/null 2>&1 & echo $! > sar_pid")
        proc.expect([pexpect.TIMEOUT, 'root@OpenWrt:/# ', pexpect.EOF])
        logger.info(f"Started sar (PID: {proc.before.strip()})")

        # Start syscall trace and execute the malware
        proc.sendline("strace -f -tt -T -y -yy -s 2048 -o /strace.log ./exec & echo $! > strace_pid")
        proc.expect([pexpect.TIMEOUT, 'root@OpenWrt:/# ', pexpect.EOF])
        logger.info(f"Started strace (PID: {proc.before.strip()})")

        # Let the malware run for the configured duration, checking for stop requests
        deadline = time.time() + app_settings.analysis_duration
        while time.time() < deadline:
            time.sleep(1)
            if os.path.exists(_STOP_FILE):
                net_proc.kill(signal.SIGINT)
                proc.kill(signal.SIGINT)
                raise AnalysisCancelled("Stop requested by user")

        proc.sendline("")
        proc.sendline("")
        proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        proc.sendline("ls")
        proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        logger.debug(proc.before)

        net_proc.kill(signal.SIGINT)
        logger.info("Stopped network capture")

        proc.sendline("kill -9 $(cat strace_pid)")
        proc.expect([pexpect.TIMEOUT, 'root@OpenWrt:/# ', pexpect.EOF])
        logger.debug(proc.before)
        logger.info("Killed strace")

        proc.sendline("kill -9 $(cat sar_pid)")
        proc.expect([pexpect.TIMEOUT, 'root@OpenWrt:/# ', pexpect.EOF])
        logger.debug(proc.before)
        logger.info("Killed sar")

        # Wait for the VM filesystem to flush captured files before shutdown
        time.sleep(app_settings.post_analysis_wait)

    def _exfiltrate(self, proc: pexpect.spawn, arch: ArchConfig):
        # Wait for the rebooted filesystem to fully settle before reading captured files
        if arch.exfiltrate_wait > 0:
            time.sleep(arch.exfiltrate_wait)
            proc.sendline("cd /")
            proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
            proc.sendline("ls")
            proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
            logger.debug(proc.before)

        logger.info("Uploading strace...")
        proc.sendline(
            f"curl --location '{self.worker_base_url}/update-task/{self.task_id}/strace'"
            f" --form 'file=@/strace.log'"
        )
        proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        logger.debug(proc.before)

        logger.info("Uploading sar...")
        proc.sendline(
            f"curl --location '{self.worker_base_url}/update-task/{self.task_id}/sar'"
            f" --form 'file=@/sar.out'"
        )
        proc.expect([pexpect.TIMEOUT, '# ', pexpect.EOF])
        logger.debug(proc.before)

    def behaviour_analysis(self, arch: ArchConfig):
        # Phase 1: Boot VM, execute malware, capture strace/sar/network data
        _check_stop()
        proc = self._start_qemu(arch)
        self._configure_network(proc, arch)
        self._run_analysis(proc, arch)
        logger.info("Shutting down QEMU...")
        proc.kill(signal.SIGINT)
        logger.info("QEMU shutdown complete")

        # Phase 2: Reboot VM to exfiltrate captured log files.
        # Files are read from the same virtual disk written in phase 1.
        _check_stop()
        proc = self._start_qemu_phase2(arch)
        self._configure_network(proc, arch)
        self._exfiltrate(proc, arch)
        logger.info("Shutting down QEMU...")
        proc.kill(signal.SIGINT)
        logger.info("QEMU shutdown complete")


_LOCK_FILE = "/tmp/sandbox_worker.lock"
_STOP_FILE = "/tmp/sandbox_stop_requested"


class AnalysisCancelled(RuntimeError):
    """Raised when a stop is requested via the /stop endpoint."""
    pass


def request_stop():
    """Create the stop-signal file. Called by the server process."""
    open(_STOP_FILE, 'w').close()


def clear_stop():
    """Remove the stop-signal file. Called by the poller before each task."""
    try:
        os.remove(_STOP_FILE)
    except FileNotFoundError:
        pass


def _check_stop():
    if os.path.exists(_STOP_FILE):
        raise AnalysisCancelled("Stop requested by user")


def dynamic_analysis(task_id, task_dir="", worker={}):
    with open(_LOCK_FILE, 'w') as _lock:
        try:
            fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another analysis is already running on this worker")
        _run_analysis_locked(task_id, task_dir, worker)


def _run_analysis_locked(task_id, task_dir="", worker={}):
    logger.info(f"Starting task: {task_id}")

    binary_path = task_dir + "/" + task_id
    arch_name = detect_arch(binary_path)
    logger.info(f"Detected architecture: {arch_name}")

    arch_config = ARCH_CONFIGS[arch_name]

    qemu_ip = str(ipaddress.IPv4Address(worker["worker_ip"]) + 1)
    qemu_gw = str(ipaddress.ip_network(qemu_ip + '/24', strict=False).network_address + 1)

    with ZipFile(arch_config.image_zip_path, 'r') as z:
        z.extractall(path=task_dir)

    kernel_path = task_dir + arch_config.image_kernel_path
    rootfs_path = task_dir + arch_config.image_rootfs_path

    analysis = Analysis(task_id, task_dir, qemu_ip, qemu_gw, kernel_path, rootfs_path, worker)
    analysis.behaviour_analysis(arch_config)
