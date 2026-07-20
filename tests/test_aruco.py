import cv2
import numpy as np
import pytest

def generate_synthetic_image(marker_id, x_offset, y_offset):
    # Create a white image 640x480
    img = np.ones((480, 640, 3), dtype=np.uint8) * 255
    
    if marker_id is not None:
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        # 4x4 marker, 100x100 pixels
        marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, 100)
        # Convert to 3 channels
        marker_img = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)
        
        # Base center is 320, 240
        center_x = 320 + x_offset
        center_y = 240 + y_offset
        
        # Top left
        tl_x = center_x - 50
        tl_y = center_y - 50
        
        if 0 <= tl_x <= 640-100 and 0 <= tl_y <= 480-100:
            img[tl_y:tl_y+100, tl_x:tl_x+100] = marker_img
            
    return img

def test_centered_marker():
    img = generate_synthetic_image(0, 0, 0)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    aruco_params = cv2.aruco.DetectorParameters()
    if hasattr(cv2.aruco, 'ArucoDetector'):
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        corners, ids, rejected = detector.detectMarkers(img)
    else:
        corners, ids, rejected = cv2.aruco.detectMarkers(img, aruco_dict, parameters=aruco_params)
        
    assert ids is not None
    assert ids[0][0] == 0
    # Center of marker should be near 320, 240
    c = corners[0][0]
    mx = sum([pt[0] for pt in c]) / 4
    my = sum([pt[1] for pt in c]) / 4
    dx = 320 - mx
    dy = 240 - my
    assert abs(dx) < 2
    assert abs(dy) < 2

def test_left_marker():
    img = generate_synthetic_image(0, -100, 0)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    aruco_params = cv2.aruco.DetectorParameters()
    if hasattr(cv2.aruco, 'ArucoDetector'):
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        corners, ids, rejected = detector.detectMarkers(img)
    else:
        corners, ids, rejected = cv2.aruco.detectMarkers(img, aruco_dict, parameters=aruco_params)
        
    c = corners[0][0]
    mx = sum([pt[0] for pt in c]) / 4
    # Marker is at x=220, so center - mx = 320 - 220 = 100 > 0
    dx = 320 - mx
    assert dx > 0

def test_right_marker():
    img = generate_synthetic_image(0, 100, 0)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    aruco_params = cv2.aruco.DetectorParameters()
    if hasattr(cv2.aruco, 'ArucoDetector'):
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        corners, ids, rejected = detector.detectMarkers(img)
    else:
        corners, ids, rejected = cv2.aruco.detectMarkers(img, aruco_dict, parameters=aruco_params)
        
    c = corners[0][0]
    mx = sum([pt[0] for pt in c]) / 4
    # Marker is at x=420, so center - mx = 320 - 420 = -100 < 0
    dx = 320 - mx
    assert dx < 0

def test_wrong_marker():
    img = generate_synthetic_image(1, 0, 0) # wrong ID
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    aruco_params = cv2.aruco.DetectorParameters()
    if hasattr(cv2.aruco, 'ArucoDetector'):
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        corners, ids, rejected = detector.detectMarkers(img)
    else:
        corners, ids, rejected = cv2.aruco.detectMarkers(img, aruco_dict, parameters=aruco_params)
        
    assert ids is not None
    # Node logic checks for target_marker_id == 0, here it's 1. 
    # In the actual node, it rejects. In the test, we verify we got ID=1.
    assert ids[0][0] == 1

def test_no_marker():
    img = generate_synthetic_image(None, 0, 0)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    aruco_params = cv2.aruco.DetectorParameters()
    if hasattr(cv2.aruco, 'ArucoDetector'):
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        corners, ids, rejected = detector.detectMarkers(img)
    else:
        corners, ids, rejected = cv2.aruco.detectMarkers(img, aruco_dict, parameters=aruco_params)
        
    assert ids is None
