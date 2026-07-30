import csv
import json

def analyze_learning_curve(csv_path):
    epochs = []
    map50 = []
    map50_95 = []

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        # Handle leading spaces in headers
        headers = [h.strip() for h in reader.fieldnames]
        reader.fieldnames = headers
        for row in reader:
            epochs.append(int(float(row['epoch'])))
            map50.append(float(row['metrics/mAP50(B)']))
            map50_95.append(float(row['metrics/mAP50-95(B)']))

    first_logged_epoch = epochs[0]
    final_epoch = epochs[-1]
    best_epoch = epochs[map50.index(max(map50))]

    # Epoch reaching mAP50 = 0.80
    epoch_80 = next((e for e, m in zip(epochs, map50) if m >= 0.80), -1)

    # Epoch reaching 95% of final mAP50
    final_map50 = map50[-1]
    target_95 = final_map50 * 0.95
    epoch_95_final = next((e for e, m in zip(epochs, map50) if m >= target_95), -1)

    return {
        "first_logged_epoch": first_logged_epoch,
        "final_epoch": final_epoch,
        "best_epoch": best_epoch,
        "epoch_reach_0.80_mAP50": epoch_80,
        "epoch_reach_95pct_final_mAP50": epoch_95_final,
        "final_mAP50": float(final_map50),
        "final_mAP50_95": float(map50_95[-1])
    }

if __name__ == "__main__":
    cand_a_csv = "ml/experiments/yolov8n_uavdt_vehicle_960_v1/results.csv"
    cand_b_csv = "ml/experiments/yolov8n_p2_uavdt_vehicle_960_v1/results.csv"

    res = {
        "Candidate_A": analyze_learning_curve(cand_a_csv),
        "Candidate_B": analyze_learning_curve(cand_b_csv)
    }

    with open("ml/reports/learning_curve_audit.json", "w") as f:
        json.dump(res, f, indent=4)

    print(json.dumps(res, indent=4))
