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


#ifndef PRECISION_LANDING_CONTROL_CPP__PID_CONTROLLER_HPP_
#define PRECISION_LANDING_CONTROL_CPP__PID_CONTROLLER_HPP_

#include <algorithm>
#include <cmath>

namespace precision_landing_control_cpp
{

struct PIDConfig
{
  double kp = 0.0;
  double ki = 0.0;
  double kd = 0.0;
  double deadband = 0.0;
  double output_min = -1.0;
  double output_max = 1.0;
  double integral_min = -0.5;
  double integral_max = 0.5;
  double stale_timeout = 1.0;   // seconds
};

class PIDController
{
public:
  explicit PIDController(const PIDConfig & config)
  : config_(config) {}

  double compute(double error, double dt);
  void reset();
  void set_config(const PIDConfig & config);

private:
  PIDConfig config_;
  double integral_ = 0.0;
  double prev_error_ = 0.0;
  bool first_sample_ = true;
};

}  // namespace precision_landing_control_cpp

#endif  // PRECISION_LANDING_CONTROL_CPP__PID_CONTROLLER_HPP_
