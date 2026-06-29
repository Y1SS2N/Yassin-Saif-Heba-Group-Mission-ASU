#!/usr/bin/env python3
"""
============================================================
ERC NAV BENCHMARK — Master Run Script
============================================================
Usage:
  python3 run_benchmark.py --level 1
  python3 run_benchmark.py --level 2 --no-teleop
  python3 run_benchmark.py --level 3 --rviz
  python3 run_benchmark.py --level 1 --headless

Arguments:
  --level      [1|2|3]   Difficulty level (required)
  --no-teleop            Skip teleop node (for autonomous testing)
  --rviz                 Launch RViz visualizer
  --headless             Run Gazebo without GUI
  --list-logs            List all saved run reports and exit

This script:
  1. Validates the environment (ROS 2, Gazebo, package build)
  2. Exports GAZEBO_MODEL_PATH
  3. Launches everything via ros2 launch
  4. Handles Ctrl-C cleanly
============================================================
"""

import argparse
import os
import subprocess
import sys
import glob
import signal
import time

# ── Terminal colours ─────────────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR     = os.path.join(SCRIPT_DIR, 'logs')
INSTALL_DIR  = os.path.join(SCRIPT_DIR, 'install')
PKG_NAME     = 'erc_nav_benchmark'


# ─────────────────────────────────────────────────────────────────────────────
#  ARGUMENT PARSING
# ─────────────────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description='ERC Navigation Benchmark – Master Launch Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 run_benchmark.py --level 1\n"
            "  python3 run_benchmark.py --level 2 --rviz\n"
            "  python3 run_benchmark.py --level 3 --headless --no-teleop\n"
        )
    )
    parser.add_argument('--level',     type=int, choices=[1, 2, 3],
                        required=True, help='Difficulty level (1=easy, 2=medium, 3=hard)')
    parser.add_argument('--no-teleop', action='store_true',
                        help='Disable keyboard teleop (for autonomous stack testing)')
    parser.add_argument('--rviz',      action='store_true',
                        help='Launch RViz2 visualizer alongside simulation')
    parser.add_argument('--headless',  action='store_true',
                        help='Run Gazebo without GUI (gzserver only)')
    parser.add_argument('--list-logs', action='store_true',
                        help='Print all saved run reports and exit')
    return parser.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
#  LOG VIEWER
# ─────────────────────────────────────────────────────────────────────────────
def list_logs():
    print(f"\n{CYAN}{BOLD}ERC NAV BENCHMARK — Saved Run Reports{RESET}")
    print(f"{CYAN}{'='*60}{RESET}")
    if not os.path.isdir(LOGS_DIR):
        print(f"{YELLOW}  No logs directory found yet.{RESET}")
        return

    logs = sorted(glob.glob(os.path.join(LOGS_DIR, '*.txt')), reverse=True)
    if not logs:
        print(f"{YELLOW}  No run reports saved yet.{RESET}")
        return

    for log in logs:
        name = os.path.basename(log)
        size = os.path.getsize(log)
        print(f"\n  {GREEN}{name}{RESET}  ({size} bytes)")
        with open(log) as f:
            print(f.read())
    print(f"{CYAN}{'='*60}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
#  ENVIRONMENT CHECKS
# ─────────────────────────────────────────────────────────────────────────────
def check_environment():
    print(f"\n{CYAN}Running pre-flight checks…{RESET}")
    ok = True

    # 1. ROS 2 sourced?
    if not os.environ.get('ROS_DISTRO'):
        print(f"  {RED}✗ ROS 2 not sourced. Run: source /opt/ros/<distro>/setup.bash{RESET}")
        ok = False
    else:
        print(f"  {GREEN}✓ ROS 2 distro: {os.environ['ROS_DISTRO']}{RESET}")

    # 2. Gazebo installed?
    gz_check = subprocess.run(['which', 'gazebo'], capture_output=True)
    if gz_check.returncode != 0:
        print(f"  {RED}✗ Gazebo not found. Install: sudo apt install ros-$ROS_DISTRO-gazebo-ros-pkgs{RESET}")
        ok = False
    else:
        print(f"  {GREEN}✓ Gazebo found{RESET}")

    # 3. Package installed/built?
    pkg_check = subprocess.run(
        ['ros2', 'pkg', 'list'],
        capture_output=True, text=True
    )
    if PKG_NAME not in pkg_check.stdout:
        print(
            f"  {YELLOW}⚠ Package '{PKG_NAME}' not found in ROS path.\n"
            f"    Run:  colcon build --packages-select {PKG_NAME}\n"
            f"          source install/setup.bash{RESET}"
        )
        # Not fatal — user might be running from source
    else:
        print(f"  {GREEN}✓ Package '{PKG_NAME}' available{RESET}")

    # 4. Python dependencies
    for dep in ['yaml', 'math', 'rclpy']:
        try:
            __import__(dep)
            print(f"  {GREEN}✓ Python: {dep}{RESET}")
        except ImportError:
            print(f"  {YELLOW}⚠ Python module '{dep}' not found{RESET}")

    return ok


# ─────────────────────────────────────────────────────────────────────────────
#  LAUNCH
# ─────────────────────────────────────────────────────────────────────────────
def launch(args):
    teleop   = 'false' if args.no_teleop else 'true'
    rviz     = 'true'  if args.rviz      else 'false'
    headless = 'true'  if args.headless  else 'false'

    # Set up GAZEBO_MODEL_PATH so Gazebo finds our rover
    models_path = os.path.join(SCRIPT_DIR, 'install', PKG_NAME, 'share', PKG_NAME, 'models')
    if not os.path.isdir(models_path):
        # Fallback: running from source (not installed)
        models_path = os.path.join(SCRIPT_DIR, 'models')

    env = os.environ.copy()
    existing = env.get('GAZEBO_MODEL_PATH', '')
    env['GAZEBO_MODEL_PATH'] = models_path + (':' + existing if existing else '')

    cmd = [
        'ros2', 'launch',
        PKG_NAME, 'benchmark.launch.py',
        f'level:={args.level}',
        f'teleop:={teleop}',
        f'rviz:={rviz}',
        f'headless:={headless}',
    ]

    print(f"\n{CYAN}{BOLD}")
    print("============================================================")
    print("              ERC NAV BENCHMARK STARTING                   ")
    print("============================================================")
    print(f"  Level    : {args.level}  {'(Easy)' if args.level==1 else '(Medium)' if args.level==2 else '(Hard)'}")
    print(f"  Teleop   : {'Enabled — use WASD keys' if not args.no_teleop else 'Disabled'}")
    print(f"  RViz     : {'Yes' if args.rviz else 'No'}")
    print(f"  Headless : {'Yes' if args.headless else 'No (GUI)'}")
    print("============================================================")
    print(f"  Command  : {' '.join(cmd)}")
    print(f"============================================================{RESET}")
    print(f"\n{YELLOW}Press Ctrl-C to abort at any time.{RESET}\n")

    proc = None
    try:
        proc = subprocess.Popen(cmd, env=env)
        proc.wait()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupt received — shutting down…{RESET}")
    finally:
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            time.sleep(1.0)
            if proc.poll() is None:
                proc.kill()
        # Clean up any orphaned Gazebo processes
        subprocess.run(['pkill', '-f', 'gzserver'], capture_output=True)
        subprocess.run(['pkill', '-f', 'gzclient'], capture_output=True)
        print(f"\n{CYAN}Benchmark session ended.{RESET}")
        print(f"Logs saved in: {LOGS_DIR}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    if args.list_logs:
        list_logs()
        sys.exit(0)

    env_ok = check_environment()

    if not env_ok:
        print(
            f"\n{RED}Pre-flight checks failed. "
            f"Fix the issues above before running.{RESET}\n"
        )
        sys.exit(1)

    print(f"\n{GREEN}All checks passed.{RESET}")
    launch(args)


if __name__ == '__main__':
    main()
