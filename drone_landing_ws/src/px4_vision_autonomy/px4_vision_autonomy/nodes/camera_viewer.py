#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from precision_landing_interfaces.msg import TargetObservation, ControlCommand, MissionStatus, MovingPlatformState
import cv2
import numpy as np
import json
import os
import time
import datetime

def imgmsg_to_cv2(img_msg):
    if img_msg.encoding != "bgr8" and img_msg.encoding != "rgb8":
        pass
    dtype = np.uint8
    n_channels = 3
    img_buf = np.asarray(img_msg.data, dtype=dtype)
    image = np.reshape(img_buf, (img_msg.height, img_msg.width, n_channels))
    if img_msg.encoding == "rgb8":
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    return image

class CameraViewer(Node):
    CAMERA_DISPLAY_WIDTH = 640
    CAMERA_DISPLAY_HEIGHT = 480
    PANEL_WIDTH = 250

    def __init__(self):
        super().__init__('camera_viewer')
        self.subscription = self.create_subscription(
            Image, '/camera', self.image_callback, qos_profile_sensor_data)
        self.obs_sub = self.create_subscription(TargetObservation, '/precision_landing/target_observation', self.obs_callback, 10)
        self.cmd_sub = self.create_subscription(ControlCommand, '/precision_landing/control_command', self.cmd_callback, 10)
        self.status_sub = self.create_subscription(MissionStatus, '/precision_landing/mission_status', self.status_callback, 10)
        self.platform_sub = self.create_subscription(MovingPlatformState, '/precision_landing/platform_state', self.platform_callback, 10)

        self.declare_parameter('mission_mode', 'fixed')
        self.mission_mode = self.get_parameter('mission_mode').get_parameter_value().string_value

        self.obs = None
        self.cmd = None
        self.status = None
        self.platform_state = None
        self.platform_start_north_m = None
        self.platform_start_time = None
        self.platform_last_moving_north_m = None
        self.platform_last_moving_time = None
        self.platform_commanded_speed_mps = 0.0

        self.trajectory = []

        self.metrics_saved = False

        # State Duration tracking
        self.last_state = MissionStatus.STATE_INIT
        self.align_start = None
        self.descend_start = None

        # Marker loss semantics
        self.target_acquired_once = False
        self.previous_target_valid = False

        # Error metrics tracking
        self.last_valid_center_error = None
        self.descent_start_error = None

        # FPS measurement
        self.fresh_frame_count = 0
        self.first_frame_time = None

        self.metrics = {
            "result": "UNKNOWN",
            "controller": "UNKNOWN",
            "mode": self.mission_mode.upper(),
            "generated_at": "",
            "mission_duration_sec": 0.0,
            "alignment_duration_sec": None,
            "descent_duration_sec": None,
            "max_center_error": 0.0,
            "final_approach_start_error_px": None,
            "final_center_error_px": None,
            "center_error_unit": "pixel",
            "marker_loss_count": 0,
            "stale_observation_count": 0,
            "fresh_frame_count": 0,
            "average_fresh_frame_fps": 0.0,
            "ui_refresh_hz": 30.0,
            "re_align_count": 0,
            "platform_speed_command_mps": 0.0
        }

        self.terminal_time = None
        self.terminal_display_duration = 5.0

        # Dashboard state
        self.latest_cv_image = None
        self.display_timer = self.create_timer(1.0 / 30.0, self.display_loop)

        self.saved_screenshot = False

        # For fresh FPS display in UI
        self.ui_fps_window = []
        self.last_ui_frame_time = None
        self.new_frame_available = False

        self.ui_frame_count = 0
        self.first_ui_time = None

        cv2.namedWindow("Drone Camera View")
        cv2.setMouseCallback("Drone Camera View", self.mouse_callback)
        self.get_logger().info('Dashboard Node Started')

    def platform_callback(self, msg):
        self.platform_state = msg
        if self.mission_mode == 'moving':
            if abs(msg.commanded_speed_mps) > 0.0:
                self.platform_commanded_speed_mps = abs(msg.commanded_speed_mps)

            if msg.moving and self.platform_start_time is None:
                self.platform_start_time = time.perf_counter()
                self.platform_start_north_m = msg.position_ned_m.x

            if msg.moving:
                self.platform_last_moving_time = time.perf_counter()
                self.platform_last_moving_north_m = msg.position_ned_m.x

    def obs_callback(self, msg):
        self.obs = msg

        is_tracking_relevant = False
        is_terminal = False
        if self.status:
            state = self.status.state
            is_tracking_relevant = state in [MissionStatus.STATE_SCAN, MissionStatus.STATE_ALIGN, MissionStatus.STATE_DESCEND]
            is_terminal = self.status.terminal

        current_valid = msg.valid

        # Target acquired once
        if current_valid:
            self.target_acquired_once = True

        # Marker loss count
        if self.previous_target_valid and not current_valid:
            if self.target_acquired_once and is_tracking_relevant and not is_terminal:
                self.metrics["marker_loss_count"] += 1

        self.previous_target_valid = current_valid

        # Stale observation count
        if msg.stale and is_tracking_relevant and not is_terminal:
            self.metrics["stale_observation_count"] += 1

        # Update center error
        if current_valid and not msg.stale and np.isfinite(msg.error_magnitude):
            self.last_valid_center_error = float(msg.error_magnitude)

            # Max center error (prioritize ALIGN and DESCEND)
            if self.status and self.status.state in [MissionStatus.STATE_ALIGN, MissionStatus.STATE_DESCEND]:
                if float(msg.error_magnitude) > self.metrics["max_center_error"]:
                    self.metrics["max_center_error"] = float(msg.error_magnitude)

    def cmd_callback(self, msg):
        self.cmd = msg
        self.metrics["controller"] = msg.controller

    def status_callback(self, msg):
        current_state = msg.state
        now_perf = time.perf_counter()

        if current_state != self.last_state:
            # Leaving ALIGN
            if self.last_state == MissionStatus.STATE_ALIGN:
                if self.align_start is not None:
                    duration = now_perf - self.align_start
                    if self.metrics["alignment_duration_sec"] is None:
                        self.metrics["alignment_duration_sec"] = 0.0
                    self.metrics["alignment_duration_sec"] += duration
                self.align_start = None

            # Leaving DESCEND
            if self.last_state == MissionStatus.STATE_DESCEND:
                if self.descend_start is not None:
                    duration = now_perf - self.descend_start
                    if self.metrics["descent_duration_sec"] is None:
                        self.metrics["descent_duration_sec"] = 0.0
                    self.metrics["descent_duration_sec"] += duration
                self.descend_start = None

            # Entering ALIGN
            if current_state == MissionStatus.STATE_ALIGN:
                self.align_start = now_perf

            # Entering DESCEND
            if current_state == MissionStatus.STATE_DESCEND:
                self.descend_start = now_perf
                pass

            self.last_state = current_state

        self.status = msg

        if msg.terminal and not self.metrics_saved:
            if self.last_valid_center_error is not None:
                self.metrics["final_center_error_px"] = self.last_valid_center_error

            if "FA_ALT: " in msg.detail:
                try:
                    self.metrics["final_approach_start_altitude"] = float(msg.detail.split("FA_ALT: ")[1].split(" | ")[0])
                except: pass
            if "FA_ERR: " in msg.detail:
                try:
                    self.metrics["final_approach_start_error_px"] = float(msg.detail.split("FA_ERR: ")[1].split(" | ")[0])
                except: pass
            if "FA_DUR: " in msg.detail:
                try:
                    self.metrics["final_approach_duration_sec"] = float(msg.detail.split("FA_DUR: ")[1].split(" | ")[0])
                except: pass

            self.metrics["touchdown_detected"] = msg.touchdown_detected
            if msg.touchdown_error_valid:
                self.metrics["touchdown_horizontal_error_m"] = msg.touchdown_horizontal_error_m

            self.metrics["re_align_count"] = getattr(msg, "re_align_count", 0)
            if self.platform_state:
                self.metrics["platform_speed_command_mps"] = self.platform_commanded_speed_mps

            self.metrics["disarmed"] = not msg.armed
            self.metrics["mission_complete"] = True

            if msg.success:
                if msg.touchdown_detected and (not msg.armed):
                    self.metrics["result"] = "SUCCESS_PRECISION_UNVERIFIED"
                else:
                    self.metrics["result"] = "PRECISION_FAIL"
            else:
                self.metrics["result"] = "FAILED"

            if self.mission_mode == 'moving' and self.platform_state:
                motion_duration = 0.0
                if self.platform_start_time is not None and self.platform_last_moving_time is not None:
                    motion_duration = max(0.0, self.platform_last_moving_time - self.platform_start_time)
                self.metrics["platform_motion_duration_sec"] = motion_duration
                self.metrics["platform_start_north_m"] = self.platform_start_north_m
                touchdown_north_m = (
                    self.platform_last_moving_north_m
                    if self.platform_last_moving_north_m is not None
                    else self.platform_state.position_ned_m.x
                )
                self.metrics["platform_touchdown_north_m"] = touchdown_north_m

                disp = 0.0
                if self.platform_start_north_m is not None:
                    disp = abs(touchdown_north_m - self.platform_start_north_m)
                self.metrics["platform_displacement_m"] = disp

                self.metrics["platform_commanded_speed_mps"] = self.platform_commanded_speed_mps
                mean_speed = disp / motion_duration if motion_duration > 0.0 else 0.0
                self.metrics["platform_measured_speed_mean_mps"] = mean_speed

                exp_disp = self.platform_commanded_speed_mps * motion_duration
                self.metrics["platform_expected_displacement_m"] = exp_disp
                ratio = disp / exp_disp if exp_disp > 0 else 0.0
                self.metrics["platform_displacement_ratio"] = ratio

                platform_pass = (motion_duration >= 5.0 and disp >= 0.50 and 0.08 <= mean_speed <= 0.12 and 0.80 <= ratio <= 1.20)
                self.metrics["platform_motion_verified"] = platform_pass

                if not platform_pass:
                    self.metrics["result"] = "PLATFORM_MOTION_FAIL"

            self.metrics["mission_duration_sec"] = msg.elapsed_sec

            self.metrics["generated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

            self.metrics["fresh_frame_count"] = self.fresh_frame_count
            if self.first_frame_time is not None and self.fresh_frame_count > 0:
                active_duration = time.perf_counter() - self.first_frame_time
                if active_duration > 0:
                    self.metrics["fresh_camera_fps"] = self.fresh_frame_count / active_duration

            if self.first_ui_time is not None and self.ui_frame_count > 0:
                ui_duration = time.perf_counter() - self.first_ui_time
                if ui_duration > 0:
                    self.metrics["ui_refresh_hz"] = self.ui_frame_count / ui_duration

            # Save metrics
            metrics_path = '/home/devuser/artifacts/runtime/latest_metrics.json'
            os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
            with open(metrics_path, 'w') as f:
                json.dump(self.metrics, f, indent=4)
            self.get_logger().info(f"Saved metrics to {metrics_path}")
            self.metrics_saved = True
            self.terminal_time = time.perf_counter()

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            pass

    def image_callback(self, msg):
        try:
            now_perf = time.perf_counter()
            if not self.metrics_saved:
                if self.first_frame_time is None:
                    self.first_frame_time = now_perf
                self.fresh_frame_count += 1

                if self.last_ui_frame_time is not None:
                    dt = now_perf - self.last_ui_frame_time
                    if dt > 0:
                        self.ui_fps_window.append(1.0 / dt)
                        if len(self.ui_fps_window) > 30:
                            self.ui_fps_window.pop(0)
                self.last_ui_frame_time = now_perf

            self.latest_cv_image = imgmsg_to_cv2(msg)
            self.new_frame_available = True
        except Exception as e:
            self.get_logger().error(f'Could not convert image: {e}')

    def display_loop(self):
        if self.latest_cv_image is None or not self.new_frame_available:
            cv2.waitKey(1)
            return

        self.new_frame_available = False

        if self.first_ui_time is None:
            self.first_ui_time = time.perf_counter()
        self.ui_frame_count += 1

        try:
            cv_image = self.latest_cv_image.copy()

            # Compact 4:3 camera presentation; the Gazebo sensor remains 1280x960.
            cv_image = cv2.resize(
                cv_image, (self.CAMERA_DISPLAY_WIDTH, self.CAMERA_DISPLAY_HEIGHT))

            panel = np.zeros(
                (self.CAMERA_DISPLAY_HEIGHT, self.PANEL_WIDTH, 3), dtype=np.uint8)

            # Styling definitions
            PAD = 10
            ROW = 15
            HEADING_ROW = 17
            y_offset = 17
            H_FONT = cv2.FONT_HERSHEY_SIMPLEX
            H_SCALE = 0.48
            H_THICK = 1
            H_COLOR = (0, 255, 255) # Yellow

            F_FONT = cv2.FONT_HERSHEY_SIMPLEX
            F_SCALE = 0.40
            F_THICK = 1
            F_COLOR = (255, 255, 255) # White

            # Function to draw field
            def draw_heading(text, y):
                cv2.putText(panel, text, (PAD, y), H_FONT, H_SCALE, H_COLOR, H_THICK)
                return y + HEADING_ROW

            def draw_field(key, val, y, color=F_COLOR):
                cv2.putText(panel, f"{key}: {val}", (PAD, y), F_FONT, F_SCALE, color, F_THICK)
                return y + ROW

            y_offset = draw_heading("MODE", y_offset)

            # Draw Mode Buttons
            btn_w, btn_h = 95, 22
            modes = ["FIXED", "MOVING"]
            bx = PAD
            for idx, mode in enumerate(modes):
                is_active = (mode.lower() == self.mission_mode.lower())
                color = (0, 255, 0) if is_active else (100, 100, 100)
                txt_col = (0, 0, 0) if is_active else (255, 255, 255)
                cv2.rectangle(panel, (bx, y_offset), (bx + btn_w, y_offset + btn_h), color, -1)

                # Center text
                tsize, _ = cv2.getTextSize(mode, F_FONT, F_SCALE, F_THICK)
                tx = bx + (btn_w - tsize[0]) // 2
                ty = y_offset + (btn_h + tsize[1]) // 2
                cv2.putText(panel, mode, (tx, ty), F_FONT, F_SCALE, txt_col, F_THICK)
                bx += btn_w + 8
            y_offset += btn_h + 8

            y_offset = draw_heading("MISSION", y_offset)
            if self.status:
                y_offset = draw_field("STATE", self.status.state, y_offset)
                y_offset = draw_field("ELAPSED", f"{self.status.elapsed_sec:.1f}s", y_offset)
                if hasattr(self.status, 're_align_count'):
                    y_offset = draw_field("RE-ALIGN", str(self.status.re_align_count), y_offset)

            y_offset = draw_heading("CONTROL", y_offset)
            if self.cmd:
                y_offset = draw_field("ACTIVE", self.cmd.controller, y_offset)
                y_offset = draw_field("VX", f"{self.cmd.command.linear.x:.2f}", y_offset)
                y_offset = draw_field("VY", f"{self.cmd.command.linear.y:.2f}", y_offset)
                y_offset = draw_field("VZ", f"{self.cmd.command.linear.z:.2f}", y_offset)

            y_offset = draw_heading("TARGET", y_offset)
            if self.obs:
                color = (0, 255, 0) if self.obs.valid else (0, 0, 255)
                if self.obs.stale: color = (0, 255, 255)
                y_offset = draw_field("STATUS", "LOCKED" if self.obs.valid else "LOST", y_offset, color)
                y_offset = draw_field("STALE", "YES" if self.obs.stale else "NO", y_offset, color)
                y_offset = draw_field("MARKER ID", str(self.obs.target_id), y_offset)
                y_offset = draw_field("ERROR X", f"{self.obs.error_x:.1f}", y_offset)
                y_offset = draw_field("ERROR Y", f"{self.obs.error_y:.1f}", y_offset)
                y_offset = draw_field("ERROR MAG", f"{self.obs.error_magnitude:.1f}", y_offset)

            if self.mission_mode == 'moving':
                y_offset = draw_heading("PLATFORM", y_offset)
                if self.platform_state:
                    y_offset = draw_field("STATE", "MOVING" if self.platform_state.moving else "STOPPED", y_offset)
                    y_offset = draw_field("CMD", f"{self.platform_state.commanded_speed_mps:.2f} m/s", y_offset)
                    y_offset = draw_field("ACTUAL SIM", f"{abs(self.platform_state.velocity_ned_mps.x):.2f} m/s", y_offset)
                else:
                    y_offset = draw_field("STATE", "WAITING", y_offset)

            if self.obs:
                if self.obs.valid:
                    # Update trajectory relative to the compact camera image.
                    # Original coordinates from obs are based on the original image (likely 1280x960 or 640x480)
                    # Scale detector coordinates without changing aspect ratio.
                    # Assuming obs center is from original size, but wait, error is normalized or in pixels?
                    # In aruco_detector we passed center_x_px, center_y_px in original size.
                    orig_w = self.latest_cv_image.shape[1]
                    orig_h = self.latest_cv_image.shape[0]
                    scale_x = self.CAMERA_DISPLAY_WIDTH / orig_w
                    scale_y = self.CAMERA_DISPLAY_HEIGHT / orig_h
                    cx = int(self.obs.center_x_px * scale_x)
                    cy = int(self.obs.center_y_px * scale_y)
                    self.trajectory.append((cx, cy))
                    if len(self.trajectory) > 30:
                        self.trajectory.pop(0)

            # Display FPS
            fps_val = sum(self.ui_fps_window)/len(self.ui_fps_window) if self.ui_fps_window else 0.0

            ui_fps = 0.0
            if self.first_ui_time is not None and self.ui_frame_count > 0:
                ui_dur = time.perf_counter() - self.first_ui_time
                if ui_dur > 0:
                    ui_fps = self.ui_frame_count / ui_dur

            y_offset = draw_heading("PERFORMANCE", y_offset)
            y_offset = draw_field("CAM FPS", f"{fps_val:.1f}", y_offset)
            y_offset = draw_field("UI HZ", f"{ui_fps:.1f}", y_offset)

            # Draw CLEAR TARGET Button at bottom
            y_offset = self.CAMERA_DISPLAY_HEIGHT - 31
            btn_w, btn_h = 150, 22
            cv2.rectangle(panel, (PAD, y_offset), (PAD + btn_w, y_offset + btn_h), (0, 0, 255), -1)
            tsize, _ = cv2.getTextSize("CLEAR TARGET", F_FONT, F_SCALE, F_THICK)
            tx = PAD + (btn_w - tsize[0]) // 2
            ty = y_offset + (btn_h + tsize[1]) // 2
            cv2.putText(panel, "CLEAR TARGET", (tx, ty), F_FONT, F_SCALE, (255, 255, 255), F_THICK)

            # Deadband and Trajectory
            cv2.circle(
                cv_image,
                (self.CAMERA_DISPLAY_WIDTH // 2, self.CAMERA_DISPLAY_HEIGHT // 2),
                14,
                (0, 255, 255),
                1,
            )  # deadband
            for i in range(1, len(self.trajectory)):
                cv2.line(cv_image, self.trajectory[i-1], self.trajectory[i], (255, 0, 255), 2)

            dashboard = np.hstack((cv_image, panel))

            if self.metrics_saved and self.terminal_time is not None:
                if time.perf_counter() - self.terminal_time < self.terminal_display_duration:
                    overlay = dashboard.copy()
                    cv2.rectangle(overlay, (110, 80), (800, 405), (0, 0, 0), -1)
                    if self.metrics['result'] == "SUCCESS":
                        color = (0, 255, 0)
                    elif self.metrics['result'] == "PRECISION_FAIL":
                        color = (0, 165, 255)
                    else:
                        color = (0, 0, 255)
                    cv2.putText(overlay, f"MISSION {self.metrics['result']}", (180, 135), H_FONT, 0.9, color, 2)

                    cv2.putText(overlay, f"Controller: {self.metrics['controller']}", (155, 185), F_FONT, 0.65, (255, 255, 255), 1)
                    cv2.putText(overlay, f"Duration: {self.metrics['mission_duration_sec']:.1f}s", (155, 225), F_FONT, 0.65, (255, 255, 255), 1)
                    cv2.putText(overlay, f"Max Error: {self.metrics['max_center_error']:.1f}px", (155, 265), F_FONT, 0.65, (255, 255, 255), 1)

                    final_error = self.metrics.get('final_center_error_px')
                    final_err_str = f"{final_error:.1f}px" if final_error is not None else "None"
                    cv2.putText(overlay, f"Final Error: {final_err_str}", (155, 305), F_FONT, 0.65, (255, 255, 255), 1)

                    cv2.putText(overlay, f"Marker Losses: {self.metrics['marker_loss_count']}", (155, 345), F_FONT, 0.65, (255, 255, 255), 1)
                    cv2.putText(overlay, f"Avg FPS: {self.metrics.get('fresh_camera_fps', 0.0):.1f}", (155, 385), F_FONT, 0.65, (255, 255, 255), 1)
                    cv2.addWeighted(overlay, 0.8, dashboard, 0.2, 0, dashboard)

            if self.status and self.status.state in [MissionStatus.STATE_ALIGN, MissionStatus.STATE_DESCEND] and not self.saved_screenshot:
                if self.fresh_frame_count > 10: # Wait a bit for FPS to stabilize
                    cv2.imwrite('/home/devuser/artifacts/descend_dashboard.png', dashboard)
                    self.saved_screenshot = True
                    self.get_logger().info("Saved dashboard screenshot to descend_dashboard.png")

            cv2.imshow("Drone Camera View", dashboard)
            cv2.waitKey(1)
        except Exception as e:
            self.get_logger().error(f'Could not process display frame: {e}')

def main(args=None):
    rclpy.init(args=args)
    camera_viewer = CameraViewer()
    try:
        rclpy.spin(camera_viewer)
    except KeyboardInterrupt:
        pass
    finally:
        camera_viewer.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
