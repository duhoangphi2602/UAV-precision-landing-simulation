# Evaluation Report: YOLOv8n UAVDT Baseline (v1)

## Overview
- **Model**: YOLOv8n (baseline)
- **Dataset**: Roboflow Universe Aerial Vehicles by UAVDT (v1)
- **Epochs**: 50
- **Batch Size**: 16
- **Image Size**: 640
- **Hardware**: RTX 3060 12GB
- **Inference Latency (per image)**: 1.6ms (GPU)

## Aggregate Metrics
- **mAP@50**: 0.501
- **mAP@50-95**: 0.335
- **Precision**: 0.652
- **Recall**: 0.461

## Per-Class Metrics
| Class | Images | Instances | Precision | Recall | mAP@50 | mAP@50-95 |
|---|---|---|---|---|---|---|
| **bus** | 131 | 251 | 0.723 | 0.438 | 0.495 | 0.333 |
| **car** | 514 | 14063 | 0.762 | 0.743 | 0.780 | 0.520 |
| **truck** | 266 | 750 | 0.541 | 0.288 | 0.311 | 0.205 |
| **van** | 421 | 1975 | 0.582 | 0.374 | 0.417 | 0.282 |

## Analysis & Limitations
1. **Class Imbalance Impact**: The dataset is heavily skewed towards cars (14,063 instances) versus buses (251 instances), trucks (750 instances) and vans (1975 instances). `car` has significantly higher performance (mAP50 = 0.780) compared to `truck` (0.311) and `van` (0.417), demonstrating the direct impact of class imbalance.
2. **Small-Object Performance**: Aerial vehicles are often extremely small. Without high-resolution native inference (trained at 640px while stretched from 960x720), the recall is notably low for minority classes (truck recall is 0.288).
3. **Preprocessing Limitation**: The Roboflow dataset was previously stretched to 960x720, and YOLO applies its own letterbox/resize to 640. This double-interpolation may hurt pixel-level precision for very small bounding boxes.
4. **False Positives / Negatives**: The relatively low overall recall (0.461) indicates high false negatives (missing many objects). However, precision is higher (0.652), meaning when the model predicts a vehicle, it is usually correct.

## Conclusion
This baseline establishes a measurable starting point for real-time edge deployment. While not production-ready in terms of recall, its 1.6ms inference latency on RTX 3060 demonstrates suitability for real-time tracking pipelines (like ByteTrack/Gimbal integration). Future work should focus on data augmentation, slicing/SAHI, or native higher-resolution training to address the small-object and class imbalance issues.
