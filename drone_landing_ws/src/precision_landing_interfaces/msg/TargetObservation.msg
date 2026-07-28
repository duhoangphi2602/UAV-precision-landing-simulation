std_msgs/Header header
uint32 sequence_id

uint8 MODE_FIXED=0
uint8 MODE_MOVING=1
uint8 MODE_GIMBAL=2
uint8 mode

string source
bool valid
bool stale

int32 target_id
int32 track_id

float32 center_x_px
float32 center_y_px
float32 error_x
float32 error_y
float32 error_magnitude
float32 confidence

bool pose_valid
geometry_msgs/Point position_m
