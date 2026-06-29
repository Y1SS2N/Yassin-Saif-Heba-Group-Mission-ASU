#!/usr/bin/env python3
"""
============================================================
ERC NAV BENCHMARK - Judging Engine Node
============================================================
Monitors ALL aspects of a benchmark run in real time:
  A) Waypoint Tracker      - sequential checkpoint validation
  B) Crash Detector        - bumper contact → immediate shutdown
  C) Timer                 - traversal latency measurement
  D) Distance Tracker      - actual path length calculation
  E) Smoothness Monitor    - cmd_vel variance analysis
  F) Score Calculator      - normalized performance scoring

Run via: ros2 run erc_nav_benchmark judging_engine.py --ros-args
         -p level:=1 -p config_path:=/path/to/waypoints.yaml
============================================================
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from gazebo_msgs.msg import ContactsState
from visualization_msgs.msg import Marker, MarkerArray
from std_msgs.msg import String

import math
import time
import os
import subprocess
import datetime
import yaml
import sys
import threading


# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
PROXIMITY_RADIUS   = 1.0    # metres  – override by config
MAX_CMD_HISTORY    = 150    # samples kept for smoothness calculation
SMOOTHNESS_HIGH    = 0.06   # total variance threshold → High
SMOOTHNESS_MOD     = 0.22   # total variance threshold → Moderate (else Poor)
SCORE_CLAMP        = (0.0, 1.0)

# ANSI colours for terminal output
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ─────────────────────────────────────────────────────────────────────────────
#  JUDGING ENGINE NODE
# ─────────────────────────────────────────────────────────────────────────────
class JudgingEngine(Node):

    def __init__(self):
        super().__init__('judging_engine')

        # ── Parameters ──────────────────────────────────────────────────────
        self.declare_parameter('level', 1)
        self.declare_parameter('config_path', '')

        self.level       = self.get_parameter('level').get_parameter_value().integer_value
        config_path      = self.get_parameter('config_path').get_parameter_value().string_value

        # ── Load waypoint config ─────────────────────────────────────────────
        cfg = self._load_config(config_path)
        level_cfg        = cfg[f'level_{self.level}']
        self.waypoints   = [(wp['x'], wp['y']) for wp in level_cfg['waypoints']]
        self.optimal_time= level_cfg.get('optimal_time', 60)
        self.timeout_sec = level_cfg.get('timeout', 180)
        self.prox_radius = level_cfg.get('proximity_radius', PROXIMITY_RADIUS)
        self.spawn_pos   = level_cfg.get('spawn', {'x': 0.0, 'y': 0.0})

        # ── State ────────────────────────────────────────────────────────────
        self.run_active          = True
        self.crashed             = False
        self.termination_lock    = threading.Lock()

        # Waypoint tracking
        self.current_wp_idx      = 0
        self.checkpoints_cleared = 0
        self.sequence_violated   = False

        # Position / distance
        self.current_x   = self.spawn_pos['x']
        self.current_y   = self.spawn_pos['y']
        self.prev_x      = None
        self.prev_y      = None
        self.total_dist  = 0.0

        # Timing
        self.start_time  = time.time()

        # Smoothness
        self.cmd_vel_history = []   # list of {'lin': float, 'ang': float}

        # ── QoS for contact sensor ───────────────────────────────────────────
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # ── Subscriptions ────────────────────────────────────────────────────
        self.odom_sub     = self.create_subscription(
            Odometry, '/odom', self._odom_cb, 10)

        self.cmd_vel_sub  = self.create_subscription(
            Twist, '/cmd_vel', self._cmd_vel_cb, 10)

        self.bumper_sub   = self.create_subscription(
            ContactsState, '/bumper_states', self._bumper_cb, sensor_qos)

        # ── Publishers ───────────────────────────────────────────────────────
        self.marker_pub   = self.create_publisher(MarkerArray, '/waypoint_markers', 10)
        self.status_pub   = self.create_publisher(String, '/benchmark/status', 10)

        # ── Periodic tick (100 ms) ───────────────────────────────────────────
        self.tick_timer   = self.create_timer(0.1, self._tick)

        # ── Marker publish timer (1 s) ───────────────────────────────────────
        self.marker_timer = self.create_timer(1.0, self._publish_waypoint_markers)

        # ── Startup log ─────────────────────────────────────────────────────
        self._print_startup_banner()

    # ─────────────────────────────────────────────────────────────────────────
    #  CONFIG LOADER
    # ─────────────────────────────────────────────────────────────────────────
    def _load_config(self, path: str) -> dict:
        if not path or not os.path.isfile(path):
            # Try default relative location
            default = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'config', 'waypoints.yaml'
            )
            path = default

        if not os.path.isfile(path):
            self.get_logger().error(f"Config not found at: {path}")
            sys.exit(1)

        with open(path, 'r') as f:
            return yaml.safe_load(f)

    # ─────────────────────────────────────────────────────────────────────────
    #  CALLBACKS
    # ─────────────────────────────────────────────────────────────────────────

    def _odom_cb(self, msg: Odometry):
        """A) Waypoint tracker + D) Distance tracker."""
        if not self.run_active:
            return

        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y

        # Distance accumulation (filter out teleports > 1 m jump)
        if self.prev_x is not None:
            delta = math.hypot(x - self.prev_x, y - self.prev_y)
            if delta < 1.0:
                self.total_dist += delta

        self.prev_x   = x
        self.prev_y   = y
        self.current_x = x
        self.current_y = y

        # Check next sequential waypoint
        self._check_waypoint(x, y)

    def _cmd_vel_cb(self, msg: Twist):
        """E) Smoothness monitor – record velocity commands."""
        if not self.run_active:
            return

        self.cmd_vel_history.append({
            'lin': msg.linear.x,
            'ang': msg.angular.z
        })
        if len(self.cmd_vel_history) > MAX_CMD_HISTORY:
            self.cmd_vel_history.pop(0)

    def _bumper_cb(self, msg: ContactsState):
        """B) Crash Detector – ANY contact with non-ground objects."""
        if not self.run_active:
            return

        # Filter out ground-plane contacts
        for state in msg.states:
            col1 = state.collision1_name.lower()
            col2 = state.collision2_name.lower()
            if 'ground' in col1 or 'ground' in col2:
                continue
            if 'wheel' in col1 or 'wheel' in col2:
                continue
            # Real obstacle contact detected
            self.get_logger().error(
                f"{RED}COLLISION DETECTED:{RESET} "
                f"{state.collision1_name}  ↔  {state.collision2_name}"
            )
            self.crashed = True
            self._terminate("Catastrophic Collision")
            return

    def _tick(self):
        """C) Timer – check for timeout."""
        if not self.run_active:
            return

        elapsed = time.time() - self.start_time
        remaining = self.timeout_sec - elapsed

        # Publish live status every ~5 s
        if int(elapsed) % 5 == 0:
            status_msg = String()
            status_msg.data = (
                f"Level:{self.level} | "
                f"WP:{self.checkpoints_cleared}/4 | "
                f"Time:{elapsed:.1f}s | "
                f"Dist:{self.total_dist:.2f}m"
            )
            self.status_pub.publish(status_msg)

        if remaining <= 0:
            self._terminate("Timeout")

    # ─────────────────────────────────────────────────────────────────────────
    #  WAYPOINT LOGIC
    # ─────────────────────────────────────────────────────────────────────────

    def _check_waypoint(self, x: float, y: float):
        """Sequential checkpoint validation."""
        if self.current_wp_idx >= len(self.waypoints):
            return

        target_x, target_y = self.waypoints[self.current_wp_idx]
        dist = math.hypot(x - target_x, y - target_y)

        if dist <= self.prox_radius:
            self.current_wp_idx += 1
            self.checkpoints_cleared += 1

            print(
                f"\n{GREEN}{BOLD}✓ CHECKPOINT {self.checkpoints_cleared}/4 CLEARED{RESET}  "
                f"| WP({target_x:.1f}, {target_y:.1f})  "
                f"| Elapsed: {time.time()-self.start_time:.1f}s\n"
            )

            if self.checkpoints_cleared == 4:
                self._terminate("Target Reached")

    # ─────────────────────────────────────────────────────────────────────────
    #  SCORING  (F)
    # ─────────────────────────────────────────────────────────────────────────

    def _calculate_smoothness(self) -> str:
        """Compute Driving Smoothness Index from cmd_vel history."""
        n = len(self.cmd_vel_history)
        if n < 2:
            return "High"

        lin_var = sum(
            abs(self.cmd_vel_history[i]['lin'] - self.cmd_vel_history[i-1]['lin'])
            for i in range(1, n)
        ) / (n - 1)

        ang_var = sum(
            abs(self.cmd_vel_history[i]['ang'] - self.cmd_vel_history[i-1]['ang'])
            for i in range(1, n)
        ) / (n - 1)

        total_var = lin_var + ang_var * 0.5   # angular weighted less

        if total_var < SMOOTHNESS_HIGH:
            return "High"
        elif total_var < SMOOTHNESS_MOD:
            return "Moderate"
        else:
            return "Poor"

    def _calculate_score(self, status: str, elapsed: float) -> float:
        """Normalized Performance Score in [0.0, 1.0]."""
        if self.crashed or status == "Catastrophic Collision":
            return 0.0

        if self.checkpoints_cleared == 0:
            return 0.0

        # Checkpoint ratio (0.0 – 1.0)
        cp_ratio = self.checkpoints_cleared / 4.0

        # Time factor: reward fast runs (capped at 1.0 so early finish doesn't
        # penalise if rover is genuinely faster than optimal)
        time_factor = min(1.0, self.optimal_time / max(elapsed, 1.0))

        # Smoothness multiplier
        smoothness_map = {"High": 1.0, "Moderate": 0.8, "Poor": 0.5}
        s_mult = smoothness_map.get(self._calculate_smoothness(), 0.8)

        score = cp_ratio * time_factor * s_mult
        return round(max(SCORE_CLAMP[0], min(SCORE_CLAMP[1], score)), 4)

    # ─────────────────────────────────────────────────────────────────────────
    #  TERMINATION
    # ─────────────────────────────────────────────────────────────────────────

    def _terminate(self, status: str):
        """Single-entry termination handler (thread-safe)."""
        with self.termination_lock:
            if not self.run_active:
                return
            self.run_active = False

        elapsed    = time.time() - self.start_time
        smoothness = self._calculate_smoothness()
        score      = self._calculate_score(status, elapsed)
        seq_status = "FAILED_VIOLATION" if self.sequence_violated else "PASSED"

        report = self._build_report(status, elapsed, smoothness, score, seq_status)

        # Print to terminal
        print(report)

        # Save to log file
        self._save_report(report, status)

        # Shutdown simulation
        self._shutdown_simulation(crash=(status == "Catastrophic Collision"))

    # ─────────────────────────────────────────────────────────────────────────
    #  REPORT BUILDER
    # ─────────────────────────────────────────────────────────────────────────

    def _build_report(self, status, elapsed, smoothness, score, seq_status) -> str:
        # Pick status colour
        if status == "Target Reached":
            status_str = f"{GREEN}{status}{RESET}"
        elif status == "Catastrophic Collision":
            status_str = f"{RED}{status}{RESET}"
        else:
            status_str = f"{YELLOW}{status}{RESET}"

        score_str = f"{score:.4f}"
        if score >= 0.7:
            score_str = f"{GREEN}{score_str}{RESET}"
        elif score >= 0.3:
            score_str = f"{YELLOW}{score_str}{RESET}"
        else:
            score_str = f"{RED}{score_str}{RESET}"

        # Plain version (for log file)
        plain = (
            "\n"
            "============================================================\n"
            "           ERC NAV BENCHMARK RUN TERMINATION REPORT        \n"
            "============================================================\n"
            f"Test Scenario ID             : Level_{self.level}\n"
            f"Final Run Status             : {status}\n"
            f"Checkpoints Cleared          : {self.checkpoints_cleared} / 4\n"
            f"Sequence Compliance Status   : {seq_status}\n"
            f"Total Traversal Latency      : {elapsed:.2f} seconds\n"
            f"Actual Distance Traveled     : {self.total_dist:.2f} meters\n"
            f"Normalized Performance Score : {score:.4f}\n"
            f"Driving Smoothness Index     : {smoothness}\n"
            "============================================================\n"
        )
        self._plain_report = plain   # store for log file

        # Coloured version (for terminal)
        coloured = (
            f"\n{CYAN}{BOLD}"
            "============================================================\n"
            "           ERC NAV BENCHMARK RUN TERMINATION REPORT        \n"
            f"============================================================{RESET}\n"
            f"Test Scenario ID             : {BOLD}Level_{self.level}{RESET}\n"
            f"Final Run Status             : {status_str}\n"
            f"Checkpoints Cleared          : {self.checkpoints_cleared} / 4\n"
            f"Sequence Compliance Status   : {seq_status}\n"
            f"Total Traversal Latency      : {elapsed:.2f} seconds\n"
            f"Actual Distance Traveled     : {self.total_dist:.2f} meters\n"
            f"Normalized Performance Score : {score_str}\n"
            f"Driving Smoothness Index     : {smoothness}\n"
            f"{CYAN}{BOLD}============================================================{RESET}\n"
        )
        return coloured

    def _save_report(self, report: str, status: str):
        """Write plain-text report to logs/ directory."""
        timestamp  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        status_tag = status.replace(" ", "_")
        log_dir    = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', 'logs'
        )
        os.makedirs(log_dir, exist_ok=True)
        filename = os.path.join(log_dir, f"run_{timestamp}_level{self.level}_{status_tag}.txt")

        try:
            with open(filename, 'w') as f:
                f.write(self._plain_report)
            print(f"\n{CYAN}📄 Report saved → {filename}{RESET}")
        except Exception as e:
            self.get_logger().error(f"Could not save report: {e}")

    def _shutdown_simulation(self, crash: bool):
        """Kill Gazebo and ROS graph."""
        if crash:
            print(f"\n{RED}{BOLD}💥 CRASH TERMINATION — Shutting down immediately{RESET}\n")
            time.sleep(0.3)
            subprocess.run(["pkill", "-9", "-f", "gzserver"],   capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "gzclient"],   capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "ros2_run"],   capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "judging_engine"], capture_output=True)
            os._exit(0)
        else:
            print(f"\n{CYAN}Simulation ending in 3 seconds…{RESET}")
            time.sleep(3.0)
            subprocess.run(["pkill", "-f", "gzserver"], capture_output=True)
            subprocess.run(["pkill", "-f", "gzclient"], capture_output=True)
            rclpy.shutdown()

    # ─────────────────────────────────────────────────────────────────────────
    #  WAYPOINT MARKERS (RViz visualisation)
    # ─────────────────────────────────────────────────────────────────────────

    def _publish_waypoint_markers(self):
        if not self.run_active:
            return

        array = MarkerArray()
        now   = self.get_clock().now().to_msg()

        for i, (wx, wy) in enumerate(self.waypoints):
            # Cylinder marker (the waypoint zone)
            cyl = Marker()
            cyl.header.frame_id = "odom"
            cyl.header.stamp    = now
            cyl.ns              = "waypoints"
            cyl.id              = i * 2
            cyl.type            = Marker.CYLINDER
            cyl.action          = Marker.ADD
            cyl.pose.position.x = wx
            cyl.pose.position.y = wy
            cyl.pose.position.z = 0.05
            cyl.pose.orientation.w = 1.0
            cyl.scale.x = self.prox_radius * 2
            cyl.scale.y = self.prox_radius * 2
            cyl.scale.z = 0.1
            cyl.lifetime.sec    = 2

            if i < self.current_wp_idx:
                # Cleared – grey
                cyl.color.r = 0.5; cyl.color.g = 0.5; cyl.color.b = 0.5; cyl.color.a = 0.4
            elif i == self.current_wp_idx:
                # Current target – green pulse
                cyl.color.r = 0.0; cyl.color.g = 1.0; cyl.color.b = 0.2; cyl.color.a = 0.7
            else:
                # Future – yellow
                cyl.color.r = 1.0; cyl.color.g = 0.8; cyl.color.b = 0.0; cyl.color.a = 0.5

            # Text label marker
            txt = Marker()
            txt.header.frame_id = "odom"
            txt.header.stamp    = now
            txt.ns              = "waypoint_labels"
            txt.id              = i * 2 + 1
            txt.type            = Marker.TEXT_VIEW_FACING
            txt.action          = Marker.ADD
            txt.pose.position.x = wx
            txt.pose.position.y = wy
            txt.pose.position.z = 1.5
            txt.pose.orientation.w = 1.0
            txt.scale.z         = 0.5
            txt.color.r = 1.0; txt.color.g = 1.0; txt.color.b = 1.0; txt.color.a = 1.0
            txt.text            = f"WP{i+1}"
            txt.lifetime.sec    = 2

            array.markers.append(cyl)
            array.markers.append(txt)

        self.marker_pub.publish(array)

    # ─────────────────────────────────────────────────────────────────────────
    #  STARTUP BANNER
    # ─────────────────────────────────────────────────────────────────────────

    def _print_startup_banner(self):
        wp_list = "  →  ".join([f"WP{i+1}({x:.1f},{y:.1f})" for i, (x, y) in enumerate(self.waypoints)])
        print(
            f"\n{CYAN}{BOLD}"
            "============================================================\n"
            "              ERC NAV BENCHMARK — JUDGING ENGINE            \n"
            f"============================================================{RESET}\n"
            f"  Level        : {BOLD}{self.level}{RESET}\n"
            f"  Waypoints    : {wp_list}\n"
            f"  Timeout      : {self.timeout_sec}s\n"
            f"  Optimal time : {self.optimal_time}s\n"
            f"  Prox. radius : {self.prox_radius}m\n"
            f"{CYAN}  START → Drive the rover!  (teleop or autonomous){RESET}\n"
            f"{CYAN}============================================================{RESET}\n"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def main(args=None):
    rclpy.init(args=args)
    node = JudgingEngine()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Run interrupted by user.{RESET}")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
