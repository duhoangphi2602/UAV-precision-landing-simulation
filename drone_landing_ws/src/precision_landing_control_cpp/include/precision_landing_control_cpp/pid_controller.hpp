#ifndef PRECISION_LANDING_CONTROL_CPP__PID_CONTROLLER_HPP_
#define PRECISION_LANDING_CONTROL_CPP__PID_CONTROLLER_HPP_

#include <algorithm>
#include <cmath>

namespace precision_landing_control_cpp
{

struct PIDConfig {
    double kp = 0.0;
    double ki = 0.0;
    double kd = 0.0;
    double deadband = 0.0;
    double output_min = -1.0;
    double output_max = 1.0;
    double integral_min = -0.5;
    double integral_max = 0.5;
    double stale_timeout = 1.0; // seconds
};

class PIDController
{
public:
    explicit PIDController(const PIDConfig & config) : config_(config) {}

    double compute(double error, double dt);
    void reset();
    void set_config(const PIDConfig & config);

private:
    PIDConfig config_;
    double integral_ = 0.0;
    double prev_error_ = 0.0;
    bool first_sample_ = true;
};

} // namespace precision_landing_control_cpp

#endif // PRECISION_LANDING_CONTROL_CPP__PID_CONTROLLER_HPP_
