# Hướng dẫn Collaboration cho LaTeX Report

## Cấu trúc thư mục

```
report/
├── REPORT_RTSP_RTP.tex          # File main (CHỈ import sections)
├── REPORT_RTSP_RTP_BACKUP.tex   # Backup file gốc
├── LOGO.png                      # Logo trường
├── DIAGRAM1.png                  # Sơ đồ kiến trúc
└── sections/                     # Thư mục chứa các section files
    ├── 0_trang_bia.tex          # Trang bìa và mục lục
    ├── 1_thong_tin.tex          # Thông tin nhóm
    ├── 2_rtsp_rtp.tex           # RTSP/RTP cơ bản (4 điểm)
    ├── 3_hd_streaming.tex       # HD Streaming (3 điểm)
    ├── 4_buffer.tex             # Client-Side Buffer (2.5 điểm)
    └── 5_ket_luan.tex           # Kết luận
```

## Phân công thành viên

| File | Người phụ trách | Nội dung | Điểm |
|------|----------------|----------|------|
| `0_trang_bia.tex` | ✅ Đã hoàn thành | Trang bìa, mục lục | - |
| `1_thong_tin.tex` | ✅ Đã hoàn thành | Thông tin nhóm, tổng quan | - |
| `2_rtsp_rtp.tex` | **Trần Hoàng Phúc** | RTSP/RTP cơ bản | 4.0 |
| `3_hd_streaming.tex` | **Nguyễn Hữu Gia Minh** | HD Video với Frame Fragmentation | 3.0 |
| `4_buffer.tex` | **Nguyễn Khánh Linh** | Client-Side Buffer Implementation | 2.5 |
| `5_ket_luan.tex` | **Cả nhóm** | Kết luận và hướng phát triển | - |

## Quy trình làm việc với Git

### 1. Clone repository

```bash
git clone <repository-url>
cd SocketHD-main/report
```

### 2. Tạo branch riêng cho mỗi thành viên

```bash
# Trần Hoàng Phúc
git checkout -b phuc/rtsp-rtp

# Nguyễn Hữu Gia Minh
git checkout -b minh/hd-streaming

# Nguyễn Khánh Linh
git checkout -b linh/buffer
```

### 3. Làm việc trên branch riêng

Mỗi thành viên chỉ chỉnh sửa file của mình:

```bash
# Ví dụ: Phúc chỉnh sửa 2_rtsp_rtp.tex
cd sections
# Chỉnh sửa file...
git add 2_rtsp_rtp.tex
git commit -m "Update RTSP/RTP implementation details"
git push origin phuc/rtsp-rtp
```

**LƯU Ý QUAN TRỌNG:**
- ❌ **KHÔNG** chỉnh sửa file `REPORT_RTSP_RTP.tex` (file main)
- ❌ **KHÔNG** chỉnh sửa file của thành viên khác
- ✅ **CHỈ** chỉnh sửa file được phân công

### 4. Merge vào main branch

Sau khi hoàn thành phần của mình:

```bash
# Chuyển về main branch
git checkout main

# Pull latest changes
git pull origin main

# Merge branch của mình
git merge phuc/rtsp-rtp   # hoặc minh/hd-streaming, linh/buffer

# Push lên remote
git push origin main
```

**Vì mỗi người làm file riêng → KHÔNG có merge conflicts!**

## Biên dịch LaTeX

### Yêu cầu

Cài đặt LaTeX distribution:
- **Windows:** MiKTeX hoặc TeX Live
- **macOS:** MacTeX
- **Linux:** TeX Live

### Compile command

```bash
# Di chuyển vào thư mục report
cd d:\UNIVERSITY\SECOND_YEAR\MANG_MAY_TINH\SOCKET\SocketHD-main\report

# Compile LaTeX
pdflatex REPORT_RTSP_RTP.tex
pdflatex REPORT_RTSP_RTP.tex  # Chạy 2 lần để update references
```

### Kiểm tra kết quả

Sau khi compile thành công, file `REPORT_RTSP_RTP.pdf` sẽ được tạo ra.

## Tips và Best Practices

### 1. Commit thường xuyên

```bash
git add sections/2_rtsp_rtp.tex
git commit -m "Add RTSP state machine explanation"
```

### 2. Pull trước khi push

```bash
git pull origin main
git push origin main
```

### 3. Kiểm tra LaTeX syntax

Trước khi commit, chạy compile để đảm bảo không có lỗi:

```bash
pdflatex REPORT_RTSP_RTP.tex
```

### 4. Comment code rõ ràng

```latex
% ===================================================================
% PHẦN NÀY DO: Trần Hoàng Phúc phụ trách
% Nội dung: Triển khai RTSP/RTP cơ bản (4 điểm)
% ===================================================================
```

### 5. Sử dụng labels và references

```latex
% Trong section
\subsection{RTP Header}\label{sec:rtp-header}

% Tham chiếu từ section khác
Như đã trình bày trong phần~\ref{sec:rtp-header}...
```

## Xử lý Conflicts (nếu có)

Nếu vẫn xảy ra conflicts (rất hiếm khi):

```bash
# Xem files bị conflict
git status

# Mở file và tìm các dòng:
# <<<<<<< HEAD
# ... code từ main branch ...
# =======
# ... code từ branch của bạn ...
# >>>>>>> branch-name

# Chọn version đúng, xóa các markers (<<<, ===, >>>)

# Sau khi sửa xong
git add <file>
git commit -m "Resolve merge conflict"
```

## Checklist trước khi submit

- [ ] Tất cả sections đã hoàn thành
- [ ] LaTeX compile thành công không có errors
- [ ] PDF output hiển thị đúng format
- [ ] Tất cả references và citations đúng
- [ ] Code listings có syntax highlighting
- [ ] Images/diagrams hiển thị rõ ràng
- [ ] Table of contents đúng page numbers
- [ ] Trang bìa có đầy đủ thông tin nhóm

## Liên hệ

Nếu có vấn đề kỹ thuật:
1. Tạo issue trên GitHub repository
2. Tag @nhóm-trưởng
3. Mô tả chi tiết vấn đề (error message, screenshots)

## References

- [Git Branching Tutorial](https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging)
- [LaTeX Documentation](https://www.overleaf.com/learn)
- [RTSP RFC 2326](https://tools.ietf.org/html/rfc2326)
- [RTP RFC 3550](https://tools.ietf.org/html/rfc3550)

---

**Cập nhật lần cuối:** 2024-12-21  
**Người tạo:** GitHub Copilot Assistant
