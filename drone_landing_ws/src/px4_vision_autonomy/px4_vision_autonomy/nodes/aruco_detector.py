#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point, PoseStamped
from std_msgs.msg import String
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
        self.camera_topic = self.get_parameter('camera_topic').get_parameter_value().string_value
        self.marker_size = self.get_parameter('marker_size').get_parameter_value().double_value
        self.target_marker_id = self.get_parameter('marker_id').get_parameter_value().integer_value

        self.pose_pub = self.create_publisher(PoseStamped, '/aruco/detections', 10)
        self.error_pub = self.create_publisher(Point, '/aruco/center_error', 10)
        self.debug_image_pub = self.create_publisher(Image, '/aruco/debug_image', 10)

        self.subscription = self.create_subscription(Image, self.camera_topic, self.image_callback, 10)
        self.status_sub = self.create_subscription(String, '/mission/status', self.status_callback, 10)

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
        self.mission_status = "UNKNOWN"

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
            
            if "SCAN" in self.mission_status and not hasattr(self, 'saved_debug_frame'):
                import cv2
                cv2.imwrite('/home/devuser/drone_landing_ws/src/px4_vision_autonomy/debug_frame.png', cv_image)
                self.saved_debug_frame = True
                self.get_logger().info("Saved debug camera frame to debug_frame.png")

            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            if self.use_new_api:
                corners, ids, rejected = self.detector.detectMarkers(gray)
            else:
                corners, ids, rejected = cv2.aruco.detectMarkers(
                    gray, self.aruco_dict, parameters=self.aruco_params)
            
            h, w = cv_image.shape[:2]
            center_x, center_y = int(w / 2), int(h / 2)
            cv2.circle(cv_image, (center_x, center_y), 5, (255, 0, 0), -1) # Image center (Blue)

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
                        
                        error_msg = Point()
                        error_msg.x = float(error_x)
                        error_msg.y = float(error_y)
                        error_msg.z = 0.0
                        self.error_pub.publish(error_msg)
                        
                        cv2.putText(cv_image, f"ID: {marker_id[0]}", (int(marker_corners[0][0]), int(marker_corners[0][1]) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        cv2.putText(cv_image, f"dx: {error_x:.1f} dy: {error_y:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            cv2.putText(cv_image, f"FPS: {self.fps:.1f}", (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(cv_image, self.mission_status, (10, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

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
