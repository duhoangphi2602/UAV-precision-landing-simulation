#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
from std_msgs.msg import String
import asyncio
from mavsdk import System
from mavsdk.offboard import (OffboardError, PositionNedYaw, VelocityBodyYawspeed)
import threading
import math
import time
from geometry_msgs.msg import Twist
from precision_landing_interfaces.msg import MissionStatus, ControlCommand

# Mission States
STATE_IDLE = "IDLE"
STATE_ARM = "ARM"
STATE_TAKEOFF = "TAKEOFF"
STATE_NAVIGATE = "NAVIGATE"
STATE_SCAN = "SCAN"
STATE_ALIGN = "ALIGN"
STATE_DESCEND = "DESCEND"
STATE_LAND = "LAND"
STATE_DONE = "DONE"

class MissionCommander(Node):
    def __init__(self):
        super().__init__('mission_commander')

        self.declare_parameter('system_address', 'udp://:14540')
        self.system_address = self.get_parameter('system_address').get_parameter_value().string_value

        # Vision Parameters
        self.declare_parameter('kp_x', 0.002)
        self.declare_parameter('kp_y', 0.002)
        self.declare_parameter('descent_speed', 0.2)
        self.declare_parameter('pixel_error_threshold', 20.0)
        self.declare_parameter('control_source', 'internal_python')

        # Waypoint Parameters
        self.declare_parameter('wp_north', 0.0)
        self.declare_parameter('wp_east', 5.8)
        self.declare_parameter('wp_down', -3.0)

        # Mapping helpers for quick iteration
        self.declare_parameter('swap_axes', False)
        self.declare_parameter('flip_x', False)
        self.declare_parameter('flip_y', False)

        self.kp_x = self.get_parameter('kp_x').get_parameter_value().double_value
        self.kp_y = self.get_parameter('kp_y').get_parameter_value().double_value
        self.descent_speed = self.get_parameter('descent_speed').get_parameter_value().double_value
        self.pixel_error_threshold = self.get_parameter('pixel_error_threshold').get_parameter_value().double_value

        self.swap_axes = self.get_parameter('swap_axes').get_parameter_value().bool_value
        self.flip_x = self.get_parameter('flip_x').get_parameter_value().bool_value
        self.flip_y = self.get_parameter('flip_y').get_parameter_value().bool_value
        self.control_source = self.get_parameter('control_source').get_parameter_value().string_value
        self.wp_north = self.get_parameter('wp_north').get_parameter_value().double_value
        self.wp_east = self.get_parameter('wp_east').get_parameter_value().double_value
        self.wp_down = self.get_parameter('wp_down').get_parameter_value().double_value

        # State
        self.state = STATE_IDLE
        self.marker_visible = False
        self.last_marker_time = 0
        self.current_error = Point()
        self.is_connected = False
        self.is_armed = False
        self.mission_start_time = time.time()

        self.new_observation_align = False
        self.new_observation_desc = False
        self.consecutive_high_error = 0
        self.consecutive_low_error = 0
        self.final_approach_active = False
        self.touchdown_detected = False
        self.touchdown_error_valid = False
        self.touchdown_horizontal_error_m = 0.0
        self.final_approach_start_error = 0.0

        # Subscribers
        self.error_sub = self.create_subscription(
            Point,
            '/aruco/center_error',
            self.error_callback,
            10)

        self.cmd_sub = self.create_subscription(
            Twist,
            '/precision_landing/cmd_vel',
            self.cmd_callback,
            10)

        self.status_pub = self.create_publisher(String, '/mission/status', 10)
        self.status_typed_pub = self.create_publisher(MissionStatus, '/precision_landing/mission_status', 10)
        self.cmd_vel_py_pub = self.create_publisher(Twist, '/precision_landing/cmd_vel_py', 10)
        self.cmd_vel_typed_py_pub = self.create_publisher(ControlCommand, '/precision_landing/control_command', 10)

        self.last_cpp_cmd_time = 0
        self.cpp_vel_x = 0.0
        self.cpp_vel_y = 0.0

        # MAVSDK
        self.drone = System()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_loop, daemon=True)
        self.thread.start()

        self.get_logger().info('Mission Commander Started')

    def error_callback(self, msg):
        self.current_error = msg
        self.last_marker_time = time.time()
        self.marker_visible = True
        self.new_observation_align = True
        self.new_observation_desc = True

    def cmd_callback(self, msg):
        self.cpp_vel_x = msg.linear.x
        self.cpp_vel_y = msg.linear.y
        self.last_cpp_cmd_time = time.time()

    def publish_typed_status(self):
        msg = MissionStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.mode = MissionStatus.MODE_FIXED

        state_map = {
            STATE_IDLE: MissionStatus.STATE_INIT,
            STATE_ARM: MissionStatus.STATE_INIT,
            STATE_TAKEOFF: MissionStatus.STATE_TAKEOFF,
            STATE_NAVIGATE: MissionStatus.STATE_NAVIGATE,
            STATE_SCAN: MissionStatus.STATE_SCAN,
            STATE_ALIGN: MissionStatus.STATE_ALIGN,
            STATE_DESCEND: MissionStatus.STATE_DESCEND,
            STATE_LAND: MissionStatus.STATE_LAND,
            STATE_DONE: MissionStatus.STATE_COMPLETE,
            "FAILED": MissionStatus.STATE_FAILED
        }
        msg.state = state_map.get(self.state, MissionStatus.STATE_INIT)
        msg.connected = self.is_connected
        msg.armed = self.is_armed
        msg.target_locked = self.marker_visible and (time.time() - self.last_marker_time < 1.0)
        msg.terminal = (self.state == STATE_DONE or self.state == "FAILED")
        msg.success = (self.state == STATE_DONE)
        msg.elapsed_sec = float(time.time() - self.mission_start_time)

        msg.touchdown_detected = self.touchdown_detected
        msg.touchdown_error_valid = self.touchdown_error_valid
        msg.touchdown_horizontal_error_m = float(self.touchdown_horizontal_error_m)

        details = [f"CONTROL: {self.control_source}"]
        if self.final_approach_active:
            details.append(f"FA_ALT: {getattr(self, 'final_approach_start_alt', 0.0):.2f}")
            details.append(f"FA_ERR: {self.final_approach_start_error:.2f}")
            if hasattr(self, 'final_approach_duration_sec'):
                details.append(f"FA_DUR: {self.final_approach_duration_sec:.2f}")

        msg.detail = " | ".join(details)
        self.status_typed_pub.publish(msg)

    async def _poll_telemetry(self):
        async def poll_alt():
            async for position in self.drone.telemetry.position():
                self.current_alt = position.relative_altitude_m
        async def poll_in_air():
            async for in_air in self.drone.telemetry.in_air():
                self.is_in_air = in_air
        asyncio.ensure_future(poll_alt())
        asyncio.ensure_future(poll_in_air())

    def start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run_mission())

    async def run_mission(self):
        await self.drone.connect(system_address=self.system_address)

        self.get_logger().info("Waiting for drone connection...")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                self.is_connected = True
                self.get_logger().info("Drone connected!")
                break

        # Start telemetry polling tasks
        await self._poll_telemetry()

        self.get_logger().info("Waiting for global position...")
        async for health in self.drone.telemetry.health():
            if health.is_global_position_ok and health.is_home_position_ok:
                self.get_logger().info("Global position OK")
                break

        # Wait until the drone is ready to be armed
        self.get_logger().info("Waiting for drone to be ready to arm...")
        async for health in self.drone.telemetry.health():
            if health.is_armable:
                self.get_logger().info("Drone is ready to arm")
                break

        # Start Mission Loop
        self.state = STATE_ARM

        while self.state != STATE_DONE and self.state != "FAILED":
            # Update armed state roughly
            if self.state == STATE_ARM:
                self.is_armed = True
            if self.state == STATE_DONE:
                self.is_armed = False

            ctrl_mode_str = "C++ PID" if self.control_source == 'external_cpp' else "PYTHON"
            self.status_pub.publish(String(data=f"State: {self.state} | CONTROL: {ctrl_mode_str}"))
            self.publish_typed_status()
            # self.get_logger().info(f"Current State: {self.state} | CONTROL: {ctrl_mode_str}")

            if self.state == STATE_ARM:
                await self.drone.action.arm()
                self.state = STATE_TAKEOFF

            elif self.state == STATE_TAKEOFF:
                await self.drone.action.takeoff()
                await asyncio.sleep(10) # Wait for takeoff
                try:
                    self.get_logger().info("Resolved takeoff waypoint: North=0.0, East=0.0, Down=-3.0")
                    for _ in range(3):
                        await self.drone.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, -3.0, 0.0))
                        await asyncio.sleep(0.1)
                    await self.drone.offboard.start()
                    await asyncio.sleep(5)
                except OffboardError as e:
                    self.get_logger().error(f"Offboard failed: {e}")

                self.state = STATE_NAVIGATE

            elif self.state == STATE_NAVIGATE:
                self.get_logger().info(f"Navigating to Inspection Point ({self.wp_north}, {self.wp_east}, {self.wp_down})")
                self.get_logger().info(f"Resolved navigate waypoint: North={self.wp_north}, East={self.wp_east}, Down={self.wp_down}")
                await self.drone.offboard.set_position_ned(PositionNedYaw(self.wp_north, self.wp_east, self.wp_down, 0.0))
                await asyncio.sleep(10)
                self.state = STATE_SCAN

            elif self.state == STATE_SCAN:
                self.get_logger().info("Scanning for marker...")
                # Yaw sweep
                await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 15.0))

                start_scan = time.time()
                while time.time() - start_scan < 24: # 360 degrees at 15 deg/s = 24s
                    if time.time() - self.last_marker_time < 0.5:
                        self.get_logger().info("Marker Found!")
                        self.state = STATE_ALIGN
                        break
                    await asyncio.sleep(0.1)

                if self.state != STATE_ALIGN:
                    self.get_logger().warn("Scan complete, marker not found. Retrying scan...")

            elif self.state == STATE_ALIGN:
                # Vision Control Loop
                if time.time() - self.last_marker_time > 1.0:
                    self.get_logger().warn("Marker lost during alignment!")
                    self.state = STATE_SCAN # Go back to scan
                    continue

                err_x = self.current_error.x
                err_y = self.current_error.y

                if self.control_source == 'external_cpp':
                    if time.time() - self.last_cpp_cmd_time > 1.0:
                        self.get_logger().warn("C++ command stale! Resetting alignment.")
                        self.state = STATE_SCAN
                        continue
                    vel_x = self.cpp_vel_x
                    vel_y = self.cpp_vel_y
                else:
                    # Compute mapping from image error to body velocities
                    if self.swap_axes:
                        vel_x = err_x * self.kp_x
                        vel_y = err_y * self.kp_y
                    else:
                        vel_y = err_x * self.kp_x
                        vel_x = -err_y * self.kp_y

                    # Apply flips if requested
                    if self.flip_x:
                        vel_x = -vel_x
                    if self.flip_y:
                        vel_y = -vel_y

                    # Clamp
                    vel_x = max(min(vel_x, 1.0), -1.0)
                    vel_y = max(min(vel_y, 1.0), -1.0)

                async for position in self.drone.telemetry.position():
                    current_alt_align = position.relative_altitude_m
                    break

                if current_alt_align < 1.5:
                    max_v = 0.15
                    vel_x = max(-max_v, min(max_v, vel_x))
                    vel_y = max(-max_v, min(max_v, vel_y))

                # Debug log to help tune mapping
                self.get_logger().info(f'ALIGN: err_x={err_x:.1f} err_y={err_y:.1f} -> vel_x={vel_x:.3f} vel_y={vel_y:.3f} swap={self.swap_axes} flip_x={self.flip_x} flip_y={self.flip_y}')

                tmsg = Twist()
                tmsg.linear.x = float(vel_x)
                tmsg.linear.y = float(vel_y)
                self.cmd_vel_py_pub.publish(tmsg)

                cmsg = ControlCommand()
                cmsg.header.stamp = self.get_clock().now().to_msg()
                cmsg.controller = "PYTHON PID"
                cmsg.valid = True
                cmsg.stale = False
                cmsg.saturated = (abs(vel_x) >= 1.0 or abs(vel_y) >= 1.0)
                cmsg.command = tmsg
                self.cmd_vel_typed_py_pub.publish(cmsg)

                # Check if centered
                err_mag = math.hypot(err_x, err_y)
                if self.new_observation_align:
                    self.new_observation_align = False
                    if err_mag <= 25.0:
                        self.consecutive_low_error += 1
                    else:
                        self.consecutive_low_error = 0

                if self.consecutive_low_error >= 2:
                    self.get_logger().info("Centered! Starting Descent.")
                    self.consecutive_high_error = 0
                    self.state = STATE_DESCEND

                await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(vel_x, vel_y, 0.0, 0.0))
                await asyncio.sleep(0.1)

            elif self.state == STATE_DESCEND:
                # Altitude and Touchdown check
                current_alt = getattr(self, 'current_alt', 10.0)
                is_in_air = getattr(self, 'is_in_air', True)

                if not is_in_air or current_alt <= 0.05:
                    if not self.touchdown_detected:
                        self.touchdown_detected = True
                        if hasattr(self, 'final_approach_start_time'):
                            self.final_approach_duration_sec = time.time() - self.final_approach_start_time

                        self.get_logger().info("Touchdown detected! Stopping Offboard and Disarming.")
                        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))

                        # Wait for land detector to trigger
                        await asyncio.sleep(2.0)

                        try:
                            await self.drone.offboard.stop()
                        except Exception:
                            pass

                        # Force PX4 land detector to trigger since we are <= 0.05m
                        try:
                            await self.drone.action.land()
                        except Exception as e:
                            self.get_logger().error(f"action.land() failed: {e}")

                        try:
                            async for pos in self.drone.telemetry.position_velocity_ned():
                                pad_north = 0.0
                                pad_east = 5.8
                                vehicle_north = pos.position.north_m
                                vehicle_east = pos.position.east_m
                                self.get_logger().info(f"Touchdown coords: N={vehicle_north:.3f}, E={vehicle_east:.3f}, pad_N={pad_north:.3f}, pad_E={pad_east:.3f}")
                                self.touchdown_horizontal_error_m = math.hypot(vehicle_north - pad_north, vehicle_east - pad_east)
                                self.touchdown_error_valid = True
                                break
                        except Exception as e:
                            self.get_logger().error(f"Failed to get position at touchdown: {e}")

                        try:
                            async def wait_for_disarm():
                                async for is_armed in self.drone.telemetry.armed():
                                    if not is_armed:
                                        return True
                                return False

                            await asyncio.wait_for(wait_for_disarm(), timeout=10.0)
                        except asyncio.TimeoutError:
                            self.get_logger().info("Auto-disarm timeout. Requesting manual disarm.")
                            try:
                                await self.drone.action.disarm()
                                await asyncio.wait_for(wait_for_disarm(), timeout=5.0)
                            except Exception as e:
                                self.get_logger().error(f"Disarm failed: {e}")
                                self.state = "FAILED"
                                continue

                        self.get_logger().info("Disarmed. Mission Complete.")
                        self.is_armed = False
                        self.state = STATE_DONE
                    continue

                err_x = self.current_error.x
                err_y = self.current_error.y
                err_mag = math.hypot(err_x, err_y)

                if current_alt < 0.3:
                    if not self.final_approach_active:
                        self.get_logger().info("Entering Guided Final Approach.")
                        self.final_approach_active = True
                        self.final_approach_start_alt = current_alt
                        self.final_approach_start_time = time.time()
                        self.final_approach_start_error = err_mag

                is_stale = (time.time() - self.last_marker_time > 0.5)

                if self.new_observation_desc:
                    self.new_observation_desc = False
                    if current_alt < 0.3:
                        if err_mag > 25.0:
                            self.consecutive_high_error += 1
                            self.consecutive_low_error = 0
                        elif err_mag <= 20.0:
                            self.consecutive_low_error += 1
                            self.consecutive_high_error = 0
                    else:
                        if err_mag > 30.0:
                            self.consecutive_high_error += 1
                        else:
                            self.consecutive_high_error = 0

                if current_alt >= 0.3:
                    if is_stale:
                        self.get_logger().warn("Marker lost during descent! Stopping.")
                        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, -0.5, 0.0))
                        await asyncio.sleep(2)
                        self.state = STATE_ALIGN
                        continue
                    if self.consecutive_high_error >= 2:
                        self.get_logger().warn(f"High error detected ({err_mag:.1f}) > 30.0 during descent. Re-aligning.")
                        self.consecutive_high_error = 0
                        self.consecutive_low_error = 0
                        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                        self.state = STATE_ALIGN
                        continue

                if self.control_source == 'external_cpp':
                    if time.time() - self.last_cpp_cmd_time > 1.0:
                        self.get_logger().warn("C++ command stale during descent! Stopping descent.")
                        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, -0.5, 0.0))
                        await asyncio.sleep(2)
                        self.state = STATE_ALIGN
                        continue
                    vel_x = self.cpp_vel_x
                    vel_y = self.cpp_vel_y
                else:
                    if self.swap_axes:
                        vel_x = err_x * self.kp_x
                        vel_y = err_y * self.kp_y
                    else:
                        vel_y = err_x * self.kp_x
                        vel_x = -err_y * self.kp_y

                    if self.flip_x:
                        vel_x = -vel_x
                    if self.flip_y:
                        vel_y = -vel_y

                if current_alt < 1.5:
                    max_v = 0.15
                    vel_x = max(-max_v, min(max_v, vel_x))
                    vel_y = max(-max_v, min(max_v, vel_y))

                vel_z = self.descent_speed

                # Final Approach logic (alt < 0.3)
                if current_alt < 0.3:
                    if hasattr(self, 'final_approach_start_time') and time.time() - self.final_approach_start_time > 15.0:
                        self.get_logger().warn("Final approach timeout! Disarming.")
                        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                        try:
                            await self.drone.offboard.stop()
                        except Exception: pass
                        try:
                            await self.drone.action.disarm()
                        except Exception: pass
                        self.state = "FAILED"
                        continue

                    # Keep XY control, but force 0 if stale to avoid flyaway
                    vel_z = 0.1
                    if is_stale:
                        vel_x = 0.0
                        vel_y = 0.0


                self.get_logger().info(f'DESCEND: alt={current_alt:.2f} err_mag={err_mag:.1f} vel_x={vel_x:.3f} vel_y={vel_y:.3f} vel_z={vel_z:.3f}')

                tmsg = Twist()
                tmsg.linear.x = float(vel_x)
                tmsg.linear.y = float(vel_y)
                tmsg.linear.z = float(vel_z)
                self.cmd_vel_py_pub.publish(tmsg)

                cmsg = ControlCommand()
                cmsg.header.stamp = self.get_clock().now().to_msg()
                cmsg.controller = "PYTHON PID"
                cmsg.valid = True
                cmsg.stale = False
                cmsg.saturated = (abs(vel_x) >= 1.0 or abs(vel_y) >= 1.0)
                cmsg.command = tmsg
                self.cmd_vel_typed_py_pub.publish(cmsg)

                await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(vel_x, vel_y, vel_z, 0.0))
                await asyncio.sleep(0.1)

            await asyncio.sleep(0.1)

        # Publish terminal status one last time
        self.publish_typed_status()

def main(args=None):
    rclpy.init(args=args)
    node = MissionCommander()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
