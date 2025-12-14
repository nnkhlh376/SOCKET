from tkinter import *
import tkinter.messagebox as tkMessageBox
from tkinter import ttk
from PIL import Image, ImageTk
import socket, threading, os, errno 
from RtpPacket import RtpPacket
import time 
from collections import deque
from NetworkAnalyzer import NetworkAnalyzer
from AdaptiveController import AdaptiveController

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT
    
    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        
        self.serverAddr = serveraddr
        self.serverPort = int(serverport) 
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.frameNbr = 0

        # --- For retransmission (NACK/RESEND) ---
        self.missing_seqs = set()
        self.frame_deadline = None
        self.FRAME_RESEND_TIMEOUT = 0.15   # 150ms đợi resend (tùy mạng)
        self.current_frame_frags = {}
        # Retransmission statistics
        self.resend_requests_sent = 0      # Số lần gửi RESEND request
        self.packets_retransmitted = 0     # Số packet được gửi lại thành công
        self.packets_recovered = 0         # Số packet cứu lại được sau retrans
        
        # Fragment reassembly
        self.current_frame_data = b''
        self.current_frame_ts = None      # timestamp của frame đang ghép
        self.expected_seq = None          # seq mong đợi tiếp theo trong frame
        self.frame_corrupted = False      # frame bị lỗi do mất gói/out-of-order
        self.last_timestamp = -1
        
        # Frame buffer for smooth playback
        self.frame_buffer = deque(maxlen=200)  # Buffer tối đa 200 frames
        self.buffer_target = 50  # Đệm 50 frames trước khi play (ổn định FPS từ đầu)
        self.buffering = False
        self.buffer_lock = threading.Lock()
        
        # Playback control
        self.playback_thread = None
        self.playback_active = False
        self.end_of_stream = False
        
        # Advanced features
        self.network_analyzer = NetworkAnalyzer()
        self.adaptive_controller = AdaptiveController(initial_quality='HIGH')
        
        # Performance tracking
        self.frame_receive_start = None
        self.frame_assembly_times = []
        # Socket error tracking
        self.socket_buffer_overflows = 0
        
        # Initialize RTSP socket to None before connection
        self.rtspSocket = None
        self.connectToServer()
        self.playEvent = threading.Event()
        self.playEvent.clear()

    def sendResendRequest(self, missing_ranges: str):
        """
        missing_ranges ví dụ: "1200-1210,1215,1220-1222"
        """
        try:
            # Chỉ gửi khi đã có socket và đã qua SETUP
            if not hasattr(self, "rtspSocket") or self.rtspSocket is None or self.state == self.INIT:
                return  # Chưa kết nối RTSP, bỏ qua
            self.rtspSeq += 1
            request = (
                f"RESEND {self.fileName} RTSP/1.0\n"
                f"CSeq: {self.rtspSeq}\n"
                f"Session: {self.sessionId}\n"
                f"Missing: {missing_ranges}\n"
            )
            self.rtspSocket.send(request.encode("utf-8"))
            self.resend_requests_sent += 1
            # print("Sent RESEND:", missing_ranges)
        except Exception as e:
            print("RESEND send error:", e)

    def seqs_to_ranges(self, seqs):
        seqs = sorted(seqs)
        if not seqs:
            return ""
        ranges = []
        start = prev = seqs[0]
        for s in seqs[1:]:
            if s == prev + 1:
                prev = s
            else:
                ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
                start = prev = s
        ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
        return ",".join(ranges)

    
    def createWidgets(self):
        """Build enhanced GUI với statistics panel"""
        self.master.rowconfigure(0, weight=1)  # Video row expands
        self.master.rowconfigure(1, weight=0)  # Button row fixed
        for i in range(4):
            self.master.columnconfigure(i, weight=1)

        # Control buttons
        self.setup = Button(self.master)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        
        self.start = Button(self.master)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        
        self.pause = Button(self.master)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=2, sticky="ew", padx=2, pady=2)
        
        self.teardown = Button(self.master)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] = self.exitClient
        self.teardown.grid(row=1, column=3, sticky="ew", padx=2, pady=2)
        
        # Video display
        self.label = Label(self.master, bg="black") 
        self.label.grid(row=0, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
        
        # Network stats panel
        self.stats_frame = LabelFrame(self.master, text="📊 Network Statistics", padx=10, pady=5)
        self.stats_frame.grid(row=2, column=0, columnspan=4, sticky=W+E, padx=5, pady=5)
    

        # Stats labels
        self.stats_labels = {}
        stats_items = [
            ('bandwidth', 'Bandwidth:'),
            ('fps', 'Frame Rate:'),
            ('quality', 'Quality:'),
            ('loss', 'Packet Loss:'),
            ('jitter', 'Jitter:'),
            ('frames', 'Frames:'),
            ('nack', 'NACK:'),
            ('retrans', 'Retransmissions:')
        ]
        
        for i, (key, text) in enumerate(stats_items):
            row = i // 2
            col = (i % 2) * 2
            
            Label(self.stats_frame, text=text, anchor=W, width=12).grid(
                row=row, column=col, sticky=W, padx=5, pady=2
            )
            self.stats_labels[key] = Label(
                self.stats_frame, text="--", anchor=W, width=20, fg="blue"
            )
            self.stats_labels[key].grid(row=row, column=col+1, sticky=W, padx=5, pady=2)
        
        # Status bar
        self.status_bar = Label(
            self.master, text="Sẵn sàng", anchor=W, bg="lightgray", relief=SUNKEN
        )
        self.status_bar.grid(row=3, column=0, columnspan=4, sticky=W+E, padx=5, pady=2)
        
        # Buffer status panel
        self.buffer_frame = LabelFrame(self.master, text="Buffer Status", padx=10, pady=5)
        self.buffer_frame.grid(row=4, column=0, columnspan=4, sticky=W+E, padx=5, pady=5)
        
        self.buffer_progress = ttk.Progressbar(
            self.buffer_frame, 
            mode='determinate', 
            maximum=100
        )
        self.buffer_progress.pack(fill=X, padx=5, pady=5)
        
        self.buffer_label = Label(self.buffer_frame, text="0/0 frames (0.0%)", fg="blue")
        self.buffer_label.pack()
    
    def setupMovie(self):
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)
            # Bắt đầu buffering ngay sau SETUP
            self.buffering = True
            self.updateStatus("Buffering frames...")
    
    def playMovie(self):
        if self.state == self.READY:
            # Kiểm tra buffer đủ chưa
            if len(self.frame_buffer) < self.buffer_target:
                tkMessageBox.showwarning(
                    'Buffer Not Ready', 
                    f'Buffering... {len(self.frame_buffer)}/{self.buffer_target} frames'
                )
                return
            
            # listenRtp đã chạy từ SETUP, không cần start lại
            
            # Start playback từ buffer
            self.playback_active = True
            self.playback_thread = threading.Thread(target=self.playFromBuffer, daemon=True)
            self.playback_thread.start()
            
            # Stats display
            threading.Thread(target=self.updateStatsDisplay, daemon=True).start()
            
            self.sendRtspRequest(self.PLAY)
    
    def pauseMovie(self):
        if self.state == self.PLAYING:
            # Stop playback thread
            self.playback_active = False
            if self.playback_thread:
                self.playback_thread.join(timeout=1.0)
            
            self.sendRtspRequest(self.PAUSE)
            self.updateStatus(f"⏸ Paused - Buffer: {len(self.frame_buffer)} frames")
    
    def exitClient(self):
        """Exit with statistics report"""
        # Stop playback
        self.playback_active = False
        
        # Print final statistics
        stats = self.network_analyzer.get_stats()
        print("\n" + "="*60)
        print("FINAL STATISTICS REPORT")
        print("="*60)
        print(f"Total Runtime:     {stats['runtime_sec']} seconds")
        print(f"Total Frames:      {self.frameNbr}")
        print(f"Total Data:        {stats['total_mb']} MB")
        print(f"Average Bandwidth: {stats['bandwidth_mbps']} Mbps")
        print(f"Average FPS:       {stats['frame_rate']} fps")
        print(f"Packet Loss:       {stats['loss_rate']}%")
        print(f"Late Packets:      {stats['late_packets']}")
        print(f"Duplicate Packets: {stats['duplicate_packets']}")
        print(f"Jitter:            {stats['jitter_ms']} ms")
        print(f"End of Stream:     {'Yes' if self.end_of_stream else 'No (user stopped)'}")
        print("="*60)
        
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()
        os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
    
    def listenRtp(self):
        """Enhanced RTP listener with retransmission (NACK/RESEND) support"""
        import time
        while True:
            try:
                data = self.rtpSocket.recv(20480)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)

                    curr_timestamp = rtpPacket.timestamp()
                    marker = rtpPacket.marker()
                    payload = rtpPacket.getPayload()
                    seq_num = rtpPacket.seqNum()

                    self.network_analyzer.record_packet(seq_num, len(data), curr_timestamp)

                    # --- Frame boundary logic ---
                    if not hasattr(self, 'current_frame_ts') or self.current_frame_ts is None:
                        self.current_frame_ts = curr_timestamp
                        self.expected_seq = seq_num
                        self.frame_marker_received = False
                        self.frame_deadline = None
                        self.missing_seqs = set()
                        self.current_frame_frags = {}
                        self.frame_receive_start = time.time()

                    # New frame (timestamp changed)
                    if curr_timestamp != self.current_frame_ts:
                        # Drop incomplete frame if marker not received
                        if not self.frame_marker_received and self.current_frame_frags:
                            self.updateStatus("⚠ Frame incomplete (timestamp jumped) -> drop")
                        # Reset for new frame
                        self.current_frame_ts = curr_timestamp
                        self.expected_seq = seq_num
                        self.frame_marker_received = False
                        self.frame_deadline = None
                        self.missing_seqs = set()
                        self.current_frame_frags = {}
                        self.frame_receive_start = time.time()

                    # --- RTP fragment reassembly ---
                    # Detect missing packets
                    if self.expected_seq is None:
                        self.expected_seq = seq_num

                    if seq_num == self.expected_seq:
                        self.expected_seq += 1
                    elif seq_num > self.expected_seq:
                        # Gap detected
                        missing = set(range(self.expected_seq, seq_num))
                        self.missing_seqs.update(missing)
                        # Send RESEND request
                        missing_ranges = self.seqs_to_ranges(self.missing_seqs)
                        if missing_ranges:
                            self.sendResendRequest(missing_ranges)
                        # Set deadline if not already set
                        if self.frame_deadline is None:
                            self.frame_deadline = time.time() + self.FRAME_RESEND_TIMEOUT
                        self.expected_seq = seq_num + 1
                    else:
                        # seq_num < expected_seq: out-of-order/duplicate
                        # Accept if it's a missing one
                        if seq_num in self.missing_seqs:
                            self.missing_seqs.remove(seq_num)
                            self.packets_retransmitted += 1  # Packet retransmitted successfully
                            self.packets_recovered += 1      # Successfully recovered
                        else:
                            continue

                    # Store fragment
                    self.current_frame_frags[seq_num] = payload

                    # If marker received, note it
                    if marker == 1:
                        self.frame_marker_received = True
                        # Set deadline if not already set
                        if self.frame_deadline is None and self.missing_seqs:
                            self.frame_deadline = time.time() + self.FRAME_RESEND_TIMEOUT

                    # Check if frame is complete (after every packet)
                    if self.frame_marker_received:
                        # Check if all missing packets have arrived
                        if not self.missing_seqs:
                            # Frame complete! Assemble it
                            assembled = b''.join(self.current_frame_frags[k] for k in sorted(self.current_frame_frags))
                            self.frameNbr += 1
                            if self.frame_receive_start:
                                assembly_time = time.time() - self.frame_receive_start
                                self.frame_assembly_times.append(assembly_time)
                            frame_info = {
                                'number': self.frameNbr,
                                'data': assembled,
                                'timestamp': curr_timestamp,
                                'size': len(assembled)
                            }
                            with self.buffer_lock:
                                self.frame_buffer.append(frame_info)
                            if self.buffering:
                                buffer_size = len(self.frame_buffer)
                                self.updateStatus(f"Buffering... {buffer_size}/{self.buffer_target} frames")
                                if buffer_size >= self.buffer_target:
                                    self.buffering = False
                                    self.updateStatus("Buffer ready - Press PLAY")
                            self.network_analyzer.record_frame()
                            stats = self.network_analyzer.get_stats()
                            adjustment = self.adaptive_controller.should_adjust(stats)
                            if adjustment:
                                self.adaptive_controller.adjust_quality(adjustment)
                                self.sendQualityUpdate()
                            # Reset for next frame
                            self.current_frame_ts = None
                            self.expected_seq = None
                            self.frame_marker_received = False
                            self.frame_deadline = None
                            self.missing_seqs = set()
                            self.current_frame_frags = {}
                            self.frame_receive_start = None
                            self.last_timestamp = curr_timestamp
                            continue
                        elif self.frame_deadline is not None and time.time() > self.frame_deadline:
                            # Timeout waiting for retransmission - discard frame
                            self.updateStatus(f"Frame timeout (still missing {len(self.missing_seqs)} packets)")
                            # Reset for next frame
                            self.current_frame_ts = None
                            self.expected_seq = None
                            self.frame_marker_received = False
                            self.frame_deadline = None
                            self.missing_seqs = set()
                            self.current_frame_frags = {}
                            self.frame_receive_start = None
                            self.last_timestamp = curr_timestamp
                            continue

                    self.last_timestamp = curr_timestamp
            except socket.timeout:
                if self.state == self.PLAYING:
                    with self.buffer_lock:
                        if len(self.frame_buffer) == 0 and self.playback_active:
                            pass
                continue
            except socket.error as e:
                import errno
                if hasattr(e, 'errno'):
                    if e.errno == errno.ENOBUFS or e.errno == errno.ENOMEM:
                        self.socket_buffer_overflows += 1
                        print(f"Socket Buffer Overflows: {self.socket_buffer_overflows}")
                        print("WARNING: Socket buffer overflow - packets dropped!")
                        print("Consider: reduce bitrate or increase SO_RCVBUF")
                    elif e.errno == errno.ECONNRESET:
                        print("Connection reset by peer")
                if self.playEvent.isSet():
                    break
                if self.teardownAcked == 1:
                    try:
                        self.rtpSocket.shutdown(socket.SHUT_RDWR)
                        self.rtpSocket.close()
                    except:
                        pass
                    break
            except Exception as e:
                # Catch-all cho các exceptions khác
                print(f"Unexpected error in listenRtp: {type(e).__name__}: {e}")
                if self.playEvent.isSet():
                    break
    
    def updateStatsDisplay(self):
        """Update statistics display every second"""
        while True:
            try:
                time.sleep(1)
                if self.state != self.PLAYING:
                    continue
                
                stats = self.network_analyzer.get_stats()
                quality = self.adaptive_controller.get_quality()
                
                # Update labels
                self.stats_labels['bandwidth'].config(
                    text=f"{stats['bandwidth_mbps']} Mbps"
                )
                self.stats_labels['fps'].config(
                    text=f"{stats['frame_rate']} fps"
                )
                self.stats_labels['quality'].config(
                    text=f"{quality} ({self.adaptive_controller.get_mtu()})"
                )
                
                # Calculate raw and effective loss
                raw_lost = stats.get('lost_packets', 0)
                raw_rate = stats.get('loss_rate', 0)
                effective_lost = max(0, raw_lost - getattr(self, "packets_recovered", 0))
                total_pkts = stats.get('total_packets', 0)
                
                if total_pkts > 0:
                    eff_rate = (effective_lost / total_pkts * 100)
                    loss_text = f"raw {raw_rate:.1f}% ({raw_lost}) | eff {eff_rate:.1f}% ({effective_lost})"
                else:
                    loss_text = f"raw {raw_rate:.1f}% ({raw_lost}) | eff ({effective_lost})"
                
                self.stats_labels['loss'].config(text=loss_text)
                
                self.stats_labels['jitter'].config(
                    text=f"{stats['jitter_ms']} ms"
                )
                self.stats_labels['frames'].config(
                    text=f"{self.frameNbr} ({stats['total_mb']} MB)"
                )
                
                # NACK requests sent
                self.stats_labels['nack'].config(
                    text=f"{self.resend_requests_sent} sent",
                    fg="orange" if self.resend_requests_sent > 0 else "blue"
                )
                
                # Retransmissions received
                self.stats_labels['retrans'].config(
                    text=f"{getattr(self, 'packets_recovered', 0)} recv",
                    fg="green" if getattr(self, 'packets_recovered', 0) > 0 else "blue"
                )
                
                # Update buffer display
                buffer_size = len(self.frame_buffer)
                buffer_percent = (buffer_size / self.frame_buffer.maxlen) * 100
                self.buffer_progress['value'] = buffer_percent
                self.buffer_label.config(
                    text=f"{buffer_size}/{self.frame_buffer.maxlen} frames ({buffer_percent:.1f}%)"
                )
                
            except Exception as e:
                break
    
    def playFromBuffer(self):
        """Playback thread - lấy frames từ buffer và hiển thị"""
        TARGET_FPS = 50
        FRAME_DURATION = 1.0 / TARGET_FPS  # 0.02 seconds
        empty_buffer_count = 0
        
        print("Starting playback from buffer...")
        
        while self.playback_active:
            try:
                frame_start = time.time()
                
                # Lấy frame từ buffer
                with self.buffer_lock:
                    if len(self.frame_buffer) == 0:
                        empty_buffer_count += 1
                        
                        # Nếu buffer trống quá lâu (5 giây) → Có thể hết video
                        if empty_buffer_count > 50:  # 50 * 0.1s = 5 giây
                            self.end_of_stream = True
                            self.updateStatus("✓ Video ended")
                            print("\nVIDEO ENDED - No more frames received")
                            tkMessageBox.showinfo(
                                'Video Ended', 
                                f'Video playback completed!\n\nTotal frames played: {self.frameNbr}'
                            )
                            self.playback_active = False
                            break
                        
                        # Buffer empty - đợi thêm
                        self.updateStatus("Buffer underrun - waiting...")
                        time.sleep(0.1)
                        continue
                    
                    empty_buffer_count = 0  # Reset counter
                    frame_info = self.frame_buffer.popleft()
                
                # Hiển thị frame
                try:
                    cache_file = self.writeFrame(frame_info['data'])
                    self.updateMovie(cache_file)
                    
                    # Update buffer status
                    buffer_level = len(self.frame_buffer)
                    if buffer_level < 10:
                        self.updateStatus(f"Buffer low: {buffer_level} frames")
                    elif buffer_level > 50:
                        self.updateStatus(f"Buffer healthy: {buffer_level} frames")
                    else:
                        self.updateStatus(f"Playing - Buffer: {buffer_level} frames")
                    
                except Exception as e:
                    print(f"Display error: {e}")
                
                # Frame rate control - chờ đủ thời gian cho frame tiếp theo
                elapsed = time.time() - frame_start
                sleep_time = max(0, FRAME_DURATION - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"Playback error: {e}")
                break
        
        print("Playback stopped")
    
    def sendQualityUpdate(self):
        """Gửi thông tin quality update cho server (tùy chọn)"""
        # Có thể implement RTSP DESCRIBE hoặc custom message
        pass
    
    def updateStatus(self, message):
        """Update status bar"""
        try:
            self.status_bar.config(text=message)
        except:
            pass
    
    def writeFrame(self, data):
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        with open(cachename, "wb") as file:
            file.write(data)
        return cachename
    
    def updateMovie(self, imageFile):
        try:
            photo = ImageTk.PhotoImage(Image.open(imageFile))
            self.label.configure(image=photo)
            self.label.image = photo
        except Exception as e:
            print(f"Update error: {e}")
    
    def connectToServer(self):
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
            self.updateStatus(f"Connected to {self.serverAddr}:{self.serverPort}")
        except Exception as e:
            tkMessageBox.showwarning('Connection Failed', f'Failed: {e}')
    
    def sendRtspRequest(self, requestCode):
        request = ""
        
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply, daemon=True).start()
            self.rtspSeq += 1
            request = f"SETUP {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nTransport: RTP/UDP; client_port={self.rtpPort}"
            self.requestSent = self.SETUP
        
        elif requestCode == self.PLAY and self.state == self.READY:
            self.rtspSeq += 1
            request = f"PLAY {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.PLAY
        
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            self.rtspSeq += 1
            request = f"PAUSE {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.PAUSE
        
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            self.rtspSeq += 1
            request = f"TEARDOWN {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.TEARDOWN
        else:
            return
        
        try:
            if self.rtspSocket is None:
                print("Send error: RTSP socket not connected")
                return
            self.rtspSocket.send(request.encode("utf-8"))
        except Exception as e:
            print(f"Send error: {e}")
    
    def recvRtspReply(self):
        while True:
            try:
                reply = self.rtspSocket.recv(1024)
                if reply:
                    self.parseRtspReply(reply.decode("utf-8"))
                if self.requestSent == self.TEARDOWN:
                    self.rtspSocket.shutdown(socket.SHUT_RDWR)
                    self.rtspSocket.close()
                    break
            except:
                break
    
    def parseRtspReply(self, data):
        try:
            lines = data.split('\n')
            seqNum = int(lines[1].split(' ')[1])
            
            if seqNum == self.rtspSeq:
                session = int(lines[2].split(' ')[1])
                
                if self.sessionId == 0:
                    self.sessionId = session
                
                if self.sessionId == session:
                    if int(lines[0].split(' ')[1]) == 200:
                        if self.requestSent == self.SETUP:
                            self.state = self.READY
                            self.openRtpPort()
                            # Bắt đầu lắng nghe RTP ngay để nhận pre-buffering frames
                            threading.Thread(target=self.listenRtp, daemon=True).start()
                            self.updateStatus("Ready to play")
                        elif self.requestSent == self.PLAY:
                            self.state = self.PLAYING
                            self.updateStatus("Playing...")
                        elif self.requestSent == self.PAUSE:
                            self.state = self.READY
                            self.playEvent.set()
                            self.updateStatus("Paused")
                        elif self.requestSent == self.TEARDOWN:
                            self.state = self.INIT
                            self.teardownAcked = 1
                            self.updateStatus("Stopped")
        except Exception as e:
            print(f"Parse error: {e}")
    
    def openRtpPort(self):
        try:
            self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.rtpSocket.settimeout(0.5)
            # Tăng socket receive buffer để tránh packet loss
            self.rtpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)  # 2 MB (thay vì mặc định ~64KB)
            self.rtpSocket.bind(('', self.rtpPort))
        except Exception as e:
            tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)
    
    def handler(self):
        self.pauseMovie()
        if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:
            self.playMovie()