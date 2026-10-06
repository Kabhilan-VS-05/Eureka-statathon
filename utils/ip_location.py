"""
IP Geolocation Utility
Resolves an IP address to city, state, and country using ip-api.com.
- No API key required (free tier: 1,000 req/min).
- Results are cached in-memory to avoid duplicate lookups.
- Private/loopback IPs return default India values for local development.
- All errors are silently caught so searches are never blocked.
"""

import requests
import ipaddress

# In-memory cache: ip -> {city, state, country}
_ip_cache = {}

# IPs that are definitely private/local
_PRIVATE_RESULT = {"city": "", "state": "", "country": "India"}
_EMPTY_RESULT = {"city": "", "state": "", "country": ""}

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def resolve_ip_location(ip: str) -> dict:
    """
    Resolve an IP address to geographic location.

    Returns a dict with keys: city, state, country.
    All values are strings; may be empty if lookup fails.
    """
    if not ip:
        return dict(_EMPTY_RESULT)

    ip = ip.strip()

    # Return cached result
    if ip in _ip_cache:
        return dict(_ip_cache[ip])

    # Return default for private/loopback IPs
    if _is_private(ip):
        result = dict(_PRIVATE_RESULT)
        _ip_cache[ip] = result
        return result

    # Fully airgapped offline mode: do not query external IP API
    result = dict(_EMPTY_RESULT)
    _ip_cache[ip] = result
    return result
