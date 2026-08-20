// Copyright 2026 User
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
// THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
// THE SOFTWARE.


#include "precision_landing_control_cpp/pid_controller.hpp"

namespace precision_landing_control_cpp
{

void PIDController::set_config(const PIDConfig & config)
{
  config_ = config;
}

void PIDController::reset()
{
  integral_ = 0.0;
  prev_error_ = 0.0;
  first_sample_ = true;
}

double PIDController::compute(double error, double dt)
{
  if (std::isnan(error) || std::isinf(error) || dt <= 0.0 || std::isnan(dt) || std::isinf(dt)) {
    return 0.0;
  }

  if (std::abs(error) <= config_.deadband) {
    // error = 0.0; // optionally zero the error if inside deadband
    return 0.0;
  }

  // Proportional
  double p = config_.kp * error;

  // Integral
  integral_ += error * dt;
  integral_ = std::clamp(integral_, config_.integral_min, config_.integral_max);
  double i = config_.ki * integral_;

  // Derivative
  double derivative = 0.0;
  if (first_sample_) {
    first_sample_ = false;
    // No derivative on first sample
  } else {
    derivative = (error - prev_error_) / dt;
  }
  double d = config_.kd * derivative;

  prev_error_ = error;

  double output = p + i + d;
  return std::clamp(output, config_.output_min, config_.output_max);
}

}  // namespace precision_landing_control_cpp
