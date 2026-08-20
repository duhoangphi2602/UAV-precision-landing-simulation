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
import json
from geometry_msgs.msg import Twist
from precision_landing_interfaces.msg import MissionStatus, ControlCommand, MovingPlatformState, TargetObservation
from ros_gz_interfaces.msg import Contacts

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
        self.declare_parameter('mission_mode', 'fixed')

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
        self.mission_mode = self.get_parameter('mission_mode').get_parameter_value().string_value

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

        self.platform_state = None
        self.re_align_count = 0

        # Subscribers
        self.error_sub = self.create_subscription(
            TargetObservation,
            '/precision_landing/target_observation',
            self.obs_callback,
            10)

        self.cmd_sub = self.create_subscription(
            Twist,
            '/precision_landing/cmd_vel',
            self.cmd_callback,
            10)

        self.platform_sub = self.create_subscription(
            MovingPlatformState,
            '/precision_landing/platform_state',
            self.platform_callback,
            10)

        self.gazebo_contact_active = False
        self.contact_sub = self.create_subscription(
            Contacts,
            '/platform_contact',
            self.contact_callback,
            10)

        self.mission_metrics = {
            "result": "IN_PROGRESS",
            "touchdown_confirmed": False,
            "touchdown_detection_source": None,
            "contact_debounce_sec": 0.0,
            "final_commit_duration_sec": 0.0,
            "final_commit_timeout": False,
            "platform_speed_at_contact_mps": 0.0,
            "platform_stop_latency_sec": 0.0,
            "armed_after_contact": False,
            "disarmed": False,
            "mission_complete": False,
            "touchdown_vehicle_north_m": 0.0,
            "touchdown_vehicle_east_m": 0.0,
            "touchdown_platform_north_m": 0.0,
            "touchdown_platform_east_m": 0.0,
            "touchdown_horizontal_error_m": 0.0
        }

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

    def obs_callback(self, msg):
        self.current_obs = msg
        self.current_error = Point(x=float(msg.error_x), y=float(msg.error_y), z=float(msg.error_magnitude))
        self.last_marker_time = time.time()
        self.marker_visible = True
        self.new_observation_align = True
        self.new_observation_desc = True

    def platform_callback(self, msg):
        self.platform_state = msg

    def contact_callback(self, msg):
        contact_found = False
        for contact in msg.contacts:
            name1 = contact.collision1.name.lower()
            name2 = contact.collision2.name.lower()
            if 'moving_aruco_platform' in name1 or 'moving_aruco_platform' in name2:
                if 'x500' in name1 or 'x500' in name2:
                    contact_found = True
                    break
        self.gazebo_contact_active = contact_found

    def cmd_callback(self, msg):
        self.cpp_vel_x = msg.linear.x
        self.cpp_vel_y = msg.linear.y
        self.last_cpp_cmd_time = time.time()

    def publish_typed_status(self):
        msg = MissionStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.mode = MissionStatus.MODE_MOVING if self.mission_mode == 'moving' else MissionStatus.MODE_FIXED

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
        msg.re_align_count = int(self.re_align_count)

        details = [f"CONTROL: {self.control_source}"]

        if hasattr(self, 'current_obs') and self.current_obs.valid:
            details.append(f"MARKER SIZE: {self.current_obs.marker_side_px:.1f}px")
            details.append(f"NORM ERROR: {self.current_obs.normalized_error:.2f}")
        else:
            details.append("MARKER SIZE: N/A")
            details.append("NORM ERROR: N/A")

        low_alt_yes_no = "YES" if (self.mission_mode == 'moving' and getattr(self, 'current_alt', 10.0) <= 0.80) else "NO"
        details.append(f"LOW ALT: {low_alt_yes_no}")

        fc_active = "ACTIVE" if getattr(self, 'final_commit_active', False) else "INACTIVE"
        details.append(f"FINAL COMMIT: {fc_active}")

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
        async def poll_landed_state():
            async for state in self.drone.telemetry.landed_state():
                self.landed_state = state
        asyncio.ensure_future(poll_alt())
        asyncio.ensure_future(poll_in_air())
        asyncio.ensure_future(poll_landed_state())

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
                    for _ in range(5):
                        await self.drone.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, -3.0, 0.0))
                        await asyncio.sleep(0.1)
                    await self.drone.offboard.start()
                    await asyncio.sleep(5)
                except OffboardError as e:
                    self.get_logger().error(f"Offboard failed: {e}. Retrying...")
                    try:
                        for _ in range(5):
                            await self.drone.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, -3.0, 0.0))
                            await asyncio.sleep(0.1)
                        await self.drone.offboard.start()
                    except Exception as e2:
                        self.get_logger().error(f"Offboard retry failed: {e2}")

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
                        if self.mission_mode == 'moving':
                            self.get_logger().info("Verifying platform motion...")
                            gate_pass = False
                            gate_start = time.time()
                            start_north = None
                            if self.platform_state:
                                start_north = self.platform_state.position_ned_m.x

                            while time.time() - gate_start < 5.0:
                                if self.platform_state and self.platform_state.valid and self.platform_state.moving:
                                    disp = 0.0
                                    if start_north is not None:
                                        disp = abs(self.platform_state.position_ned_m.x - start_north)
                                    if disp >= 0.20:
                                        gate_pass = True
                                        break
                                await asyncio.sleep(0.1)

                            if not gate_pass:
                                self.get_logger().error("PLATFORM_MOTION_NOT_VERIFIED")
                                self.state = "FAILED"
                                break

                        self.state = STATE_ALIGN
                        break
                    await asyncio.sleep(0.1)

                if self.state not in [STATE_ALIGN, "FAILED"]:
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
                landed_state = getattr(self, 'landed_state', None)
                ls_str = str(landed_state) if landed_state else "UNKNOWN"

                is_stale = (time.time() - self.last_marker_time > 0.5)

                if current_alt < 0.60:
                    if not hasattr(self, 'last_td_check_time') or time.time() - self.last_td_check_time > 0.5:
                        self.last_td_check_time = time.time()
                        self.get_logger().info(f"TOUCHDOWN_CHECK alt={current_alt:.2f} in_air={is_in_air} landed_state={ls_str} state={self.state}")

                # 1. Touchdown priority
                is_touchdown = False
                detected_source = None

                if not getattr(self, 'touchdown_latched', False):
                    # The fixed world has no platform contact sensor, and PX4 can
                    # continue reporting IN_AIR while Offboard commands a gentle
                    # descent against the pad. Restore the fixed-demo touchdown
                    # boundary that existed before the moving-platform slice.
                    if self.mission_mode != 'moving' and current_alt <= 0.05:
                        self.fixed_touchdown_debounce_count = getattr(
                            self, 'fixed_touchdown_debounce_count', 0) + 1
                        if self.fixed_touchdown_debounce_count >= 2:
                            is_touchdown = True
                            detected_source = "fixed_altitude"
                    else:
                        self.fixed_touchdown_debounce_count = 0

                    # Debounce logic for gazebo contact
                    if not is_touchdown and self.gazebo_contact_active:
                        if not hasattr(self, 'gz_contact_start'):
                            self.gz_contact_start = time.time()
                        else:
                            if time.time() - self.gz_contact_start >= 0.15: # 0.15s debounce
                                is_touchdown = True
                                detected_source = "gazebo_contact"
                    else:
                        if hasattr(self, 'gz_contact_start'):
                            del self.gz_contact_start

                    # MAVSDK check
                    if not is_touchdown and (not is_in_air or "ON_GROUND" in ls_str or "LANDED" in ls_str):
                        if not hasattr(self, 'touchdown_debounce_count'):
                            self.touchdown_debounce_count = 1
                        else:
                            self.touchdown_debounce_count += 1

                        if self.touchdown_debounce_count >= 2:
                            is_touchdown = True
                            detected_source = "mavsdk"
                    else:
                        self.touchdown_debounce_count = 0
                else:
                    is_touchdown = True

                # 2. Existing touchdown latch
                if is_touchdown and not getattr(self, 'touchdown_latched', False):
                    self.touchdown_latched = True
                    self.mission_metrics["touchdown_confirmed"] = True
                    self.mission_metrics["touchdown_detection_source"] = detected_source
                    if detected_source == "gazebo_contact":
                        self.mission_metrics["contact_debounce_sec"] = time.time() - self.gz_contact_start
                    self.get_logger().info(f"TOUCHDOWN_LATCHED via {detected_source}")
                    self.touchdown_detected = True

                if getattr(self, 'touchdown_latched', False):
                    vel_x, vel_y, vel_z = 0.0, 0.0, 0.0
                    if not hasattr(self, 'terminal_flow_started'):
                        self.terminal_flow_started = True
                        self.mission_metrics["result"] = "PASS"
                        if hasattr(self, 'final_approach_start_time'):
                            self.final_approach_duration_sec = time.time() - self.final_approach_start_time
                            self.mission_metrics["final_commit_duration_sec"] = self.final_approach_duration_sec
                        if self.platform_state and self.platform_state.valid:
                            self.mission_metrics["platform_speed_at_contact_mps"] = math.hypot(
                                self.platform_state.velocity_ned_mps.x,
                                self.platform_state.velocity_ned_mps.y)

                        self.state = STATE_LAND
                        self.publish_typed_status()
                        continue

                    await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                    await asyncio.sleep(0.1)
                    continue

                # Parse Observation
                if hasattr(self, 'current_obs') and self.current_obs.valid:
                    err_x = self.current_obs.error_x
                    err_y = self.current_obs.error_y
                    err_mag = self.current_obs.error_magnitude
                    marker_side_px = self.current_obs.marker_side_px
                    norm_err = self.current_obs.normalized_error
                else:
                    err_x, err_y, err_mag = 0.0, 0.0, 0.0
                    marker_side_px, norm_err = 0.0, -1.0

                is_low_alt = (self.mission_mode == 'moving' and current_alt <= 0.80)
                if is_low_alt and not hasattr(self, 'low_alt_entered'):
                    self.low_alt_entered = True
                    self.get_logger().info(f"Entered LOW_ALTITUDE_ZONE at {current_alt:.2f}m")

                # 3. Existing final commit logic for MOVING
                if self.mission_mode == 'moving' and getattr(self, 'final_commit_active', False):
                    if not hasattr(self, 'final_commit_start_time'):
                        self.final_commit_start_time = time.time()
                        self.get_logger().info(f"MOVING_FINAL_COMMIT active at alt={current_alt:.2f}")

                    if time.time() - self.final_commit_start_time > 1.2:
                        if not getattr(self, 'timeout_flow_started', False):
                            self.timeout_flow_started = True
                            self.get_logger().warn("FINAL_COMMIT_TIMEOUT. Stopping platform, zeroing XY, landing.")
                            self.mission_metrics["result"] = "FINAL_COMMIT_TIMEOUT"
                            self.mission_metrics["final_commit_timeout"] = True

                            # stop platform
                            tmsg = Twist()
                            self.cmd_vel_py_pub.publish(tmsg)
                            cmsg = ControlCommand()
                            cmsg.header.stamp = self.get_clock().now().to_msg()
                            cmsg.controller = "PYTHON PID"
                            cmsg.valid = True
                            cmsg.stale = False
                            cmsg.saturated = False
                            cmsg.command = tmsg
                            self.cmd_vel_typed_py_pub.publish(cmsg)

                            async def timeout_land():
                                try:
                                    await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                                    await asyncio.sleep(0.5)
                                    await self.drone.offboard.stop()
                                    await asyncio.sleep(0.5)
                                    await self.drone.action.land()
                                except Exception as e:
                                    self.get_logger().error(f"Fallback land failed: {e}")
                                self.state = STATE_LAND
                            asyncio.ensure_future(timeout_land())
                        continue

                    await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.6, 0.0))
                    await asyncio.sleep(0.1)
                    continue

                # Calculate XY correction
                if self.control_source == 'external_cpp':
                    if time.time() - self.last_cpp_cmd_time > 1.0:
                        self.get_logger().warn("C++ command stale during descent!")
                        vel_x, vel_y = 0.0, 0.0
                    else:
                        vel_x = self.cpp_vel_x
                        vel_y = self.cpp_vel_y
                else:
                    if self.swap_axes:
                        vel_x = err_x * self.kp_x
                        vel_y = err_y * self.kp_y
                    else:
                        vel_y = err_x * self.kp_x
                        vel_x = -err_y * self.kp_y
                    if self.flip_x: vel_x = -vel_x
                    if self.flip_y: vel_y = -vel_y

                if current_alt < 1.5:
                    max_v = 0.30
                    vel_x = max(-max_v, min(max_v, vel_x))
                    vel_y = max(-max_v, min(max_v, vel_y))

                vel_z = self.descent_speed

                if not is_low_alt:
                    # HIGH-ALTITUDE SAFETY (or FIXED mode logic)
                    fixed_final_approach = self.mission_mode != 'moving' and current_alt < 0.3

                    if self.new_observation_desc:
                        self.new_observation_desc = False
                        if fixed_final_approach:
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

                    observation_invalid = (
                        is_stale or
                        not hasattr(self, 'current_obs') or
                        not self.current_obs.valid
                    )

                    if observation_invalid and not fixed_final_approach:
                        self.get_logger().warn("Marker lost/stale during high-altitude descent! Re-aligning.")
                        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                        await asyncio.sleep(2)
                        self.state = STATE_ALIGN
                        continue

                    if self.consecutive_high_error >= 2 and not fixed_final_approach:
                        self.get_logger().warn(f"High error detected ({err_mag:.1f}px > threshold). Re-aligning.")
                        self.consecutive_high_error = 0
                        self.consecutive_low_error = 0
                        self.re_align_count += 1
                        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                        self.state = STATE_ALIGN
                        continue

                    # Final Commit Logic for FIXED mode
                    if fixed_final_approach:
                        if not getattr(self, 'final_approach_active', False):
                            self.get_logger().info("Entering Guided Final Approach.")
                            self.final_approach_active = True
                            self.final_approach_start_alt = current_alt
                            self.final_approach_start_time = time.time()
                            self.final_approach_start_error = err_mag

                        if hasattr(self, 'final_approach_start_time') and time.time() - self.final_approach_start_time > 15.0:
                            self.get_logger().warn("Final approach timeout! Disarming.")
                            await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                            try: await self.drone.offboard.stop()
                            except: pass
                            try: await self.drone.action.disarm()
                            except: pass
                            self.state = "FAILED"
                            continue

                        vel_z = 0.1
                        if observation_invalid:
                            vel_x, vel_y = 0.0, 0.0
                else:
                    # SCALE-AWARE LOW-ALTITUDE POLICY (MOVING ONLY)
                    self.new_observation_desc = False

                    if is_stale or not hasattr(self, 'current_obs') or not self.current_obs.valid:
                        vel_x, vel_y, vel_z = 0.0, 0.0, 0.0
                        if not hasattr(self, 'low_alt_lost_time'):
                            self.low_alt_lost_time = time.time()

                        if time.time() - self.low_alt_lost_time > 0.5:
                            self.get_logger().warn("LOW_ALTITUDE_TARGET_LOST")
                            await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                            try: await self.drone.offboard.stop()
                            except: pass
                            self.state = "FAILED"
                            continue
                    else:
                        if hasattr(self, 'low_alt_lost_time'):
                            del self.low_alt_lost_time

                        # Policy check
                        if norm_err <= 0.50 and norm_err >= 0:
                            # A. Continue guided descent
                            self.divergence_count = 0
                        elif norm_err <= 0.75 and norm_err >= 0:
                            # B. Hold vertical and re-center
                            vel_z = 0.0
                            self.divergence_count = 0
                        else:
                            # C. Low-altitude unsafe divergence
                            vel_z = 0.0
                            if not hasattr(self, 'divergence_count'):
                                self.divergence_count = 1
                            else:
                                self.divergence_count += 1

                            if self.divergence_count >= 2:
                                # Keep bounded XY correction, don't climb/align
                                vel_x = max(-0.10, min(0.10, vel_x))
                                vel_y = max(-0.10, min(0.10, vel_y))

                        # 8. BOUNDED FINAL COMMIT TRIGGER
                        if current_alt <= 0.70 and norm_err <= 0.50 and norm_err >= 0:
                            if not hasattr(self, 'low_alt_good_obs'):
                                self.low_alt_good_obs = 1
                            else:
                                self.low_alt_good_obs += 1

                            if self.low_alt_good_obs >= 2:
                                self.final_commit_active = True
                                continue
                        else:
                            self.low_alt_good_obs = 0

                self.get_logger().info(f'DESCEND: alt={current_alt:.2f} err_mag={err_mag:.1f} norm={norm_err:.2f} vel_x={vel_x:.3f} vel_y={vel_y:.3f} vel_z={vel_z:.3f}')

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

            elif self.state == STATE_LAND:
                self.get_logger().info("LANDING SEQUENCE. Stopping Offboard if running, and waiting for disarm...")
                try:
                    await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                    if self.mission_mode != 'moving':
                        # Keep the historical fixed-demo zero setpoint briefly so
                        # the vehicle remains settled before leaving Offboard.
                        await asyncio.sleep(2.0)
                    await self.drone.offboard.stop()
                except: pass

                if self.mission_mode != 'moving':
                    try:
                        await self.drone.action.land()
                    except Exception as e:
                        self.get_logger().error(f"action.land() failed: {e}")

                if self.mission_mode == 'moving':
                    tmsg = Twist()
                    self.cmd_vel_py_pub.publish(tmsg)

                start_wait = time.time()
                disarmed = False
                while time.time() - start_wait < 10.0:
                    is_armed = False
                    async for armed in self.drone.telemetry.armed():
                        is_armed = armed
                        break
                    if not is_armed:
                        disarmed = True
                        break
                    await asyncio.sleep(0.5)

                if not disarmed:
                    self.get_logger().warn("Auto-disarm timeout. Requesting manual disarm.")
                    try:
                        await self.drone.action.disarm()
                    except Exception as e:
                        self.get_logger().error(f"Manual disarm failed: {e}")

                    start_wait = time.time()
                    while time.time() - start_wait < 5.0:
                        is_armed = True
                        async for armed in self.drone.telemetry.armed():
                            is_armed = armed
                            break
                        if not is_armed:
                            disarmed = True
                            break
                        await asyncio.sleep(0.5)

                if not disarmed:
                    self.mission_metrics["result"] = "DISARM_FAILED"
                    self.mission_metrics["disarmed"] = False
                    self.mission_metrics["mission_complete"] = False
                    self.get_logger().error("MISSION_FAILED: PX4 remained armed after landing and disarm timeouts.")
                    self.state = "FAILED"
                    break

                self.mission_metrics["disarmed"] = True
                self.get_logger().info("Disarmed. Mission Complete.")
                self.is_armed = False

                try:
                    async for pos in self.drone.telemetry.position_velocity_ned():
                        pad_north, pad_east = 0.0, 5.8
                        if self.mission_mode == 'moving' and self.platform_state is not None:
                            pad_north = self.platform_state.position_ned_m.x
                            pad_east = self.platform_state.position_ned_m.y

                        vehicle_north = pos.position.north_m
                        vehicle_east = pos.position.east_m
                        self.mission_metrics["touchdown_vehicle_north_m"] = vehicle_north
                        self.mission_metrics["touchdown_vehicle_east_m"] = vehicle_east
                        self.mission_metrics["touchdown_platform_north_m"] = pad_north
                        self.mission_metrics["touchdown_platform_east_m"] = pad_east

                        err = math.hypot(vehicle_north - pad_north, vehicle_east - pad_east)
                        self.mission_metrics["touchdown_horizontal_error_m"] = err

                        self.get_logger().info(f"Final coords: N={vehicle_north:.3f}, E={vehicle_east:.3f}, pad_N={pad_north:.3f}, pad_E={pad_east:.3f}, err={err:.3f}")
                        self.touchdown_horizontal_error_m = err
                        self.touchdown_error_valid = True
                        break
                except Exception as e:
                    self.get_logger().error(f"Failed to get position at end: {e}")

                self.mission_metrics["mission_complete"] = True
                if self.mission_metrics["result"] == "PASS" and self.mission_metrics["touchdown_horizontal_error_m"] > 0.3:
                    self.mission_metrics["result"] = "FAIL"

                self.state = STATE_DONE
                break

        # Publish terminal status one last time
        self.publish_typed_status()
        self.get_logger().info(f"Writing mission metrics JSON: {json.dumps(self.mission_metrics)}")

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
