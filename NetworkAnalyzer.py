import time
from collections import deque
import statistics

class NetworkAnalyzer:
    
    def __init__(self, window_size=100):
        self.window_size = window_size
        
        # Buffers để tính toán thống kê
        self.packet_times = deque(maxlen=window_size)
        self.packet_sizes = deque(maxlen=window_size)
        self.frame_times = deque(maxlen=50)
        self.jitter_buffer = deque(maxlen=window_size)
        
        # Counters
        self.total_packets = 0
        self.total_bytes = 0
        self.lost_packets = 0
        self.late_packets = 0
        self.duplicate_packets = 0
        
        # Sequence tracking
        self.expected_seq = None
        self.last_seq = -1
        self.seq_history = set()
        
        # Timing
        self.last_packet_time = None
        self.start_time = time.time()
        
    def record_packet(self, seq_num, packet_size, timestamp=None):
        """Ghi nhận packet nhận được"""
        current_time = time.time()
        
        if timestamp is None:
            timestamp = current_time
        
        self.total_packets += 1
        self.total_bytes += packet_size
        
        # Detect loss
        if self.expected_seq is not None:
            if seq_num > self.expected_seq:
                lost = seq_num - self.expected_seq
                self.lost_packets += lost
                print(f"Mất {lost} packets (seq {self.expected_seq} -> {seq_num})")
            elif seq_num < self.expected_seq:
                # Duplicate hoặc out-of-order
                if seq_num in self.seq_history:
                    self.duplicate_packets += 1
                    print(f"⚠ Duplicate packet: seq {seq_num}")
                else:
                    self.late_packets += 1
                    print(f"⚠ Late packet: seq {seq_num}")
        
        self.expected_seq = seq_num + 1
        self.last_seq = seq_num
        self.seq_history.add(seq_num)
        
        # Record timing
        self.packet_times.append(current_time)
        self.packet_sizes.append(packet_size)
        
        # Calculate jitter
        if self.last_packet_time is not None:
            inter_arrival = current_time - self.last_packet_time
            self.jitter_buffer.append(inter_arrival)
        
        self.last_packet_time = current_time
    
    def record_frame(self):
        """Ghi nhận frame hoàn chỉnh"""
        self.frame_times.append(time.time())
    
    def get_bandwidth(self):
        """Tính bandwidth hiện tại (Mbps)"""
        if len(self.packet_times) < 2:
            return 0.0
        
        time_window = self.packet_times[-1] - self.packet_times[0]
        if time_window == 0:
            return 0.0
        
        bytes_in_window = sum(self.packet_sizes)
        bandwidth_mbps = (bytes_in_window * 8) / (time_window * 1_000_000)
        return bandwidth_mbps
    
    def get_packet_rate(self):
        """Tính packet rate (packets/sec)"""
        if len(self.packet_times) < 2:
            return 0.0
        
        time_window = self.packet_times[-1] - self.packet_times[0]
        if time_window == 0:
            return 0.0
        
        return len(self.packet_times) / time_window
    
    def get_frame_rate(self):
        """Tính frame rate (FPS)"""
        if len(self.frame_times) < 2:
            return 0.0
        
        time_window = self.frame_times[-1] - self.frame_times[0]
        if time_window == 0:
            return 0.0
        
        return len(self.frame_times) / time_window
    
    def get_jitter(self):
        """Tính jitter (ms) - độ biến thiên delay"""
        if len(self.jitter_buffer) < 2:
            return 0.0
        
        try:
            jitter_ms = statistics.stdev(self.jitter_buffer) * 1000
            return jitter_ms
        except:
            return 0.0
    
    def get_loss_rate(self):
        """Tính tỷ lệ mất gói (%)"""
        total = self.total_packets + self.lost_packets
        if total == 0:
            return 0.0
        return (self.lost_packets / total) * 100
    
    def get_stats(self):
        """Lấy tất cả thống kê"""
        runtime = time.time() - self.start_time
        
        return {
            'bandwidth_mbps': round(self.get_bandwidth(), 2),
            'packet_rate': round(self.get_packet_rate(), 1),
            'frame_rate': round(self.get_frame_rate(), 1),
            'jitter_ms': round(self.get_jitter(), 2),
            'loss_rate': round(self.get_loss_rate(), 2),
            'total_packets': self.total_packets,
            'lost_packets': self.lost_packets,
            'late_packets': self.late_packets,
            'duplicate_packets': self.duplicate_packets,
            'total_mb': round(self.total_bytes / (1024 * 1024), 2),
            'runtime_sec': round(runtime, 1)
        }