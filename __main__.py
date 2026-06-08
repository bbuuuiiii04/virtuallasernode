"""CLI entry point + wiring.  Run:  python3 -m virtuallasernode --web"""

import argparse
import sys

from . import __version__
from .artnet import (ADVERTISED_UNIVERSES, ARTNET_PORT, ArtNetNode,
                     broadcast_ip_for, detect_local_ip, open_socket)
from .fixtures import FIXTURES
from .util import log
from .webserver import start_web_server


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="virtuallasernode",
        description="VirtualLaserNode — virtual Art-Net node + ArtDMX "
                    "inspector for SoundSwitch.")
    p.add_argument("--dump-all", action="store_true",
                   help="log EVERY Art-Net packet with no throttling")
    p.add_argument("--changes-only", action="store_true",
                   help="for ArtDMX, log only frames where channels changed")
    p.add_argument("--quiet-poll-replies", action="store_true",
                   help="always suppress our own ArtPollReply echoes")
    p.add_argument("--web", action="store_true",
                   help="start the browser channel inspector (HTTP + SSE)")
    p.add_argument("--web-port", type=int, default=8137,
                   help="port for the web inspector (default 8137)")
    p.add_argument("--bind-ip", action="append", default=[], metavar="IP",
                   help="extra specific local IP to bind for ArtDMX receive "
                        "(repeatable; for multi-homed machines)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    local_ip = detect_local_ip()
    bcast_targets = sorted({"255.255.255.255", broadcast_ip_for(local_ip)})

    # Wildcard socket: receives broadcast ArtPoll, sends broadcast replies.
    sock = open_socket("0.0.0.0", broadcast=True)
    if sock is None:
        log(f"FATAL: could not bind 0.0.0.0:{ARTNET_PORT}. Another Art-Net app "
            f"(or a previous instance) may hold the port. Close it and retry.")
        sys.exit(1)

    # Specific-IP sockets win the unicast demux for ArtDMX.
    recv_socks = [("0.0.0.0", sock)]
    for ip in dict.fromkeys(["127.0.0.1", local_ip, *args.bind_ip]):
        if ip == "0.0.0.0":
            continue
        s = open_socket(ip)
        if s is not None:
            recv_socks.append((ip, s))

    node = ArtNetNode(
        local_ip, bcast_targets, sock, recv_socks,
        dump_all=args.dump_all,
        changes_only=args.changes_only,
        quiet_poll_replies=args.quiet_poll_replies,
    )

    # ---- startup banner ----
    log(f"VirtualLaserNode v{__version__} starting")
    log(f"Receive sockets bound: {[ip for ip, _ in recv_socks]} "
        f"(port {ARTNET_PORT})")
    log(f"Local detected IP: {local_ip}")
    log(f"Broadcast targets: {bcast_targets}")
    log(f"Advertised universes: {', '.join(str(u) for u in ADVERTISED_UNIVERSES)}")
    log(f"Fixtures patched: {len(FIXTURES)} "
        f"({', '.join(f['name'] for f in FIXTURES)})")
    mode = ("dump-all" if args.dump_all
            else "changes-only" if args.changes_only else "default")
    log(f"Log mode: {mode}")

    node.send_reply("startup announce", force_log=True)

    if args.web:
        try:
            start_web_server(node, args.web_port)
            log(f"Web inspector: http://127.0.0.1:{args.web_port}/")
        except OSError as e:
            log(f"Web inspector failed to start on port {args.web_port}: {e}")

    log("Waiting for ArtPoll / ArtDMX")
    try:
        node.run()
    except KeyboardInterrupt:
        log("Shutting down (KeyboardInterrupt).")
        sys.exit(0)


if __name__ == "__main__":
    main()
