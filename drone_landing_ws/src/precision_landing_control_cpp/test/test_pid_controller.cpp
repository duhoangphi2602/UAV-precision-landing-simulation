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


#include <gtest/gtest.h>
#include "precision_landing_control_cpp/pid_controller.hpp"

using precision_landing_control_cpp::PIDConfig;
using precision_landing_control_cpp::PIDController;

TEST(PIDControllerTest, ZeroError) {
  PIDConfig config;
  config.kp = 1.0; config.ki = 0.0; config.kd = 0.0;
  PIDController pid(config);
  EXPECT_DOUBLE_EQ(pid.compute(0.0, 0.1), 0.0);
}

TEST(PIDControllerTest, PositiveError) {
  PIDConfig config;
  config.kp = 1.0; config.ki = 0.0; config.kd = 0.0;
  config.output_max = 5.0;
  config.output_min = -5.0;
  PIDController pid(config);
  EXPECT_DOUBLE_EQ(pid.compute(2.0, 0.1), 2.0);
}

TEST(PIDControllerTest, NegativeError) {
  PIDConfig config;
  config.kp = 1.0; config.ki = 0.0; config.kd = 0.0;
  config.output_max = 5.0;
  config.output_min = -5.0;
  PIDController pid(config);
  EXPECT_DOUBLE_EQ(pid.compute(-2.0, 0.1), -2.0);
}

TEST(PIDControllerTest, Deadband) {
  PIDConfig config;
  config.kp = 1.0; config.ki = 0.0; config.kd = 0.0;
  config.deadband = 1.0;
  config.output_max = 5.0;
  config.output_min = -5.0;
  PIDController pid(config);
  EXPECT_DOUBLE_EQ(pid.compute(0.5, 0.1), 0.0);
  // Outside the deadband, proportional output remains unchanged.
  EXPECT_DOUBLE_EQ(pid.compute(2.0, 0.1), 2.0);
}

TEST(PIDControllerTest, Saturation) {
  PIDConfig config;
  config.kp = 10.0;
  config.output_max = 5.0;
  config.output_min = -5.0;
  PIDController pid(config);
  EXPECT_DOUBLE_EQ(pid.compute(1.0, 0.1), 5.0);   // 10.0 -> clamped to 5.0
  EXPECT_DOUBLE_EQ(pid.compute(-1.0, 0.1), -5.0);
}

TEST(PIDControllerTest, IntegralLimit) {
  PIDConfig config;
  config.kp = 0.0; config.ki = 10.0; config.kd = 0.0;
  config.integral_max = 1.0;
  config.integral_min = -1.0;
  config.output_max = 100.0;
  config.output_min = -100.0;
  PIDController pid(config);
  // integrate +10 for dt=1 -> integral = 10, clamped to 1. Output = ki*1 = 10
  EXPECT_DOUBLE_EQ(pid.compute(10.0, 1.0), 10.0);
}

TEST(PIDControllerTest, Reset) {
  PIDConfig config;
  config.kp = 0.0; config.ki = 1.0; config.kd = 0.0;
  config.output_max = 10.0;
  config.output_min = -10.0;
  config.integral_max = 10.0;
  config.integral_min = -10.0;
  PIDController pid(config);
  EXPECT_DOUBLE_EQ(pid.compute(1.0, 1.0), 1.0);
  pid.reset();
  EXPECT_DOUBLE_EQ(pid.compute(0.0, 1.0), 0.0);   // should be 0 because integral is reset
}

TEST(PIDControllerTest, DerivativeFirstSample) {
  PIDConfig config;
  config.kp = 0.0; config.ki = 0.0; config.kd = 1.0;
  config.output_max = 10.0;
  config.output_min = -10.0;
  PIDController pid(config);
  EXPECT_DOUBLE_EQ(pid.compute(1.0, 1.0), 0.0);   // First sample, derivative is 0
  EXPECT_DOUBLE_EQ(pid.compute(2.0, 1.0), 1.0);   // Second sample, derivative is (2-1)/1 = 1
}

TEST(PIDControllerTest, InvalidDt) {
  PIDConfig config;
  config.kp = 1.0; config.ki = 1.0; config.kd = 1.0;
  PIDController pid(config);
  EXPECT_DOUBLE_EQ(pid.compute(1.0, -1.0), 0.0);
  EXPECT_DOUBLE_EQ(pid.compute(1.0, 0.0), 0.0);
}

TEST(PIDControllerTest, FiniteOutput) {
  PIDConfig config;
  config.kp = 1.0;
  PIDController pid(config);
  EXPECT_DOUBLE_EQ(pid.compute(std::nan(""), 0.1), 0.0);
  EXPECT_DOUBLE_EQ(pid.compute(std::numeric_limits<double>::infinity(), 0.1), 0.0);
}

int main(int argc, char ** argv)
{
  testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
