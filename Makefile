.PHONY: build test demo-python demo-cpp verify stop

build:
	./scripts/build_workspace.sh

test:
	./scripts/verify_halfday.sh

demo-python:
	./scripts/run_demo_python_baseline.sh

shadow-cpp:
	./scripts/run_shadow_cpp.sh

demo-cpp:
	./scripts/run_demo_cpp_control.sh

demo-moving-aruco:
	./scripts/run_demo_moving_aruco.sh

verify:
	./scripts/verify_halfday.sh

stop:
	./scripts/stop_demo.sh
