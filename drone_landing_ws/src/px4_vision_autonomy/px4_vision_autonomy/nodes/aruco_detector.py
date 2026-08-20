#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point, PoseStamped
from std_msgs.msg import String
from precision_landing_interfaces.msg import TargetObservation
import cv2
import numpy as np
import time

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

def cv2_to_imgmsg(cv_image, encoding="bgr8"):
    img_msg = Image()
    img_msg.header.frame_id = "camera_link"
    img_msg.height = cv_image.shape[0]
    img_msg.width = cv_image.shape[1]
    img_msg.encoding = encoding
    img_msg.is_bigendian = 0
    img_msg.step = cv_image.shape[1] * 3
    img_msg.data = cv_image.tobytes()
    return img_msg

class ArucoDetector(Node):
    def __init__(self):
        super().__init__('aruco_detector')
        self.declare_parameter('camera_topic', '/camera')
        self.declare_parameter('marker_size', 0.5)
        self.declare_parameter('marker_id', 0)
        self.declare_parameter('mission_mode', 'fixed')
        self.camera_topic = self.get_parameter('camera_topic').get_parameter_value().string_value
        self.marker_size = self.get_parameter('marker_size').get_parameter_value().double_value
        self.target_marker_id = self.get_parameter('marker_id').get_parameter_value().integer_value
        self.mission_mode = self.get_parameter('mission_mode').get_parameter_value().string_value

        self.pose_pub = self.create_publisher(PoseStamped, '/aruco/detections', 10)
        self.error_pub = self.create_publisher(Point, '/aruco/center_error', 10)
        self.obs_pub = self.create_publisher(TargetObservation, '/precision_landing/target_observation', 10)
        self.debug_image_pub = self.create_publisher(Image, '/aruco/debug_image', 10)

        self.subscription = self.create_subscription(
            Image, self.camera_topic, self.image_callback, qos_profile_sensor_data)
        self.status_sub = self.create_subscription(String, '/mission/status', self.status_callback, 10)

        self.sequence_id = 0

        if hasattr(cv2.aruco, 'DetectorParameters_create'):
            self.aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
            self.aruco_params = cv2.aruco.DetectorParameters_create()
            self.use_new_api = False
        else:
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            self.aruco_params = cv2.aruco.DetectorParameters()
            self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
            self.use_new_api = True

        self.camera_matrix = np.array([[320.0, 0.0, 320.0],
                                       [0.0, 320.0, 240.0],
                                       [0.0, 0.0, 1.0]])
        self.dist_coeffs = np.zeros((5, 1))

        self.last_time = time.time()
        self.fps = 0.0
        self.mission_status = "TEST (STATIC GATE)"

        self.get_logger().info(f'Aruco Detector Started. Listening on {self.camera_topic}')

    def status_callback(self, msg):
        self.mission_status = msg.data

    def image_callback(self, msg):
        try:
            current_time = time.time()
            dt = current_time - self.last_time
            if dt > 0:
                self.fps = 1.0 / dt
            self.last_time = current_time

            cv_image = imgmsg_to_cv2(msg)

            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

            if self.use_new_api:
                corners, ids, rejected = self.detector.detectMarkers(gray)
            else:
                corners, ids, rejected = cv2.aruco.detectMarkers(
                    gray, self.aruco_dict, parameters=self.aruco_params)

            h, w = cv_image.shape[:2]
            center_x, center_y = int(w / 2), int(h / 2)
            cv2.circle(cv_image, (center_x, center_y), 5, (255, 0, 0), -1) # Image center (Blue)

            obs_msg = TargetObservation()
            obs_msg.header = msg.header
            obs_msg.sequence_id = self.sequence_id
            self.sequence_id += 1
            obs_msg.mode = TargetObservation.MODE_MOVING if self.mission_mode == 'moving' else TargetObservation.MODE_FIXED
            obs_msg.source = "aruco"
            obs_msg.valid = False
            obs_msg.stale = False
            obs_msg.track_id = -1
            obs_msg.pose_valid = False

            if ids is not None:
                # cv2.aruco.drawDetectedMarkers(cv_image, corners, ids) # We draw manually

                for i, marker_id in enumerate(ids):
                    if marker_id[0] == self.target_marker_id:
                        marker_points = np.array([[-self.marker_size / 2, self.marker_size / 2, 0],
                                                  [self.marker_size / 2, self.marker_size / 2, 0],
                                                  [self.marker_size / 2, -self.marker_size / 2, 0],
                                                  [-self.marker_size / 2, -self.marker_size / 2, 0]], dtype=np.float32)

                        success, rvec, tvec = cv2.solvePnP(marker_points, corners[i], self.camera_matrix, self.dist_coeffs)

                        if success:
                            # cv2.drawFrameAxes(cv_image, self.camera_matrix, self.dist_coeffs, rvec, tvec, 0.1)
                            pose_msg = PoseStamped()
                            pose_msg.header = msg.header
                            pose_msg.pose.position.x = float(tvec[0][0])
                            pose_msg.pose.position.y = float(tvec[1][0])
                            pose_msg.pose.position.z = float(tvec[2][0])
                            self.pose_pub.publish(pose_msg)

                        marker_corners = corners[i][0]
                        marker_center_x = sum([c[0] for c in marker_corners]) / 4
                        marker_center_y = sum([c[1] for c in marker_corners]) / 4

                        pts = marker_corners.astype(int)
                        cv2.polylines(cv_image, [pts], isClosed=True, color=(0, 255, 0), thickness=4)
                        cv2.circle(cv_image, (int(marker_center_x), int(marker_center_y)), 5, (0, 0, 255), -1)

                        cv2.arrowedLine(cv_image, (center_x, center_y), (int(marker_center_x), int(marker_center_y)), (0, 255, 255), 2)

                        error_x = center_x - marker_center_x
                        error_y = center_y - marker_center_y

                        error_magnitude = np.sqrt(error_x**2 + error_y**2)

                        side_0 = np.linalg.norm(marker_corners[0] - marker_corners[1])
                        side_1 = np.linalg.norm(marker_corners[1] - marker_corners[2])
                        side_2 = np.linalg.norm(marker_corners[2] - marker_corners[3])
                        side_3 = np.linalg.norm(marker_corners[3] - marker_corners[0])
                        marker_side_px = float(np.mean([side_0, side_1, side_2, side_3]))

                        normalized_error = -1.0
                        if np.isfinite(marker_side_px) and marker_side_px > 1.0:
                            normalized_error = float(error_magnitude / marker_side_px)

                        obs_msg.valid = True
                        obs_msg.target_id = int(marker_id[0])
                        obs_msg.center_x_px = float(marker_center_x)
                        obs_msg.center_y_px = float(marker_center_y)
                        obs_msg.error_x = float(error_x)
                        obs_msg.error_y = float(error_y)
                        obs_msg.error_magnitude = float(error_magnitude)
                        obs_msg.marker_side_px = marker_side_px
                        obs_msg.normalized_error = normalized_error

                        # Confidence logic remains unchanged, mapped linearly from error
                        if error_magnitude < 10.0:
                            obs_msg.confidence = 1.0
                        elif error_magnitude < 100.0:
                            obs_msg.confidence = 1.0 - (error_magnitude / 100.0)
                        else:
                            obs_msg.confidence = 0.1

                        if success:
                            obs_msg.pose_valid = True
                            obs_msg.position_m.x = float(tvec[0][0])
                            obs_msg.position_m.y = float(tvec[1][0])
                            obs_msg.position_m.z = float(tvec[2][0])

                        error_msg = Point()
                        error_msg.x = float(error_x)
                        error_msg.y = float(error_y)
                        error_msg.z = float(error_magnitude)
                        self.error_pub.publish(error_msg)
                        break

            self.obs_pub.publish(obs_msg)

            # The dashboard consumes the raw camera stream directly. Avoid a
            # full 1280x960 Python bytes copy on every perception callback unless
            # an explicit debug-image consumer is attached.
            if self.debug_image_pub.get_subscription_count() > 0:
                debug_msg = cv2_to_imgmsg(cv_image, "bgr8")
                debug_msg.header = msg.header
                self.debug_image_pub.publish(debug_msg)

        except Exception as e:
            self.get_logger().error(f'Error in image_callback: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = ArucoDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
