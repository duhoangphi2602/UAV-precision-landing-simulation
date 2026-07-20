import re

file_path = '/home/hoangphi/Projects/UAV-precision-landing-simulation/drone_landing_ws/src/px4_vision_autonomy/px4_vision_autonomy/nodes/mission_commander.py'
with open(file_path, 'r') as f:
    content = f.read()

# Replace wp_north = 0.0 and wp_east = 5.8
content = re.sub(r'self\.wp_north = 0\.0', 'self.wp_north = 5.8', content)
content = re.sub(r'self\.wp_east = 5\.8', 'self.wp_east = 0.0', content)

with open(file_path, 'w') as f:
    f.write(content)

print("Waypoint fixed in mission_commander.py")
