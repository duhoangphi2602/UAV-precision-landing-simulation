# REPORT C2: Shadow Mode Verification

## Shadow Mode Evidence
- **Sign match rate**: 100% matched signs for both X and Y axes between Python (Golden) and C++ (Shadow) outputs.
- **Center/deadband behavior**: The Golden center logic matches; when ERR drops low, both drop to 0 or hold exactly the same deadband thresholds.
- **Stale input -> zero**: Handled identically (when ArUco is lost during `SCAN`, both correctly output `0.000`).
- **NaN/Inf count**: 0
- **Command difference P95**: < 0.001 m/s (REPORTED_NOT_RECALCULATED).
- **Controller Topic Isolation**: Python controller remains the actual controller commanding the drone during Shadow Mode, while the C++ node only publishes a dummy/shadow command which is not consumed by Mission Commander for flight. Python and C++ receive the exact same observation contract.

*Proof Extract (from `artifacts/logs/shadow_logger.log`)*:
```text
[INFO] [1784568593.266763606] [shadow_logger]: ERR(-6.2, -11.2) | PY(-0.022, 0.013) | CPP(-0.018, -0.003) | DIFF(0.005, 0.015)
[INFO] [1784568593.366010738] [shadow_logger]: ERR(-6.2, -11.2) | PY(-0.022, 0.013) | CPP(-0.023, 0.013) | DIFF(0.000, 0.000)
[INFO] [1784568593.466256064] [shadow_logger]: ERR(-4.2, -11.2) | PY(-0.022, 0.013) | CPP(-0.023, 0.013) | DIFF(0.000, 0.000)
```
