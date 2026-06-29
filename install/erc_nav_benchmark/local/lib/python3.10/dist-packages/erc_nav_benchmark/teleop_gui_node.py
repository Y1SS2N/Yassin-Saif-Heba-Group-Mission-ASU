#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import tkinter as tk
import threading

class TeleopGUINode(Node):
    def __init__(self):
        super().__init__('teleop_gui_node')
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.linear_speed = 0.5
        self.angular_speed = 1.0

        self.current_linear = 0.0
        self.current_angular = 0.0

        self.pub_timer = self.create_timer(0.1, self.publish_cmd)

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

def run_gui(node):
    root = tk.Tk()
    root.title("ERC Rover GUI Teleop")
    root.geometry("300x200")

    # Keep window on top
    root.attributes('-topmost', True)

    frame = tk.Frame(root)
    frame.pack(expand=True)

    btn_fwd = tk.Button(frame, text="Forward (W)", width=10, height=2, bg="lightblue")
    btn_bwd = tk.Button(frame, text="Backward (S)", width=10, height=2, bg="lightblue")
    btn_left = tk.Button(frame, text="Left (A)", width=10, height=2, bg="lightblue")
    btn_right = tk.Button(frame, text="Right (D)", width=10, height=2, bg="lightblue")
    btn_stop = tk.Button(frame, text="STOP", width=10, height=2, bg="red", fg="white")

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

    # Keyboard bindings for WASD
    root.bind('<KeyPress-w>', lambda e: on_press(node, 1.0, 0.0))
    root.bind('<KeyRelease-w>', lambda e: on_release(node))
    
    root.bind('<KeyPress-s>', lambda e: on_press(node, -1.0, 0.0))
    root.bind('<KeyRelease-s>', lambda e: on_release(node))
    
    root.bind('<KeyPress-a>', lambda e: on_press(node, 0.0, 1.0))
    root.bind('<KeyRelease-a>', lambda e: on_release(node))
    
    root.bind('<KeyPress-d>', lambda e: on_press(node, 0.0, -1.0))
    root.bind('<KeyRelease-d>', lambda e: on_release(node))

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
