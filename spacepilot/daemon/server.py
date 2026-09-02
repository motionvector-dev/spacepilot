"""Daemon listeners: a permission-authenticated UDS and a tailnet-only peer port."""

from __future__ import annotations

import asyncio
import datetime as dt
import errno
import fcntl
import ipaddress
import json
import os
import socket
import stat
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

import uvicorn

from spacepilot.daemon.api import FleetControl, PeerReads, create_local_app, create_peer_app
from spacepilot.daemon.picture import PictureSampler
from spacepilot.services.execution import LocalExecutionService
from spacepilot.substrate import DirectLocal, Substrate


DEFAULT_PEER_PORT = 8765


class DaemonAlreadyRunning(RuntimeError):
    pass


class UnsafeSocketPath(RuntimeError):
    pass


class TailnetUnavailable(RuntimeError):
    pass


class PeerListenerState:
    """Small thread-safe fact supplier for the local health/status route."""

    def __init__(self, state: str) -> None:
        self._lock = threading.Lock()
        self._value: dict[str, Any] = {}
        self.update(state)

    def update(self, state: str, *, address: str | None = None,
               error: str | None = None) -> None:
        with self._lock:
            self._value = {
                "state": state,
                "address": address,
                "error": error,
                "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._value)


class _PeerServer(uvicorn.Server):
    """Let the local UDS server own process signals for coordinated shutdown."""

    @contextmanager
    def capture_signals(self):  # uvicorn >= 0.30
        yield

    def install_signal_handlers(self) -> None:  # uvicorn 0.22 compatibility
        return None


@dataclass
class BoundUnixSocket:
    path: Path
    sock: socket.socket
    lock_fd: int
    inode: int


def _ensure_private_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise UnsafeSocketPath(f"daemon socket parent is a symlink: {path.parent}")
    st = path.parent.stat()
    if st.st_uid != os.getuid():
        raise UnsafeSocketPath(f"daemon socket parent is not owned by this user: {path.parent}")
    # This is a per-user authentication boundary, so remove group/other access
    # even when the directory predated the daemon with a permissive umask.
    path.parent.chmod(0o700)


def _lock_socket(path: Path) -> int:
    lock_path = path.with_name(path.name + ".lock")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise UnsafeSocketPath(f"cannot safely open daemon lock {lock_path}: {exc}") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            raise UnsafeSocketPath(f"daemon lock is not a user-owned regular file: {lock_path}")
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DaemonAlreadyRunning(f"daemon already owns {path}") from exc
        return fd
    except Exception:
        os.close(fd)
        raise


def _remove_stale_socket(path: Path) -> None:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(st.st_mode):
        raise UnsafeSocketPath(f"refusing to replace non-socket path: {path}")
    if st.st_uid != os.getuid():
        raise UnsafeSocketPath(f"refusing to replace a socket owned by another user: {path}")

    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        probe.settimeout(0.15)
        try:
            probe.connect(str(path))
        except OSError as exc:
            if exc.errno not in {errno.ECONNREFUSED, errno.ENOENT}:
                raise UnsafeSocketPath(f"cannot prove daemon socket is stale: {path}: {exc}") from exc
        else:
            raise DaemonAlreadyRunning(f"daemon is already listening on {path}")
    finally:
        probe.close()
    path.unlink()


@contextmanager
def bind_unix_socket(path: Path | str) -> Iterator[BoundUnixSocket]:
    """Exclusively bind a private UDS, cleaning only proven stale sockets."""
    requested = Path(path).expanduser()
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    # Resolve the parent, not the final component: resolving the whole path
    # would follow an attacker-created socket-path symlink before lstat could
    # reject it.
    resolved = requested.parent.resolve(strict=False) / requested.name
    if len(os.fsencode(str(resolved))) > 100:
        raise UnsafeSocketPath(
            f"daemon socket path is too long for portable AF_UNIX use ({len(os.fsencode(str(resolved)))} bytes): {resolved}"
        )
    _ensure_private_parent(resolved)
    lock_fd = _lock_socket(resolved)
    sock: socket.socket | None = None
    inode: int | None = None
    try:
        _remove_stale_socket(resolved)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(resolved))
        sock.listen(128)
        resolved.chmod(0o600)
        st = resolved.lstat()
        if st.st_uid != os.getuid() or not stat.S_ISSOCK(st.st_mode):
            raise UnsafeSocketPath(f"bound daemon path failed ownership/type check: {resolved}")
        inode = st.st_ino
        yield BoundUnixSocket(resolved, sock, lock_fd, inode)
    finally:
        if sock is not None:
            sock.close()
        if inode is not None:
            try:
                current = resolved.lstat()
                if stat.S_ISSOCK(current.st_mode) and current.st_ino == inode:
                    resolved.unlink()
            except FileNotFoundError:
                pass
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def discover_tailnet_ipv4(
    run: Callable[..., Any] | None = None,
) -> str:
    """Return only this node's exact CGNAT Tailscale IPv4 from status JSON."""
    if run is None:
        from spacepilot.cli import run_cmd
        run = run_cmd
    try:
        raw = run(
            ["tailscale", "status", "--json"],
            capture=True,
            timeout=3.0,
        )
        payload = json.loads(raw)
    except Exception as exc:
        raise TailnetUnavailable(f"tailscale status unavailable: {exc}") from exc
    addresses = payload.get("Self", {}).get("TailscaleIPs", []) if isinstance(payload, dict) else []
    if not isinstance(addresses, list):
        raise TailnetUnavailable("tailscale status Self.TailscaleIPs is not a list")
    tailnet = ipaddress.ip_network("100.64.0.0/10")
    for text in addresses:
        try:
            address = ipaddress.ip_address(text)
        except ValueError:
            continue
        if isinstance(address, ipaddress.IPv4Address) and address in tailnet:
            return str(address)
    raise TailnetUnavailable("tailscale status reported no exact CGNAT IPv4 for Self")


@contextmanager
def bind_peer_socket(ip: str, port: int) -> Iterator[socket.socket]:
    """Bind exactly one validated tailnet address, never a wildcard fallback."""
    address = ipaddress.ip_address(ip)
    if not isinstance(address, ipaddress.IPv4Address) or address not in ipaddress.ip_network("100.64.0.0/10"):
        raise TailnetUnavailable(f"refusing non-tailnet peer bind address: {ip}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((str(address), port))
        sock.listen(128)
        yield sock
    finally:
        sock.close()


async def _serve_peer(
    substrate: Substrate,
    *,
    stop: asyncio.Event,
    peer_port: int,
    peer_picture_signer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None,
    peer_reads: PeerReads | None,
    peer_authenticator: Any | None,
    fixed_ip: str | None,
    discover: bool,
    status: PeerListenerState,
    retry_seconds: float = 5.0,
) -> None:
    """Wait for Tailscale without delaying the local door, then serve exactly it."""
    while not stop.is_set():
        try:
            ip = fixed_ip
            if ip is None:
                if not discover:
                    status.update("disabled")
                    return
                ip = await asyncio.to_thread(discover_tailnet_ipv4)
            peer_context = bind_peer_socket(ip, peer_port)
            peer_sock = peer_context.__enter__()
        except (TailnetUnavailable, OSError) as exc:
            status.update("waiting", error=str(exc))
            if fixed_ip is not None:
                raise
            try:
                await asyncio.wait_for(stop.wait(), timeout=retry_seconds)
            except TimeoutError:
                continue
            return

        try:
            status.update("listening", address=f"{ip}:{peer_port}")
            peer = _PeerServer(uvicorn.Config(
                create_peer_app(
                    substrate,
                    picture_signer=peer_picture_signer,
                    peer_reads=peer_reads,
                    peer_authenticator=peer_authenticator,
                ),
                log_level="info", access_log=False,
            ))
            serving = asyncio.create_task(peer.serve(sockets=[peer_sock]))
            stopping = asyncio.create_task(stop.wait())
            done, _ = await asyncio.wait(
                {serving, stopping}, return_when=asyncio.FIRST_COMPLETED,
            )
            if stopping in done:
                peer.should_exit = True
                await serving
                return
            stopping.cancel()
            await asyncio.gather(stopping, return_exceptions=True)
            # An unexpected peer-server exit is not permission to widen the
            # bind. Re-discover this node's exact address before retrying.
            if fixed_ip is not None:
                await serving
                return
        finally:
            peer_context.__exit__(None, None, None)
            if not stop.is_set():
                status.update("waiting")


async def _serve(
    bound: BoundUnixSocket,
    substrate: Substrate,
    peer_ip: str | None,
    peer_port: int,
    peer_picture_signer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None,
    discover_peer: bool,
    peer_status: PeerListenerState,
    fleet: FleetControl | None = None,
    peer_reads: PeerReads | None = None,
    peer_authenticator: Any | None = None,
    fleet_status_supplier: Callable[[], Mapping[str, Any]] | None = None,
    lifecycle_components: tuple[Any, ...] = (),
) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_shutdown() -> None:
        loop.call_soon_threadsafe(stop.set)

    def health() -> dict[str, Any]:
        value: dict[str, Any] = {"peer": peer_status.snapshot()}
        if fleet_status_supplier is not None:
            try:
                value["fleet"] = dict(fleet_status_supplier())
            except Exception as exc:
                value["fleet"] = {"background": {"state": "degraded", "errors": [str(exc)]}}
        return value

    local = uvicorn.Server(uvicorn.Config(
        create_local_app(
            substrate,
            shutdown=request_shutdown,
            health_supplier=health,
            fleet=fleet,
        ),
        log_level="info",
        access_log=False,
    ))

    async def serve_local() -> None:
        serving = asyncio.create_task(local.serve(sockets=[bound.sock]))
        stopping = asyncio.create_task(stop.wait())
        done, _ = await asyncio.wait(
            {serving, stopping}, return_when=asyncio.FIRST_COMPLETED,
        )
        if stopping in done:
            local.should_exit = True
            await serving
        else:
            stop.set()
        stopping.cancel()
        await asyncio.gather(stopping, return_exceptions=True)

    started: list[Any] = []
    try:
        for component in lifecycle_components:
            starter = getattr(component, "start", None)
            if callable(starter):
                await asyncio.to_thread(starter)
            started.append(component)
        await asyncio.gather(
            serve_local(),
            _serve_peer(
                substrate,
                stop=stop,
                peer_port=peer_port,
                peer_picture_signer=peer_picture_signer,
                peer_reads=peer_reads,
                peer_authenticator=peer_authenticator,
                fixed_ip=peer_ip,
                discover=discover_peer,
                status=peer_status,
            ),
        )
    finally:
        for component in reversed(started):
            closer = getattr(component, "stop", None) or getattr(component, "close", None)
            if callable(closer):
                await asyncio.to_thread(closer)


def run_daemon(
    *,
    socket_path: Path,
    service: LocalExecutionService | None = None,
    sampler: PictureSampler | None = None,
    peer_port: int = DEFAULT_PEER_PORT,
    tailnet_ip: str | None = None,
    discover_tailnet: bool = True,
    identity: Any | None = None,
    fleet_control: FleetControl | None = None,
    fleet_manager: Any | None = None,
    orders_supplier: Callable[[], Any] | None = None,
    peer_reads: PeerReads | None = None,
    peer_authenticator: Any | None = None,
    fleet_runtime: Any | None = None,
    gossip_puller: Any | None = None,
    index_writer: Any | None = None,
) -> None:
    """Run the foreground daemon, honoring the exact supplied UDS path.

    An unavailable tailnet leaves the local daemon useful; it never widens to
    wildcard or LAN binding.  Passing ``tailnet_ip`` is primarily for a service
    wrapper or test and is validated again by ``bind_peer_socket``.
    """
    from spacepilot.daemon.identity import load_or_create, sign_picture

    machine_identity = identity or load_or_create()
    if service is None:
        # Match `spacepilot run`'s driver construction, including the existing
        # machine-local mflux_bin_dir config.  The execution logic itself stays
        # exclusively in LocalExecutionService.
        from spacepilot.cli import load_config
        from spacepilot.drivers.mflux_driver import MfluxDriver, mflux_bin_dir
        execution = LocalExecutionService(
            driver=MfluxDriver(bin_dir=mflux_bin_dir(load_config())),
        )
    else:
        execution = service
    picture = sampler or PictureSampler(identity_probe=lambda: {
        "key_id": machine_identity.key_id,
        "public_key": machine_identity.public_key_b64,
        "algorithm": "Ed25519",
    })
    substrate = DirectLocal(execution, picture_supplier=picture.sample)
    owns_fleet_runtime = False
    if fleet_runtime is None and all(value is None for value in (
        fleet_control, fleet_manager, orders_supplier, peer_reads, peer_authenticator,
    )):
        from spacepilot.daemon.identity import Identity
        if isinstance(machine_identity, Identity):
            from spacepilot.daemon.index import IndexWriter
            from spacepilot.daemon.runtime import build_runtime
            fleet_runtime = build_runtime(
                machine_identity, peer_port=peer_port,
                index_writer=index_writer or IndexWriter(),
            )
            index_writer = None  # FleetRuntime now owns this writer exactly once.
            owns_fleet_runtime = True
    if fleet_runtime is not None:
        fleet_control = fleet_control or fleet_runtime.controls()
        peer_reads = peer_reads or fleet_runtime.peer_reads()
        peer_authenticator = peer_authenticator or fleet_runtime.peer_authenticator()
    if fleet_control is None and fleet_manager is not None and orders_supplier is not None:
        fleet_control = FleetControl(
            snapshot=lambda: fleet_manager.refresh(orders_supplier()).to_wire(),
        )
    peer_status = PeerListenerState(
        "waiting" if tailnet_ip is not None or discover_tailnet else "disabled"
    )
    try:
        with bind_unix_socket(socket_path) as bound:
            asyncio.run(_serve(
                bound,
                substrate,
                tailnet_ip,
                peer_port,
                lambda value: sign_picture(machine_identity, value),
                discover_tailnet,
                peer_status,
                fleet_control,
                peer_reads,
                peer_authenticator,
                fleet_runtime.status if fleet_runtime is not None else None,
                tuple(component for component in (
                    fleet_manager, gossip_puller, index_writer,
                    *(fleet_runtime.lifecycle_components() if fleet_runtime is not None else ()),
                ) if component is not None),
            ))
    finally:
        # _serve normally closes these. This also covers a bind/start failure
        # after the default runtime created its background index writer.
        if owns_fleet_runtime:
            for component in fleet_runtime.lifecycle_components():
                closer = getattr(component, "close", None)
                if callable(closer):
                    closer()
