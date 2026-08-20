import unittest
import cv2
import numpy as np


def create_marker(aruco_dict, marker_id, size):
    if hasattr(cv2.aruco, 'generateImageMarker'):
        return cv2.aruco.generateImageMarker(aruco_dict, marker_id, size)

    marker = np.zeros((size, size), dtype=np.uint8)
    cv2.aruco.drawMarker(aruco_dict, marker_id, size, marker, 1)
    return marker


def create_detector_parameters():
    if hasattr(cv2.aruco, 'DetectorParameters_create'):
        return cv2.aruco.DetectorParameters_create()
    return cv2.aruco.DetectorParameters()


class TestArucoDetection(unittest.TestCase):
    def test_detection(self):
        # Generate a marker
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker_id = 0
        marker_img = create_marker(aruco_dict, marker_id, 200)
        
        # Create a larger image and place marker
        bg = np.ones((400, 400), dtype=np.uint8) * 255
        bg[100:300, 100:300] = marker_img
        
        # Detect
        params = create_detector_parameters()
        corners, ids, rejected = cv2.aruco.detectMarkers(bg, aruco_dict, parameters=params)
        
        self.assertIsNotNone(ids)
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[0][0], marker_id)


if __name__ == '__main__':
    unittest.main()
