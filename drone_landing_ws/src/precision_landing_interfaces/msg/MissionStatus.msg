std_msgs/Header header

uint8 MODE_FIXED=0
uint8 MODE_MOVING=1
uint8 MODE_GIMBAL=2
uint8 MODE_GESTURE=3
uint8 MODE_FINAL=4
uint8 mode

uint8 STATE_INIT=0
uint8 STATE_TAKEOFF=1
uint8 STATE_NAVIGATE=2
uint8 STATE_SCAN=3
uint8 STATE_ALIGN=4
uint8 STATE_DESCEND=5
uint8 STATE_LAND=6
uint8 STATE_COMPLETE=7
uint8 STATE_FAILED=8
uint8 STATE_GESTURE_READY=9
uint8 STATE_MANUAL_GESTURE_FLIGHT=10
uint8 STATE_TARGET_AVAILABLE=11
uint8 STATE_AUTO_LAND_AUTHORIZED=12
uint8 state

bool connected
bool armed
bool target_locked
bool terminal
bool success

float32 elapsed_sec
string detail
bool touchdown_detected
bool touchdown_error_valid
float32 touchdown_horizontal_error_m
uint32 re_align_count
