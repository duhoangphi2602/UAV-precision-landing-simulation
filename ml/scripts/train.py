import os
import yaml
import argparse
from ultralytics import YOLO

def train(cfg_path, override_epochs=None, override_name=None):
    with open(cfg_path, 'r') as f:
        cfg = yaml.safe_load(f)

    model = YOLO(cfg['model'])

    train_args = {
        'data': cfg['data'],
        'epochs': override_epochs if override_epochs is not None else cfg['epochs'],
        'patience': cfg['patience'],
        'batch': cfg['batch'],
        'imgsz': cfg['imgsz'],
        'device': cfg['device'],
        'workers': cfg['workers'],
        'seed': cfg['seed'],
        'cache': cfg['cache'],
        'project': os.path.abspath(cfg['project']),
        'name': override_name if override_name else cfg['name'],
        'exist_ok': cfg.get('exist_ok', False)
    }

    results = model.train(**train_args)
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--cfg', type=str, default='ml/configs/yolov8n_uavdt_baseline.yaml')
    parser.add_argument('--smoke', action='store_true', help='Run a quick smoke test')
    args = parser.parse_args()

    if args.smoke:
        print("Running SMOKE test...")
        train(args.cfg, override_epochs=1, override_name='yolov8n_uavdt_baseline_smoke')
    else:
        print("Running FULL training...")
        train(args.cfg)
