.PHONY: build setup-gesture verify-assets test verify demo-python demo-cpp demo-moving-aruco demo-gesture-control demo-final demo-final-cpu demo-final-gpu stop

build:
	./scripts/build_workspace.sh

setup-gesture:
	./scripts/setup_gesture.sh

verify-assets:
	./scripts/verify_gesture_assets.sh

test:
	./scripts/verify_halfday.sh

verify: test

demo-python:
	./scripts/run_demo_python_baseline.sh

demo-cpp:
	./scripts/run_demo_cpp_control.sh

demo-moving-aruco:
	./scripts/run_demo_moving_aruco.sh

demo-gesture-control:
	./scripts/run_demo_gesture_control.sh

demo-final: demo-final-cpu

demo-final-cpu:
	./scripts/run_demo_final.sh

demo-final-gpu:
	COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml ./scripts/run_demo_final.sh

stop:
	./scripts/stop_demo.sh
