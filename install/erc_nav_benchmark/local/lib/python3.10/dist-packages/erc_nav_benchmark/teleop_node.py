#!/usr/bin/env python3
"""
============================================================
ERC NAV BENCHMARK - Teleop Node
============================================================
Keyboard-controlled rover driving for benchmark testing.

Controls:
  W / ↑   : Forward
  S / ↓   : Backward
  A / ←   : Turn left
  D / →   : Turn right
  Q       : Spin left (in-place)
  E       : Spin right (in-place)
  SPACE   : Emergency stop
  X       : Quit

Speed can be adjusted with +/- keys.
============================================================
"""

import sys
import os
import select
import termios
import tty
import threading
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


# ── Constants ────────────────────────────────────────────────────────────────
LINEAR_STEP  = 0.05   # m/s per increment
ANGULAR_STEP = 0.1    # rad/s per increment
MAX_LINEAR   = 0.8    # m/s
MAX_ANGULAR  = 1.5    # rad/s
MIN_SPEED    = 0.1

# Display colours
CYAN  = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED   = "\033[91m"
BOLD  = "\033[1m"
RESET = "\033[0m"

KEY_BINDINGS = {
    'w': ( 1,  0),   # forward
    's': (-1,  0),   # backward
    'a': ( 0,  1),   # turn left
    'd': ( 0, -1),   # turn right
    'q': ( 0,  2),   # spin left fast
    'e': ( 0, -2),   # spin right fast
    '\x1b[A': (1, 0),  # up arrow
    '\x1b[B': (-1, 0), # down arrow
    '\x1b[C': (0, -1), # right arrow
    '\x1b[D': (0, 1),  # left arrow
}

STOP_KEYS  = {' ', 'x', 'X', '\x03'}   # space, x, Ctrl-C


# ─────────────────────────────────────────────────────────────────────────────
#  TELEOP NODE
# ─────────────────────────────────────────────────────────────────────────────
class TeleopNode(Node):

    def __init__(self):
        super().__init__('teleop_node')

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.linear_speed  = 0.3   # m/s default
        self.angular_speed = 0.8   # rad/s default

        self.current_linear  = 0.0
        self.current_angular = 0.0

        # Publish at 10 Hz even when no key pressed (keeps last command alive)
        self.pub_timer = self.create_timer(0.1, self._publish_cmd)

        self._print_help()

    def _publish_cmd(self):
        twist = Twist()
        twist.linear.x  = self.current_linear
        twist.angular.z = self.current_angular
        self.cmd_pub.publish(twist)

    def apply_key(self, lin_dir: float, ang_dir: float):
        """Update velocity based on key direction."""
        if lin_dir != 0:
            self.current_linear  = lin_dir * self.linear_speed
            self.current_angular = 0.0
        elif ang_dir != 0:
            speed_mult = 1.5 if abs(ang_dir) == 2 else 1.0
            self.current_linear  = 0.0
            self.current_angular = (ang_dir / abs(ang_dir)) * self.angular_speed * speed_mult

    def stop(self):
        self.current_linear  = 0.0
        self.current_angular = 0.0

    def speed_up(self):
        self.linear_speed  = min(MAX_LINEAR,  self.linear_speed  + LINEAR_STEP)
        self.angular_speed = min(MAX_ANGULAR, self.angular_speed + ANGULAR_STEP)
        self._print_speed()

    def speed_down(self):
        self.linear_speed  = max(MIN_SPEED, self.linear_speed  - LINEAR_STEP)
        self.angular_speed = max(MIN_SPEED, self.angular_speed - ANGULAR_STEP)
        self._print_speed()

    def _print_speed(self):
        print(
            f"\r{YELLOW}Speed → Linear: {self.linear_speed:.2f} m/s  "
            f"Angular: {self.angular_speed:.2f} rad/s{RESET}          ",
            end='', flush=True
        )

    def _print_help(self):
        print(
            f"\n{CYAN}{BOLD}"
            "============================================================\n"
            "              ERC NAV BENCHMARK — TELEOP NODE               \n"
            f"============================================================{RESET}\n"
            f"  {BOLD}W / ↑{RESET}     Forward          {BOLD}S / ↓{RESET}  Backward\n"
            f"  {BOLD}A / ←{RESET}     Turn Left        {BOLD}D / →{RESET}  Turn Right\n"
            f"  {BOLD}Q{RESET}         Spin Left        {BOLD}E{RESET}      Spin Right\n"
            f"  {BOLD}+{RESET}         Speed Up         {BOLD}-{RESET}      Speed Down\n"
            f"  {BOLD}SPACE{RESET}     Emergency Stop   {BOLD}X{RESET}      Quit\n"
            f"{CYAN}============================================================{RESET}\n"
            f"  Linear: {self.linear_speed:.2f} m/s  |  Angular: {self.angular_speed:.2f} rad/s\n"
            f"{CYAN}============================================================{RESET}\n"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  KEYBOARD READER  (raw terminal, non-blocking)
# ─────────────────────────────────────────────────────────────────────────────
def get_key(settings):
    """Read a single key (or arrow-escape sequence) from stdin."""
    tty.setraw(sys.stdin.fileno())
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
    if rlist:
        key = sys.stdin.read(1)
        # Handle arrow keys (escape sequences: ESC [ A/B/C/D)
        if key == '\x1b':
            extra = sys.stdin.read(2)
            key   = key + extra
    else:
        key = ''
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main(args=None):
    rclpy.init(args=args)
    node = TeleopNode()

    # Spin ROS in a background thread so keyboard reading stays on main thread
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    settings = termios.tcgetattr(sys.stdin)
    try:
        while rclpy.ok():
            key = get_key(settings)

            if not key:
                # No input → decay to stop (comment out if you prefer latching)
                node.stop()
                continue

            if key in STOP_KEYS:
                node.stop()
                if key in {'x', 'X', '\x03'}:
                    print(f"\n{YELLOW}Teleop node stopping…{RESET}")
                    break

            elif key == '+':
                node.speed_up()

            elif key == '-':
                node.speed_down()

            elif key in KEY_BINDINGS:
                lin_dir, ang_dir = KEY_BINDINGS[key]
                node.apply_key(lin_dir, ang_dir)

                # Live feedback
                direction = (
                    "FORWARD" if lin_dir > 0 else
                    "BACKWARD" if lin_dir < 0 else
                    "LEFT" if ang_dir > 0 else "RIGHT"
                )
                print(
                    f"\r{GREEN}▶ {direction:<10}{RESET}  "
                    f"lin={node.current_linear:+.2f}  "
                    f"ang={node.current_angular:+.2f}      ",
                    end='', flush=True
                )

    except Exception as e:
        print(f"\n{RED}Teleop error: {e}{RESET}")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        node.stop()
        time.sleep(0.2)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
