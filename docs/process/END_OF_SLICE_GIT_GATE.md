# MANDATORY END-OF-SLICE GIT CLOSURE GATE

- Không mở Slice mới khi Slice hiện tại chưa commit và working tree chưa sạch.
- Mọi Slice phải chạy source/test/acceptance checks.
- Phải audit tracked, staged, untracked và ignored files.
- Không commit dataset, model binary, training output hoặc local ML reports.
- Chỉ selective-stage source/config/test/reproduction documentation.
- Phải merge vào main và tạo annotated tag.
- Không push remote nếu người dùng chưa yêu cầu.
- Nếu audit phát hiện forbidden artifact đang tracked, Slice chưa được đóng.
