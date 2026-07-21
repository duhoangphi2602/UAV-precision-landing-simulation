# REPORT C3: Full C++ Runtime Evidence

## Runtime Architecture
- **C++ PID**: Acts as the authoritative source for velocity XY during alignment and descent.
- **Python Mission Commander**: Manages the state machine, interacts with MAVSDK, orchestrates the mission sequence, and manages Z descent. The entire mission DOES NOT run solely in C++.

## Mission Sequence
`ARM` -> `TAKEOFF` -> `OFFBOARD` -> `NAVIGATE` -> `SCAN` -> `ALIGN` -> `DESCEND` -> `LAND` -> `DISARMED` -> `MISSION COMPLETE`

## A. Pre-polish Repeatability (3 Consecutive SITL Runs)

### Run 1
- **Run Status**: PASS
- **Mission duration**: ~40 seconds
- **Marker-loss count**: 0
- **Stale count**: 0
- **NaN/Inf count**: 0
- **Cleanup**: PASS

### Run 2
- **Run Status**: PASS
- **Mission duration**: ~40 seconds
- **Marker-loss count**: 0
- **Stale count**: 0
- **NaN/Inf count**: 0
- **Cleanup**: PASS

### Run 3
- **Run Status**: PASS
- **Mission duration**: ~40 seconds
- **Marker-loss count**: 0
- **Stale count**: 0
- **NaN/Inf count**: 0
- **Cleanup**: PASS

## B. Post-polish Final Verification
- **Run Status**: PASS
- **Final Touchdown**: Verified.
- **Disarm**: Verified.
- **Mission Complete**: Verified.
- **Cleanup**: PASS.

*(Note: Pre-polish runs achieved 3/3 SUCCESS. Post-polish validation ran successfully as a single validation run.)*
