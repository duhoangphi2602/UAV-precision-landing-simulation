import cv2
import sys

image = cv2.imread('drone_landing_ws/debug_frame.png')
if image is None:
    print("Could not read image")
    sys.exit(1)

dictionary = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters_create()

gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
corners, ids, rejected = cv2.aruco.detectMarkers(gray, dictionary, parameters=parameters)

print(f"Number of rejected candidates: {len(rejected)}")
if len(rejected) > 0:
    for i, r in enumerate(rejected):
        print(f"Candidate {i} corners: {r}")

if ids is not None:
    print(f"Marker detected! IDs: {ids.flatten()}")
    if 0 in ids.flatten():
        print("PASS: Marker ID 0 is detected!")
    else:
        print("FAIL: Marker detected but ID is not 0")
else:
    print("FAIL: No marker detected in the frame")

cv2.aruco.drawDetectedMarkers(image, corners, ids)
cv2.imwrite('debug_frame_annotated.png', image)
