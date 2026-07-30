# SLICE 3C: ACCURACY/LATENCY PARETO OPTIMIZATION AND FINAL AUDIT

## 1. INITIALIZATION AUDIT
**CANDIDATE_A_INIT:**
- Exact checkpoint: `ml/experiments/yolov8n_uavdt_baseline_v1/weights/best.pt`
- Resume: False (Transfer learning)
- Transferred tensors: All backbone and neck layers (YOLOv8n architecture). Only the final detection head was re-initialized for 1 class (`cls_remap: true`).
- Initial class count: 1 (vehicle)

**CANDIDATE_B_INIT:**
- Exact checkpoint: `yolov8n-p2.yaml` (Official architecture without UAVDT pretrained weights)
- Resume: False
- Transferred tensors: Mostly standard COCO or random initialization for the new P2 architecture.
- P2-specific randomly initialized layers: The new P2 detection head and associated upsampling layers.
- Initial class count: 1 (vehicle)

*Verification:* Candidate A's first logged epoch (epoch 1) recorded a validation mAP50 of 0.876. This confirms that Candidate A benefited massively from transferred weights. Candidate B started near zero and took 11 epochs to reach 0.80 mAP50.

---

## 2. LEARNING-CURVE INTERPRETATION
- **Candidate A:** First epoch mAP50 = 0.876. Reached 95% of final mAP50 at Epoch 1. Best epoch: 90. Final test mAP50: 0.877.
- **Candidate B:** First epoch mAP50 < 0.10. Reached 0.80 mAP50 at Epoch 11. Reached 95% of final mAP50 at Epoch 20. Best epoch: 82. Final test mAP50: 0.878.

**Conclusion:** *FAST CONVERGENCE không đồng nghĩa với BETTER FINAL GENERALIZATION. LARGE IMPROVEMENT FROM LOW START không đồng nghĩa với BETTER MODEL.* Dù Candidate B có learning curve rất ấn tượng (tăng mAP50 từ 0 lên 0.878), nó thực tế chỉ đạt mức ngang ngửa Candidate A (vốn đã bắt đầu từ 0.876 nhờ domain knowledge transfer).

---

## 3. FAIR LATENCY BENCHMARK
Executed in a single Python process, interleaved A→B→B→A, with `torch.cuda.synchronize()`. Test on 500 images, `imgsz=960`, `batch=1`.

**Candidate A (`yolov8n_uavdt_vehicle_960_v1.pt`)**
- Total Mean: **~6.8 ms** (Inference: 4.4 ms, Pre: 1.7 ms, NMS: 0.7 ms)
- P95: 7.4 ms
- P99: 8.9 ms

**Candidate B (`yolov8n_p2_uavdt_vehicle_960_v1.pt`)**
- Total Mean: **~10.1 ms** (Inference: 7.3 ms, Pre: 1.6 ms, NMS: 1.1 ms)
- P95: 15.4 ms
- P99: 16.3 ms

**Conclusion:** Candidate A is roughly 33% faster in end-to-end latency and inference. Cấu trúc P2 head khiến Candidate B chậm hơn đáng kể.

---

## 4. SIZE-BIN COMPARISON
Recall performance by object size on test set:

| Object Size (max dim) | Candidate A Recall | Candidate B (P2) Recall | Delta |
|---|---|---|---|
| **Tiny** (<16 px) | 42.6% | 45.0% | **+2.4%** |
| **Small** (16-32 px) | 71.0% | 72.1% | **+1.1%** |
| **Medium** (32-96 px) | 84.8% | 84.2% | -0.6% |
| **Large** (>96 px) | 91.3% | 88.3% | -3.0% |

**Conclusion:** P2 layer *thực sự giúp ích* cho tiny và small objects đúng như thiết kế, nhưng lại làm suy giảm khả năng phát hiện medium và large objects, dẫn đến tổng recall không tăng.

---

## 5. OPERATING-POINT COMPARISON
Fair sweep performed on validation set (F1 max) -> evaluated on Test set:
- Cả hai model đều đạt Max F1 tại **Confidence = 0.20**.
- **Candidate A:** Test Precision = 0.884, Test Recall = 0.743, **Test F1 = 0.807**
- **Candidate B:** Test Precision = 0.881, Test Recall = 0.730, **Test F1 = 0.798**

**Conclusion:** Tại operating point tối ưu, Candidate A đánh bại Candidate B ở cả Precision, Recall và F1.

---

## 6. FINAL MODEL DECISION

**Result:** `A_WINS`
- Candidate B chỉ cải thiện tiny recall (+2.4%), nhưng bị sụt giảm large recall, dẫn đến F1 chung kém hơn Candidate A.
- Candidate A nhẹ hơn, inference nhanh hơn (4.4ms vs 7.3ms), và có độ ổn định tổng thể tốt hơn trên tập test.
- Candidate A chính thức là deployment model. Candidate B được lưu trữ làm research artifact.

---

## FINAL OUTPUT STATUS
- `FINAL_MODEL=CANDIDATE_A`
- `LEARNING_CURVE_EXPLANATION=VERIFIED`
- `FAIR_LATENCY_BENCHMARK=PASS`
- `SIZE_BIN_ANALYSIS=PASS`
- `READY_FOR_SLICE_4=YES`
