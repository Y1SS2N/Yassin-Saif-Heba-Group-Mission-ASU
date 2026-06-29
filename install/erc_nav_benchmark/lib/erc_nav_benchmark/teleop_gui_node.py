#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import tkinter as tk
import threading
import math
import os
import yaml

class TeleopGUINode(Node):
    def __init__(self):
        super().__init__('teleop_gui_node')
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.linear_speed = 0.5
        self.angular_speed = 1.0

        self.current_linear = 0.0
        self.current_angular = 0.0

        # Load waypoints
        self.declare_parameter('level', 1)
        self.declare_parameter('config_path', '')
        self.level = self.get_parameter('level').get_parameter_value().integer_value
        config_path = self.get_parameter('config_path').get_parameter_value().string_value

        if not config_path or not os.path.isfile(config_path):
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'share', 'erc_nav_benchmark', 'config', 'waypoints.yaml'
            )

        self.waypoints = []
        self.prox_radius = 1.0
        try:
            with open(config_path, 'r') as f:
                cfg = yaml.safe_load(f)
                level_cfg = cfg[f'level_{self.level}']
                self.waypoints = [(wp['x'], wp['y']) for wp in level_cfg['waypoints']]
                self.prox_radius = level_cfg.get('proximity_radius', 1.0)
        except Exception as e:
            self.get_logger().error(f"Failed to load config in GUI: {e}")

        # Odometry tracking
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_yaw = 0.0
        self.current_wp_idx = 0

        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self.odom_cb, 10
        )

        self.pub_timer = self.create_timer(0.1, self.publish_cmd)

    def odom_cb(self, msg):
        self.current_x = msg.pose.pose.position.x
        self.current_y = msg.pose.pose.position.y
        
        # Quaternion to Euler yaw
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.current_yaw = math.atan2(siny_cosp, cosy_cosp)

        # Update current waypoint index based on proximity
        if self.current_wp_idx < len(self.waypoints):
            target_x, target_y = self.waypoints[self.current_wp_idx]
            dist = math.hypot(self.current_x - target_x, self.current_y - target_y)
            if dist <= self.prox_radius:
                self.current_wp_idx += 1

    def publish_cmd(self):
        twist = Twist()
        twist.linear.x = self.current_linear
        twist.angular.z = self.current_angular
        self.cmd_pub.publish(twist)

    def set_cmd(self, linear, angular):
        self.current_linear = linear * self.linear_speed
        self.current_angular = angular * self.angular_speed

    def stop(self):
        self.current_linear = 0.0
        self.current_angular = 0.0

def on_press(node, linear, angular):
    node.set_cmd(linear, angular)

def on_release(node):
    node.stop()

def update_gui_loop(node, labels):
    if not rclpy.ok():
        return

    # Update position label
    labels['pos'].config(text=f"Position: X={node.current_x:.2f}, Y={node.current_y:.2f}")

    # Update waypoint label
    if node.current_wp_idx < len(node.waypoints):
        target_x, target_y = node.waypoints[node.current_wp_idx]
        dist = math.hypot(node.current_x - target_x, node.current_y - target_y)
        
        # Calculate relative angle/bearing
        dx = target_x - node.current_x
        dy = target_y - node.current_y
        target_angle = math.atan2(dy, dx)
        relative_angle = target_angle - node.current_yaw
        relative_angle = (relative_angle + math.pi) % (2 * math.pi) - math.pi
        relative_deg = math.degrees(relative_angle)

        direction_text = ""
        if dist <= node.prox_radius:
            direction_text = "ARRIVED!"
        elif abs(relative_deg) < 10:
            direction_text = "Go STRAIGHT"
        elif relative_deg > 0:
            direction_text = f"Turn LEFT ({abs(relative_deg):.0f}°)"
        else:
            direction_text = f"Turn RIGHT ({abs(relative_deg):.0f}°)"

        labels['wp'].config(text=f"Target WP {node.current_wp_idx+1}: ({target_x:.1f}, {target_y:.1f})")
        labels['dist'].config(text=f"Distance: {dist:.2f} meters")
        labels['nav'].config(text=f"Guidance: {direction_text}", fg="green" if "STRAIGHT" in direction_text else "orange")
    else:
        labels['wp'].config(text="ALL WAYPOINTS CLEARED!", fg="green")
        labels['dist'].config(text="Distance: 0.00 m")
        labels['nav'].config(text="Guidance: Finished", fg="blue")

    labels['root'].after(100, lambda: update_gui_loop(node, labels))

def run_gui(node):
    root = tk.Tk()
    root.title(f"ERC Rover Controller (Level {node.level})")
    root.geometry("400x320")

    # Keep window on top
    root.attributes('-topmost', True)

    # Info frame
    info_frame = tk.LabelFrame(root, text="Navigation Info", padx=10, pady=5)
    info_frame.pack(fill="x", padx=10, pady=5)

    pos_label = tk.Label(info_frame, text="Position: X=0.00, Y=0.00", font=("Helvetica", 10, "bold"))
    pos_label.pack(anchor="w")

    wp_label = tk.Label(info_frame, text="Target WP: --", font=("Helvetica", 10))
    wp_label.pack(anchor="w")

    dist_label = tk.Label(info_frame, text="Distance: --", font=("Helvetica", 10))
    dist_label.pack(anchor="w")

    nav_label = tk.Label(info_frame, text="Guidance: --", font=("Helvetica", 10, "bold"), fg="blue")
    nav_label.pack(anchor="w")

    # Control frame
    ctrl_frame = tk.LabelFrame(root, text="Controls (Mouse or WASD Keys)", padx=10, pady=5)
    ctrl_frame.pack(expand=True, fill="both", padx=10, pady=5)

    btn_frame = tk.Frame(ctrl_frame)
    btn_frame.pack(expand=True)

    btn_fwd = tk.Button(btn_frame, text="Forward (W)", width=12, height=2, bg="lightblue")
    btn_bwd = tk.Button(btn_frame, text="Backward (S)", width=12, height=2, bg="lightblue")
    btn_left = tk.Button(btn_frame, text="Left (A)", width=12, height=2, bg="lightblue")
    btn_right = tk.Button(btn_frame, text="Right (D)", width=12, height=2, bg="lightblue")
    btn_stop = tk.Button(btn_frame, text="STOP (Space)", width=12, height=2, bg="red", fg="white")

    # Grid layout
    btn_fwd.grid(row=0, column=1, padx=5, pady=5)
    btn_left.grid(row=1, column=0, padx=5, pady=5)
    btn_stop.grid(row=1, column=1, padx=5, pady=5)
    btn_right.grid(row=1, column=2, padx=5, pady=5)
    btn_bwd.grid(row=2, column=1, padx=5, pady=5)

    # Bindings for mouse clicks
    btn_fwd.bind('<ButtonPress-1>', lambda e: on_press(node, 1.0, 0.0))
    btn_fwd.bind('<ButtonRelease-1>', lambda e: on_release(node))

    btn_bwd.bind('<ButtonPress-1>', lambda e: on_press(node, -1.0, 0.0))
    btn_bwd.bind('<ButtonRelease-1>', lambda e: on_release(node))

    btn_left.bind('<ButtonPress-1>', lambda e: on_press(node, 0.0, 1.0))
    btn_left.bind('<ButtonRelease-1>', lambda e: on_release(node))

    btn_right.bind('<ButtonPress-1>', lambda e: on_press(node, 0.0, -1.0))
    btn_right.bind('<ButtonRelease-1>', lambda e: on_release(node))
    
    btn_stop.bind('<ButtonPress-1>', lambda e: on_release(node))

    # Keyboard bindings for WASD and Space
    root.bind('<KeyPress-w>', lambda e: on_press(node, 1.0, 0.0))
    root.bind('<KeyRelease-w>', lambda e: on_release(node))
    
    root.bind('<KeyPress-s>', lambda e: on_press(node, -1.0, 0.0))
    root.bind('<KeyRelease-s>', lambda e: on_release(node))
    
    root.bind('<KeyPress-a>', lambda e: on_press(node, 0.0, 1.0))
    root.bind('<KeyRelease-a>', lambda e: on_release(node))
    
    root.bind('<KeyPress-d>', lambda e: on_press(node, 0.0, -1.0))
    root.bind('<KeyRelease-d>', lambda e: on_release(node))

    root.bind('<KeyPress-space>', lambda e: on_release(node))

    labels = {
        'root': root,
        'pos': pos_label,
        'wp': wp_label,
        'dist': dist_label,
        'nav': nav_label
    }

    # Start update loop
    root.after(100, lambda: update_gui_loop(node, labels))

    root.protocol("WM_DELETE_WINDOW", lambda: (node.destroy_node(), rclpy.shutdown(), root.destroy()))
    root.mainloop()

def main(args=None):
    rclpy.init(args=args)
    node = TeleopGUINode()

    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    run_gui(node)

if __name__ == '__main__':
    main()
