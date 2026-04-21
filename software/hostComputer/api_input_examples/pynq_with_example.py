"""Minimal example showing context-manager usage for PYNQController.

Run from repository root:
  python examples/pynq_with_example.py --ip 192.168.3.1 --port 5000
"""

from __future__ import annotations

import argparse
import pathlib
import sys

# Ensure repository root is importable when this script is run from examples/.
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.host_api import PYNQController


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Context-manager example for PYNQController")
    parser.add_argument("--ip", default="192.168.3.1", help="PYNQ server IP")
    parser.add_argument("--port", type=int, default=5000, help="PYNQ server port")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    with PYNQController(server_ip=args.ip, server_port=args.port) as ctrl:
        if not ctrl.is_connected:
            print("Connection failed.")
            return 1

        ok = True
        ok = ok and ctrl.create_laser(laser_id=1, pid_param1=100, pid_param2=10, pid_param3=1)
        ok = ok and ctrl.lock_laser(laser_id=1, pid_param1=1500, pid_param2=20, pid_param3=3, duration=15)
        ok = ok and ctrl.start_cavity(duration=20)
        ok = ok and ctrl.stop_cavity()
        ok = ok and ctrl.unlock_laser(laser_id=1)
        ok = ok and ctrl.remove_laser(laser_id=1)

        print("Example completed." if ok else "Example completed with errors.")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
