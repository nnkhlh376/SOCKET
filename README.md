# HD Video Streaming System - RTP/RTSP

Hệ thống streaming video HD (720p/1080p) sử dụng giao thức RTP/RTSP với các tính năng nâng cao.

## 🎯 Tính năng

### ✅ Core Features
- **RTP/RTSP Protocol**: Streaming video qua mạng
- **HD Support**: Hỗ trợ video 720p và 1080p
- **Frame Fragmentation**: Phân mảnh frames lớn để truyền qua MTU
- **Fragment Reassembly**: Ghép các fragments thành frame hoàn chỉnh

### ✅ Advanced Features
- **Client-Side Buffer**: Bộ đệm 20-100 frames giảm jitter
- **Adaptive Quality Control**: Tự động điều chỉnh chất lượng (LOW/MEDIUM/HIGH/ULTRA)
- **Network Analytics**: Theo dõi bandwidth, packet loss, jitter, FPS
- **Pre-buffering**: Đệm trước frames khi SETUP để phát mượt mà
- **End-of-Stream Detection**: Tự động phát hiện khi hết video

## 📁 Cấu trúc

```
├── Server.py              # Main server
├── ServerWorker.py        # Worker xử lý client
├── Client.py              # GUI client application
├── ClientLauncher.py      # Entry point cho client
├── RtpPacket.py          # RTP protocol implementation
├── VideoStream.py        # Video file parser
├── NetworkAnalyzer.py    # Network monitoring
├── AdaptiveController.py # Quality adaptation
└── sample_1920x1080.mjpeg # Video mẫu
```

## 🚀 Cách sử dụng

### 1. Chạy Server
```powershell
python Server.py 5000
```

### 2. Chạy Client
```powershell
python ClientLauncher.py localhost 5000 25000 sample_1920x1080.mjpeg
```

### 3. Thao tác
1. Click **Setup** → Buffering 20 frames
2. Đợi status "✓ Buffer ready"
3. Click **Play** → Video phát mượt mà
4. Click **Pause** → Tạm dừng
5. Click **Teardown** → Dừng và xem thống kê

## 📊 Statistics

Hệ thống theo dõi:
- **Bandwidth**: Mbps real-time
- **Frame Rate**: FPS thực tế
- **Packet Loss**: Tỷ lệ % mất gói
- **Jitter**: Độ dao động delay (ms)
- **Buffer Status**: Số frames trong buffer

## 🛠️ Yêu cầu

```
Python 3.7+
tkinter
Pillow
```

## 👨‍💻 Tác giả

Đồ án môn Mạng Máy Tính - HCMUT
