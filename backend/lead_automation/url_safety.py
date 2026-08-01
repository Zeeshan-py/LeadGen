"""URL safety checks for outbound lead-enrichment requests."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
}
BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".home.arpa",
)


def is_safe_public_url(value: str, *, resolve: bool = False) -> bool:
    """Allow only public HTTP(S) URLs before server-side fetches."""
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    hostname = (parsed.hostname or "").strip().strip(".").lower()
    if not hostname:
        return False
    if parsed.username or parsed.password:
        return False
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(BLOCKED_HOST_SUFFIXES):
        return False
    if _unsafe_ip_literal(hostname):
        return False
    if resolve and not _resolves_to_public_ips(hostname, parsed.port or _default_port(parsed.scheme)):
        return False
    return True


def _unsafe_ip_literal(hostname: str) -> bool:
    try:
        return not ipaddress.ip_address(hostname).is_global
    except ValueError:
        return False


def _resolves_to_public_ips(hostname: str, port: int) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        address = info[4][0]
        try:
            if not ipaddress.ip_address(address).is_global:
                return False
        except ValueError:
            return False
    return True


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80
