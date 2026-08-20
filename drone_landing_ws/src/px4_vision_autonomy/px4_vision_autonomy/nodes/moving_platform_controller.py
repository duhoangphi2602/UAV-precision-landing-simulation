#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, Pose
from precision_landing_interfaces.msg import MissionStatus, MovingPlatformState

class MovingPlatformController(Node):
    def __init__(self):
        super().__init__('moving_platform_controller')

        # Subscriptions
        self.status_sub = self.create_subscription(
            MissionStatus,
            '/precision_landing/mission_status',
            self.status_callback,
            10
        )
        
        self.pose_sub = self.create_subscription(
            Pose,
            '/model/moving_aruco_platform/pose',
            self.pose_callback,
            10
        )

        # Publishers
        self.cmd_pub = self.create_publisher(
            Twist,
            '/model/moving_aruco_platform/cmd_vel',
            10
        )
        
        self.state_pub = self.create_publisher(
            MovingPlatformState,
            '/precision_landing/platform_state',
            10
        )

        # State variables
        self.movement_started = False
        self.stop_requested = False
        self.last_status = None
        self.current_enu_pose = Pose()
        self.last_pose_stamp = self.get_clock().now()
        
        # We will keep a simple velocity estimate based on pose diff since cmd_vel feedback isn't guaranteed
        self.last_enu_pose = None
        self.current_enu_vy = 0.0
        self.current_enu_vx = 0.0
        self.current_enu_vz = 0.0
        self.moving_streak = 0

        self.timer = self.create_timer(0.1, self.timer_callback) # 10 Hz
        self.get_logger().info('MovingPlatformController started.')

    def status_callback(self, msg):
        self.last_status = msg
        # Latch logic
        # Accepted moving mode starts at SCAN. Final mode starts during manual
        # flight so the operator acquires a physically moving target before
        # explicitly authorizing autonomous landing.
        start_moving = (
            msg.mode == MissionStatus.MODE_MOVING
            and msg.state == MissionStatus.STATE_SCAN
        ) or (
            msg.mode == MissionStatus.MODE_FINAL
            and msg.state in [
                MissionStatus.STATE_MANUAL_GESTURE_FLIGHT,
                MissionStatus.STATE_TARGET_AVAILABLE,
            ]
        )
        if start_moving:
            if not self.movement_started:
                self.get_logger().info('PLATFORM_LATCH_STARTED')
            self.movement_started = True

        # Stop conditions
        if msg.touchdown_detected or msg.terminal or msg.state == MissionStatus.STATE_FAILED or msg.state == MissionStatus.STATE_LAND:
            if not self.stop_requested:
                self.get_logger().info('PLATFORM_STOP reason=TOUCHDOWN')
            self.stop_requested = True

    def pose_callback(self, msg):
        now = self.get_clock().now()
        dt = (now - self.last_pose_stamp).nanoseconds / 1e9
        
        if self.last_enu_pose is not None and dt > 0.0:
            self.current_enu_vx = (msg.position.x - self.last_enu_pose.position.x) / dt
            self.current_enu_vy = (msg.position.y - self.last_enu_pose.position.y) / dt
            self.current_enu_vz = (msg.position.z - self.last_enu_pose.position.z) / dt
            
        # Keep the immediately preceding sample. The former assignment lagged
        # this reference by one callback, producing a two-sample displacement
        # divided by a one-sample interval (approximately 2x reported speed).
        self.last_enu_pose = msg
        self.current_enu_pose = msg
        self.last_pose_stamp = now

    def timer_callback(self):
        # 1. Publish command
        cmd = Twist()
        
        speed_command_enu_y = 0.0
        if self.movement_started and not self.stop_requested:
            speed_command_enu_y = 0.10
        
        cmd.linear.y = speed_command_enu_y
        self.cmd_pub.publish(cmd)
        
        state_str = str(self.last_status.state) if self.last_status else "None"
        self.get_logger().info(f'PLATFORM_COMMAND mission_state={state_str} latched={self.movement_started} cmd_enu_y={speed_command_enu_y:.2f} measured_enu_y={self.current_enu_pose.position.y:.2f} measured_speed={self.current_enu_vy:.2f}', throttle_duration_sec=2.0)

        # Evaluate measured motion
        measured_v_north = self.current_enu_vy
        if abs(measured_v_north) >= 0.05:
            self.moving_streak += 1
        else:
            self.moving_streak = 0
            
        actual_moving = (self.moving_streak >= 3)
        
        if speed_command_enu_y > 0 and not actual_moving:
            # We are commanding motion but platform is not moving physically
            self.get_logger().info('PLATFORM_COMMAND_WITHOUT_MOTION: Commanded 0.10 but measured speed < 0.05', throttle_duration_sec=2.0)

        # 2. Publish state (converted to NED)
        state_msg = MovingPlatformState()
        state_msg.header.stamp = self.get_clock().now().to_msg()
        state_msg.header.frame_id = 'moving_platform'
        state_msg.valid = True
        state_msg.moving = actual_moving
        state_msg.source = 'gazebo_pose'
        
        # ENU to NED Conversion
        # Point.x = North (ENU Y)
        # Point.y = East (ENU X)
        # Point.z = Down (-ENU Z)
        state_msg.position_ned_m.x = self.current_enu_pose.position.y
        state_msg.position_ned_m.y = self.current_enu_pose.position.x
        state_msg.position_ned_m.z = -self.current_enu_pose.position.z
        
        state_msg.velocity_ned_mps.x = self.current_enu_vy
        state_msg.velocity_ned_mps.y = self.current_enu_vx
        state_msg.velocity_ned_mps.z = -self.current_enu_vz
        
        # The speed we command in NED is along North, which is ENU Y
        state_msg.commanded_speed_mps = speed_command_enu_y
        
        self.state_pub.publish(state_msg)

    def destroy_node(self):
        # Ensure we stop before exit
        self.get_logger().info('Shutting down, sending zero twist.')
        cmd = Twist()
        self.cmd_pub.publish(cmd)
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = MovingPlatformController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
