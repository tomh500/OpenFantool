"""Keep the source edition's network activity on the local machine."""

from functools import cache
import ipaddress
import os
import socket
from urllib.error import URLError
from urllib.request import OpenerDirector
import webbrowser

import requests
from PySide6.QtGui import QDesktopServices

from core.runtime.source_options import OFFLINE_MESSAGE, remote_network_blocked


_IP_FAMILIES = (socket.AF_INET, socket.AF_INET6)


def _local_host(host, family=0):
    if isinstance(host, bytes):
        host = host.decode("ascii")
    if host.lower() == "localhost":
        return "::1" if family == socket.AF_INET6 else "127.0.0.1"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise PermissionError(OFFLINE_MESSAGE) from None
    if address.is_loopback:
        return str(address)
    raise PermissionError(OFFLINE_MESSAGE)


def _local_address(sock, address):
    if sock.family not in _IP_FAMILIES:
        return address
    return (_local_host(address[0], sock.family), *address[1:])


def _install_socket_guard():
    bind = socket.socket.bind
    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex
    sendto = socket.socket.sendto
    getaddrinfo = socket.getaddrinfo
    getnameinfo = socket.getnameinfo

    def bind_local(sock, address):
        return bind(sock, _local_address(sock, address))

    def connect_local(sock, address):
        return connect(sock, _local_address(sock, address))

    def connect_ex_local(sock, address):
        return connect_ex(sock, _local_address(sock, address))

    def sendto_local(sock, data, *args):
        if args:
            args = (*args[:-1], _local_address(sock, args[-1]))
        return sendto(sock, data, *args)

    def resolve_local(host, port, family=0, type=0, proto=0, flags=0):
        if host is not None:
            host = _local_host(host, family)
        return getaddrinfo(host, port, family, type, proto, flags)

    def reverse_local(ip):
        address = _local_host(ip)
        return "localhost", [], [address]

    def host_addresses(name):
        address = _local_host(name)
        return name, [], [address]

    def name_info_local(address, flags):
        address = (_local_host(address[0]), *address[1:])
        return getnameinfo(address, flags | socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)

    socket.socket.bind = bind_local
    socket.socket.connect = connect_local
    socket.socket.connect_ex = connect_ex_local
    socket.socket.sendto = sendto_local
    socket.getaddrinfo = resolve_local
    socket.gethostbyname = _local_host
    socket.gethostbyname_ex = host_addresses
    socket.gethostbyaddr = reverse_local
    socket.getnameinfo = name_info_local


@cache
def activate_remote_policy():
    if not remote_network_blocked():
        return

    original_open_url = QDesktopServices.openUrl
    original_startfile = os.startfile

    def block_requests(*args, **kwargs):
        # Block before the transport can use a localhost HTTP proxy.
        raise requests.exceptions.ConnectionError(OFFLINE_MESSAGE)

    def block_urllib(*args, **kwargs):
        raise URLError(OFFLINE_MESSAGE)

    def open_local_file(url):
        path = url.toLocalFile().replace("\\", "/")
        if url.isLocalFile() and not url.host() and not path.startswith("//"):
            return original_open_url(url)
        return False

    def start_local_file(path, *args, **kwargs):
        name = os.fsdecode(path).replace("\\", "/")
        if name.startswith("//") or "://" in name:
            raise PermissionError(OFFLINE_MESSAGE)
        return original_startfile(path, *args, **kwargs)

    _install_socket_guard()
    requests.Session.send = block_requests
    OpenerDirector.open = block_urllib
    QDesktopServices.openUrl = staticmethod(open_local_file)
    os.startfile = start_local_file
    webbrowser.open = lambda *args, **kwargs: False


def configure_text_links(browser):
    """Control links that QTextBrowser otherwise opens through native Qt."""
    enabled = not remote_network_blocked()
    browser.setOpenLinks(enabled)
    browser.setOpenExternalLinks(enabled)
