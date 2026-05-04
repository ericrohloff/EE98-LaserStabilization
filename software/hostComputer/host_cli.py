import argparse
import shlex
import time

try:
    from .pynq_client import PYNQController
except ImportError:
    from pynq_client import PYNQController


def _parse_cli_value(raw: str):
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        return int(raw, 0)
    except ValueError:
        return raw


def _parse_cli_command(spec: str):
    """Parse one CLI command spec into method name, args, and kwargs."""
    parts = shlex.split(spec)
    if not parts:
        raise ValueError("Command spec cannot be empty.")

    method_name = parts[0]
    args = []
    kwargs = {}

    for token in parts[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            kwargs[key] = _parse_cli_value(value)
        else:
            args.append(_parse_cli_value(token))

    return method_name, args, kwargs


def _run_interactive_commands(ctrl: PYNQController) -> bool:
    """Run user-entered API commands until the user exits interactive mode."""
    print("Interactive command mode enabled.")
    print("Enter one API call per line (example: create_laser laser_id=2 pid_param1=120 pid_param2=12 pid_param3=2)")
    print("Type 'help' for available calls. Type 'exit' or 'quit' to stop.")

    available = [
        "create_laser",
        "remove_laser",
        "lock_laser",
        "unlock_laser",
        "start_cavity",
        "stop_cavity",
        "request_adc_data",
        "send_command",
    ]

    all_ok = True
    while True:
        raw = input("pynq> ").strip()
        if not raw:
            continue
        if raw.lower() in {"exit", "quit"}:
            break
        if raw.lower() == "help":
            print("Available methods:")
            for name in available:
                print(f"- {name}")
            continue

        try:
            method_name, args, kwargs = _parse_cli_command(raw)
            method = getattr(ctrl, method_name, None)
            if method is None or not callable(method):
                raise ValueError(f"Unknown API method: {method_name}")

            result = method(*args, **kwargs)
            ok = bool(result) if isinstance(result, bool) else True
            all_ok = all_ok and ok
            print(f"{method_name} -> {result}")
            if not ctrl.is_connected:
                print("Connection to server lost. Exiting interactive mode.")
                return False
            if isinstance(result, bool) and not result:
                print("Command failed. Exiting interactive mode.")
                return False
        except Exception as exc:
            all_ok = False
            print(f"Command failed: {exc}")
            if not ctrl.is_connected:
                print("Connection to server lost. Exiting interactive mode.")
                return False

    return all_ok


def _run_cli_commands(ctrl: PYNQController, commands: list[str]) -> bool:
    """Run a list of user-provided API command specs."""
    all_ok = True
    for idx, spec in enumerate(commands, start=1):
        method_name, args, kwargs = _parse_cli_command(spec)
        method = getattr(ctrl, method_name, None)
        if method is None or not callable(method):
            raise ValueError(
                f"Unknown API method in --command #{idx}: {method_name}")

        print(f"> {spec}")
        result = method(*args, **kwargs)
        ok = bool(result) if isinstance(result, bool) else True
        all_ok = all_ok and ok
        print(f"  {result}")
        if not ctrl.is_connected:
            print("Connection to server lost. Exiting.")
            return False
        if isinstance(result, bool) and not result:
            print("Command failed. Exiting.")
            return False
    return all_ok


def _load_commands_from_file(path: str) -> list[str]:
    """Load command specs from a text file."""
    commands: list[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            spec = line.strip()
            if not spec or spec.startswith("#"):
                continue
            commands.append(spec)
    return commands


def _run_default_feedback_demo(ctrl: PYNQController) -> None:
    """Run the original step-by-step feedback-loop demo."""
    print("Feedback-loop test plan:")
    for step in PYNQController.feedback_loop_test_plan():
        print(f"- {step}")
    print()

    def run_step(label: str, action) -> bool:
        print(f"> {label}")
        ok = action()
        print(f"  {'OK' if ok else 'FAILED'}")
        return ok

    if run_step("create_laser(laser_id=1, p1=100, p2=10, p3=1)", lambda: ctrl.create_laser(laser_id=1, pid_param1=100, pid_param2=10, pid_param3=1)):
        if not run_step("create_laser(laser_id=2, p1=120, p2=12, p3=2)", lambda: ctrl.create_laser(laser_id=2, pid_param1=120, pid_param2=12, pid_param3=2)):
            raise SystemExit(1)
    else:
        raise SystemExit(1)

    if not run_step("lock_laser(laser_id=1, p1=1500, p2=20, p3=3, duration=15)", lambda: ctrl.lock_laser(laser_id=1, pid_param1=1500, pid_param2=20, pid_param3=3, duration=15)):
        raise SystemExit(1)
    if not run_step("start_cavity(duration=30)", lambda: ctrl.start_cavity(duration=30)):
        raise SystemExit(1)

    time.sleep(1)

    if not run_step("lock_laser(laser_id=2, p1=1550, p2=25, p3=2, duration=10)", lambda: ctrl.lock_laser(laser_id=2, pid_param1=1550, pid_param2=25, pid_param3=2, duration=10)):
        raise SystemExit(1)
    if not run_step("stop_cavity()", lambda: ctrl.stop_cavity()):
        raise SystemExit(1)

    if not run_step("unlock_laser(laser_id=1)", lambda: ctrl.unlock_laser(laser_id=1)):
        raise SystemExit(1)
    if not run_step("unlock_laser(laser_id=2)", lambda: ctrl.unlock_laser(laser_id=2)):
        raise SystemExit(1)
    if not run_step("remove_laser(laser_id=1)", lambda: ctrl.remove_laser(laser_id=1)):
        raise SystemExit(1)
    if not run_step("remove_laser(laser_id=2)", lambda: ctrl.remove_laser(laser_id=2)):
        raise SystemExit(1)


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PYNQ laser controller CLI",
    )
    parser.add_argument("--ip", default="192.168.3.1",
                        help="PYNQ server IP address")
    parser.add_argument("--port", type=int, default=5000,
                        help="PYNQ server TCP port")
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Socket timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "-c",
        "--command",
        action="append",
        default=[],
        help=(
            "Controller API command to run. Can be provided multiple times. "
            "Example: --command \"create_laser laser_id=2 pid_param1=120 pid_param2=12 pid_param3=2\""
        ),
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run an interactive prompt to enter API commands",
    )
    parser.add_argument(
        "--commands-file",
        action="append",
        default=[],
        help=(
            "Path to a text file containing API commands, one per line. "
            "Can be provided multiple times."
        ),
    )
    return parser


def run_cli(args: argparse.Namespace) -> int:
    """Execute CLI workflow from parsed args and return process exit code."""
    with PYNQController(server_ip=args.ip, server_port=args.port, timeout=args.timeout) as ctrl:
        if not ctrl.is_connected:
            print("Could not reach PYNQ board - check IP/port and board status.")
            return 1

        combined_commands: list[str] = []
        for file_path in args.commands_file:
            combined_commands.extend(_load_commands_from_file(file_path))
        combined_commands.extend(args.command)

        if combined_commands:
            ok = _run_cli_commands(ctrl, combined_commands)
            return 0 if ok else 1

        if args.interactive:
            ok = _run_interactive_commands(ctrl)
            return 0 if ok else 1

        _run_default_feedback_demo(ctrl)
        return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for script/module execution."""
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
