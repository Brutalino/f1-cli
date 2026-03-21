"""
f1-cli — Formula 1 Live Timing in your Terminal.

Usage:
    f1-cli                  Full view (live timing)
    f1-cli -t               Times only (GAP, INT, LAST, BEST)
    f1-cli -s               Simple (positions + GAP only)
    f1-cli demo             Simulated race
    f1-cli login            Authenticate with F1TV (opens browser)
    f1-cli logout           Remove saved auth token
    f1-cli status           Show auth status
    f1-cli --help           Show help

Toggle keys while running:
    s  sectors    t  tyres+pit    c  race control    q  quit
"""

from __future__ import annotations

import argparse
import sys


def cmd_live(args):
    from .data_store import DataStore
    from .live_client import F1LiveClient
    from .app import run_app

    store = DataStore()

    if not args.no_auth:
        from .auth import ensure_auth
        ensure_auth()

    save_file = None
    if args.save:
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_file = f"f1_live_{ts}.txt"
        print(f"  Saving to: {save_file}")

    client = F1LiveClient(
        store=store,
        save_file=save_file,
        no_auth=args.no_auth,
        timeout=args.timeout,
    )
    client.start_background()

    try:
        run_app(store, view=args.view)
    finally:
        client.stop()


def cmd_demo(args):
    from .data_store import DataStore
    from .demo_data import DemoRunner
    from .app import run_app

    store = DataStore()
    demo = DemoRunner(store, speed=args.speed)
    demo.start_background()

    try:
        run_app(store, view=args.view)
    finally:
        demo.stop()


def cmd_login(args):
    from .auth import ensure_auth
    print("  Opening browser for F1TV login...")
    ensure_auth()


def cmd_logout(args):
    from .auth import logout
    logout()


def cmd_status(args):
    from .auth import show_status
    show_status()


def main():
    parser = argparse.ArgumentParser(
        prog="f1-cli",
        description="F1 Live Timing in your Terminal",
        epilog="Toggle keys: s=sectors  t=tyres+pit  c=race control  q=quit",
    )

    view_group = parser.add_mutually_exclusive_group()
    view_group.add_argument(
        "-t", "--times", action="store_const", dest="view", const="times",
        help="Times view: GAP, INT, LAST, BEST",
    )
    view_group.add_argument(
        "-s", "--simple", action="store_const", dest="view", const="simple",
        help="Simple view: positions + GAP only",
    )
    parser.set_defaults(view="full")

    sub = parser.add_subparsers(dest="command")

    # demo
    p_demo = sub.add_parser("demo", help="Simulated race")
    p_demo.add_argument("--speed", type=float, default=2.0, help="Speed multiplier")
    demo_view = p_demo.add_mutually_exclusive_group()
    demo_view.add_argument("-t", "--times", action="store_const", dest="view", const="times")
    demo_view.add_argument("-s", "--simple", action="store_const", dest="view", const="simple")
    p_demo.set_defaults(view="full")

    # live
    p_live = sub.add_parser("live", help="Connect to F1 live timing")
    p_live.add_argument("--save", action="store_true", help="Save raw data to file")
    p_live.add_argument("--no-auth", action="store_true", help="Skip F1TV auth")
    p_live.add_argument("--timeout", type=int, default=120, help="Timeout seconds")
    live_view = p_live.add_mutually_exclusive_group()
    live_view.add_argument("-t", "--times", action="store_const", dest="view", const="times")
    live_view.add_argument("-s", "--simple", action="store_const", dest="view", const="simple")
    p_live.set_defaults(view="full")

    # auth commands
    sub.add_parser("login", help="Authenticate with F1TV (opens browser)")
    sub.add_parser("logout", help="Remove saved auth token")
    sub.add_parser("status", help="Show auth status")

    args = parser.parse_args()

    if args.command == "demo":
        cmd_demo(args)
    elif args.command == "live":
        cmd_live(args)
    elif args.command == "login":
        cmd_login(args)
    elif args.command == "logout":
        cmd_logout(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command is None:
        args.save = False
        args.no_auth = False
        args.timeout = 120
        cmd_live(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
