#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point, Twist
import math

class ShadowLogger(Node):
    def __init__(self):
        super().__init__('shadow_logger')
        self.err_x = 0.0
        self.err_y = 0.0
        self.py_vx = 0.0
        self.py_vy = 0.0
        self.cpp_vx = 0.0
        self.cpp_vy = 0.0
        
        self.create_subscription(Point, '/aruco/center_error', self.err_cb, 10)
        self.create_subscription(Twist, '/precision_landing/cmd_vel_py', self.py_cb, 10)
        self.create_subscription(Twist, '/precision_landing/cpp_shadow_cmd', self.cpp_cb, 10)
        
        self.timer = self.create_timer(0.1, self.log_cb)  # 10Hz log
        self.get_logger().info('Shadow Logger Started')

    def err_cb(self, msg):
        self.err_x = msg.x
        self.err_y = msg.y

    def py_cb(self, msg):
        self.py_vx = msg.linear.x
        self.py_vy = msg.linear.y

    def cpp_cb(self, msg):
        self.cpp_vx = msg.linear.x
        self.cpp_vy = msg.linear.y

    def log_cb(self):
        # We assume outside deadband if error > 5 pixels
        stale = (self.py_vx == 0 and self.cpp_vx == 0 and self.py_vy == 0 and self.cpp_vy == 0 and self.err_x == 0 and self.err_y == 0)
        
        py_sign_x = math.copysign(1, self.py_vx) if self.py_vx != 0 else 0
        cpp_sign_x = math.copysign(1, self.cpp_vx) if self.cpp_vx != 0 else 0
        py_sign_y = math.copysign(1, self.py_vy) if self.py_vy != 0 else 0
        cpp_sign_y = math.copysign(1, self.cpp_vy) if self.cpp_vy != 0 else 0
        
        diff_x = abs(self.py_vx - self.cpp_vx)
        diff_y = abs(self.py_vy - self.cpp_vy)
        
        self.get_logger().info(
            f"ERR({self.err_x:.1f}, {self.err_y:.1f}) | "
            f"PY({self.py_vx:.3f}, {self.py_vy:.3f}) | "
            f"CPP({self.cpp_vx:.3f}, {self.cpp_vy:.3f}) | "
            f"DIFF({diff_x:.3f}, {diff_y:.3f})"
        )

def main(args=None):
    rclpy.init(args=args)
    node = ShadowLogger()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
