#!/usr/bin/env python3
"""
============================================================
ERC NAV BENCHMARK - Waypoint Publisher Node
============================================================
Publishes:
  - Visual markers for all 4 waypoints in RViz
  - Numbered text labels above each waypoint
  - Spawn position indicator
  - Continuously updates cleared/active/pending states
============================================================
"""

import rclpy
from rclpy.node import Node
from visualization_msgs.msg import Marker, MarkerArray
from geometry_msgs.msg import Point
from std_msgs.msg import Int32
import yaml
import os
import sys
import math


class WaypointPublisher(Node):

    def __init__(self):
        super().__init__('waypoint_publisher')

        # ── Parameters ──────────────────────────────────────────────────────
        self.declare_parameter('level', 1)
        self.declare_parameter('config_path', '')

        self.level   = self.get_parameter('level').get_parameter_value().integer_value
        config_path  = self.get_parameter('config_path').get_parameter_value().string_value

        # ── Load config ──────────────────────────────────────────────────────
        cfg           = self._load_config(config_path)
        level_cfg     = cfg[f'level_{self.level}']
        self.waypoints= [(wp['x'], wp['y']) for wp in level_cfg['waypoints']]
        self.spawn    = level_cfg.get('spawn', {'x': 0.0, 'y': 0.0})
        self.prox_rad = level_cfg.get('proximity_radius', 1.0)

        # Track which waypoints are cleared (updated by subscriber)
        self.cleared_up_to = 0

        # ── Pub/Sub ──────────────────────────────────────────────────────────
        self.marker_pub   = self.create_publisher(MarkerArray, '/waypoint_markers', 10)
        self.cleared_sub  = self.create_subscription(
            Int32, '/benchmark/checkpoints_cleared',
            self._cleared_cb, 10
        )

        # Publish markers at 2 Hz
        self.create_timer(0.5, self._publish_all_markers)

        self.get_logger().info(
            f"WaypointPublisher ready — Level {self.level}, "
            f"{len(self.waypoints)} waypoints"
        )

    def _load_config(self, path: str) -> dict:
        if not path or not os.path.isfile(path):
            default = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'config', 'waypoints.yaml'
            )
            path = default
        if not os.path.isfile(path):
            self.get_logger().error(f"Config not found: {path}")
            sys.exit(1)
        with open(path) as f:
            return yaml.safe_load(f)

    def _cleared_cb(self, msg: Int32):
        self.cleared_up_to = msg.data

    def _publish_all_markers(self):
        array = MarkerArray()
        now   = self.get_clock().now().to_msg()

        # ── Spawn marker ────────────────────────────────────────────────────
        spawn_m = Marker()
        spawn_m.header.frame_id = "odom"
        spawn_m.header.stamp    = now
        spawn_m.ns              = "spawn"
        spawn_m.id              = 0
        spawn_m.type            = Marker.ARROW
        spawn_m.action          = Marker.ADD
        spawn_m.pose.position.x = self.spawn['x']
        spawn_m.pose.position.y = self.spawn['y']
        spawn_m.pose.position.z = 0.5
        spawn_m.pose.orientation.w = 1.0
        spawn_m.scale.x = 0.8; spawn_m.scale.y = 0.15; spawn_m.scale.z = 0.15
        spawn_m.color.r = 0.0; spawn_m.color.g = 0.8; spawn_m.color.b = 1.0; spawn_m.color.a = 0.9
        spawn_m.lifetime.sec = 2
        array.markers.append(spawn_m)

        # ── Waypoint markers ─────────────────────────────────────────────────
        for i, (wx, wy) in enumerate(self.waypoints):
            base_id = (i + 1) * 10

            # State-based colour
            if i < self.cleared_up_to:
                r, g, b, a = 0.4, 0.4, 0.4, 0.3   # cleared – grey
            elif i == self.cleared_up_to:
                r, g, b, a = 0.0, 1.0, 0.3, 0.8   # active – bright green
            else:
                r, g, b, a = 1.0, 0.75, 0.0, 0.5  # pending – amber

            # Ground disc (proximity zone)
            disc = Marker()
            disc.header.frame_id = "odom"
            disc.header.stamp    = now
            disc.ns              = "wp_disc"
            disc.id              = base_id
            disc.type            = Marker.CYLINDER
            disc.action          = Marker.ADD
            disc.pose.position.x = wx
            disc.pose.position.y = wy
            disc.pose.position.z = 0.02
            disc.pose.orientation.w = 1.0
            disc.scale.x = self.prox_rad * 2
            disc.scale.y = self.prox_rad * 2
            disc.scale.z = 0.04
            disc.color.r = r; disc.color.g = g; disc.color.b = b; disc.color.a = a
            disc.lifetime.sec = 2
            array.markers.append(disc)

            # Vertical pole
            pole = Marker()
            pole.header.frame_id = "odom"
            pole.header.stamp    = now
            pole.ns              = "wp_pole"
            pole.id              = base_id + 1
            pole.type            = Marker.CYLINDER
            pole.action          = Marker.ADD
            pole.pose.position.x = wx
            pole.pose.position.y = wy
            pole.pose.position.z = 1.0
            pole.pose.orientation.w = 1.0
            pole.scale.x = 0.05; pole.scale.y = 0.05; pole.scale.z = 2.0
            pole.color.r = r; pole.color.g = g; pole.color.b = b; pole.color.a = 0.9
            pole.lifetime.sec = 2
            array.markers.append(pole)

            # Number text label
            label = Marker()
            label.header.frame_id = "odom"
            label.header.stamp    = now
            label.ns              = "wp_label"
            label.id              = base_id + 2
            label.type            = Marker.TEXT_VIEW_FACING
            label.action          = Marker.ADD
            label.pose.position.x = wx
            label.pose.position.y = wy
            label.pose.position.z = 2.3
            label.pose.orientation.w = 1.0
            label.scale.z = 0.6
            label.color.r = 1.0; label.color.g = 1.0; label.color.b = 1.0; label.color.a = 1.0
            label.text    = f"WP {i+1}"
            if i < self.cleared_up_to:
                label.text += " ✓"
            elif i == self.cleared_up_to:
                label.text += " ◀"
            label.lifetime.sec = 2
            array.markers.append(label)

            # Path line to next waypoint
            if i < len(self.waypoints) - 1:
                nx, ny = self.waypoints[i + 1]
                line = Marker()
                line.header.frame_id = "odom"
                line.header.stamp    = now
                line.ns              = "wp_path"
                line.id              = base_id + 3
                line.type            = Marker.LINE_STRIP
                line.action          = Marker.ADD
                p1 = Point(); p1.x = wx; p1.y = wy; p1.z = 0.1
                p2 = Point(); p2.x = nx; p2.y = ny; p2.z = 0.1
                line.points          = [p1, p2]
                line.scale.x         = 0.05
                if i < self.cleared_up_to:
                    line.color.r = 0.4; line.color.g = 0.4; line.color.b = 0.4; line.color.a = 0.3
                else:
                    line.color.r = 1.0; line.color.g = 0.8; line.color.b = 0.0; line.color.a = 0.4
                line.lifetime.sec = 2
                array.markers.append(line)

        self.marker_pub.publish(array)


def main(args=None):
    rclpy.init(args=args)
    node = WaypointPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
