import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
import sys
import time
import subprocess

class ContractTest(Node):
    def __init__(self):
        super().__init__('contract_test')
        self.subscription = self.create_subscription(
            Point,
            '/aruco/center_error',
            self.listener_callback,
            10)
        self.msg_count = 0

    def set_marker_pose(self, x, y):
        cmd = f"gz service -s /world/inspection/set_pose --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 3000 --req 'name: \"aruco_marker_1\", position: {{x: {x}, y: {y}, z: 0.0}}'"
        subprocess.run(cmd, shell=True)
        time.sleep(2.0)
        
    def listener_callback(self, msg):
        print(f"Error -> x: {msg.x:.1f}, y: {msg.y:.1f}")
        sys.exit(0)

def main(args=None):
    x = float(sys.argv[1])
    y = float(sys.argv[2])
    
    rclpy.init(args=args)
    test = ContractTest()
    test.set_marker_pose(x, y)
    rclpy.spin_once(test, timeout_sec=5.0)
    test.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
