from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket
import time
import math

class ServerWorker:
    SETUP = 'SETUP'
    PLAY = 'PLAY'
    PAUSE = 'PAUSE'
    TEARDOWN = 'TEARDOWN'
    
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    OK_200 = 0
    FILE_NOT_FOUND_404 = 1
    CON_ERR_500 = 2
    

    def __init__(self, clientInfo):
        self.clientInfo = clientInfo
        self.seq = 1000

        # RTP packet cache for retransmission (NACK/RESEND)
        from collections import OrderedDict
        import threading
        import time
        self.rtp_cache = OrderedDict()      # key: seq, value: (packet_bytes, timestamp)
        self.rtp_cache_lock = threading.Lock()
        self.RTP_CACHE_MAX = 8000           # ~ vài nghìn packets là ổn (tuỳ RAM)
        self.RTP_CACHE_TTL = 2.0            # chỉ giữ ~2 giây gần nhất để resend

        # Packet loss simulation (for testing retransmission)
        self.SIMULATE_PACKET_LOSS = True    # Bật/tắt giả lập loss
        self.PACKET_LOSS_RATE = 0.05        # 5% packet loss (thay đổi tùy ý)
        self.packets_dropped = 0            # Đếm số packet bị drop

        
        # Statistics
        self.frames_sent = 0
        self.packets_sent = 0
        self.bytes_sent = 0
        self.start_time = None
        
    def run(self):
        threading.Thread(target=self.recvRtspRequest, daemon=True).start()
    
    def recvRtspRequest(self):
        """Receive RTSP requests from client"""
        connSocket = self.clientInfo['rtspSocket'][0]
        while True:
            try:
                data = connSocket.recv(4096)
                if data:
                    print("Received:\n" + data.decode("utf-8"))
                    self.processRtspRequest(data.decode("utf-8"))
            except Exception as e:
                print(f"Receive error: {e}")
                break
    
    def processRtspRequest(self, data):
        """Process RTSP request"""
        try:
            request = data.split('\n')
            line1 = request[0].split(' ')
            requestType = line1[0]
            filename = line1[1]
            seq = request[1].split(' ')
            
            if requestType == self.SETUP:
                if self.state == self.INIT:
                    print("Processing SETUP")
                    try:
                        self.clientInfo['videoStream'] = VideoStream(filename)
                        self.state = self.READY
                        
                        # Tạo UDP socket ngay cho pre-buffering
                        self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        
                    except IOError:
                        self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
                        return
                    # Generate a randomized RTSP session ID
                    self.clientInfo['session'] = randint(100000, 999999)
                    # Send RTSP reply
                    self.replyRtsp(self.OK_200, seq[1])
                    # Get the RTP/UDP port from the last line
                    self.clientInfo['rtpPort'] = request[2].split('=')[1]
                    
                    # Bắt đầu pre-buffering ngay
                    self.clientInfo['prebuffer_event'] = threading.Event()
                    self.clientInfo['prebuffer_event'].clear()
                    threading.Thread(
                        target=self.prebufferFrames, 
                        daemon=True
                    ).start()
            
            elif requestType == self.PLAY:
                if self.state == self.READY:
                    print("processing PLAY\n")
                    self.state = self.PLAYING
                    self.start_time = time.time()
                    
                    # Dừng pre-buffering thread
                    if 'prebuffer_event' in self.clientInfo:
                        self.clientInfo['prebuffer_event'].set()
                    
                    # RTP socket đã tạo từ SETUP
                    self.replyRtsp(self.OK_200, seq[1])
                    
                    self.clientInfo['event'] = threading.Event()
                    self.clientInfo['worker'] = threading.Thread(
                        target=self.sendRtp, 
                        daemon=True
                    )
                    self.clientInfo['worker'].start()
            
            elif requestType == self.PAUSE:
                if self.state == self.PLAYING:
                    print("processing PAUSE\n")
                    self.state = self.READY
                    self.clientInfo['event'].set()
                    self.replyRtsp(self.OK_200, seq[1])
                    self.printStatistics()
            

            elif requestType == "RESEND":
                # tìm dòng "Missing:"
                missing_line = None
                for line in request:
                    if line.startswith("Missing:"):
                        missing_line = line
                        break
                if not missing_line:
                    return

                missing_spec = missing_line.split(":", 1)[1].strip()

                def expand(spec: str):
                    out = []
                    for part in spec.split(","):
                        part = part.strip()
                        if not part:
                            continue
                        if "-" in part:
                            a, b = part.split("-", 1)
                            a, b = int(a), int(b)
                            out.extend(range(a, b + 1))
                        else:
                            out.append(int(part))
                    return out

                missing_seqs = expand(missing_spec)

                address = self.clientInfo['rtspSocket'][1][0]
                port = int(self.clientInfo['rtpPort'])

                resent = 0
                with self.rtp_cache_lock:
                    for s in missing_seqs:
                        if s in self.rtp_cache:
                            pkt, _ = self.rtp_cache[s]
                            self.clientInfo['rtpSocket'].sendto(pkt, (address, port))
                            resent += 1

                print(f"RESEND: requested={len(missing_seqs)} resent={resent}")

            # ...existing code...
            elif requestType == self.TEARDOWN:
                print("processing TEARDOWN\n")
                self.clientInfo['event'].set()
                self.replyRtsp(self.OK_200, seq[1])
                self.printStatistics()
                
                # Cleanup
                if 'videoStream' in self.clientInfo:
                    self.clientInfo['videoStream'].close()
                if 'rtpSocket' in self.clientInfo:
                    self.clientInfo['rtpSocket'].close()

        except Exception as e:
            print(f"✗ Process error: {e}")
            traceback.print_exc()
    
    def prebufferFrames(self):
        """Gửi frames để client buffer trước khi PLAY"""
        PREBUFFER_COUNT = 60  # Gửi 60 frames (tương ứng với buffer_target 50 + dự phòng)
        
        print(f"Pre-buffering {PREBUFFER_COUNT} frames...")
        
        for i in range(PREBUFFER_COUNT):
            # Check if PLAY received
            if self.clientInfo['prebuffer_event'].isSet():
                print("PLAY received, stopping pre-buffer")
                return
            
            data = self.clientInfo['videoStream'].nextFrame()
            if not data:
                print("End of video during pre-buffer")
                break
            
            frameNumber = self.clientInfo['videoStream'].frameNbr()
            
            try:
                address = self.clientInfo['rtspSocket'][1][0]
                port = int(self.clientInfo['rtpPort'])
                
                self.splitAndSendFrame(data, frameNumber, address, port)
                
                # Gửi nhanh để fill buffer nhanh (0.01s = 100 FPS tạm thời)
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Pre-buffer error: {e}")
                break
        
        print(f"Pre-buffering complete: {i+1} frames sent")
    
    def sendRtp(self):
        
        frame_times = []
        last_report_time = time.time()
        
        while True:
            frame_start = time.time()
            
            # Check for pause/stop
            if self.clientInfo['event'].isSet():
                print("Stopping RTP stream")
                break
            
            # Get next frame
            data = self.clientInfo['videoStream'].nextFrame()
            
            if not data:
                print("End of video")
                print(f"\n🎬 VIDEO STREAM ENDED")
                print(f"Total frames sent: {self.frames_sent}")
                print(f"Total packets sent: {self.packets_sent}")
                self.printStatistics()
                break
            
            frameNumber = self.clientInfo['videoStream'].frameNbr()
            
            try:
                address = self.clientInfo['rtspSocket'][1][0]
                port = int(self.clientInfo['rtpPort'])
                
                # Split and send frame with current MTU
                packets_in_frame = self.splitAndSendFrame(
                    data, frameNumber, address, port
                )
                
                self.frames_sent += 1
                self.bytes_sent += len(data)
                
                # Log large frames
                if len(data) > 100000:  # > 100KB
                    print(f"Large frame #{frameNumber}: {len(data)/1024:.1f} KB → {packets_in_frame} packets")
                
            except Exception as e:
                print(f"Send error: {e}")
                break
            
            # Frame rate control
            frame_elapsed = time.time() - frame_start
            frame_times.append(frame_elapsed)
            
            time.sleep(0.02)  # Server: 50 FPS sending rate, Client: 25 FPS playback (2:1 ratio)
            
            # Periodic stats report
            if time.time() - last_report_time > 10.0:  # Every 10 seconds
                self.printPeriodicStats(frame_times)
                frame_times = []
                last_report_time = time.time()
    
    def splitAndSendFrame(self, data, frameNumber, address, port):
        MTU = 1450
        packets_count = math.ceil(len(data) / MTU)

        for i in range(packets_count):
            offset = i * MTU
            chunk = data[offset:offset + MTU]

            self.seq += 1
            marker = 1 if (offset + MTU >= len(data)) else 0

            # Create RTP packet
            packet = self.makeRtp(chunk, self.seq, marker)

            # --- RTP cache logic ---
            now = time.time()
            with self.rtp_cache_lock:
                self.rtp_cache[self.seq] = (packet, now)
                # Remove expired packets (TTL)
                while self.rtp_cache and (now - next(iter(self.rtp_cache.values()))[1] > self.RTP_CACHE_TTL):
                    self.rtp_cache.popitem(last=False)
                # Limit max cache size
                while len(self.rtp_cache) > self.RTP_CACHE_MAX:
                    self.rtp_cache.popitem(last=False)

            # --- Simulate packet loss (for testing retransmission) ---
            if self.SIMULATE_PACKET_LOSS:
                from random import random
                if random() < self.PACKET_LOSS_RATE:
                    self.packets_dropped += 1
                    # Skip sending this packet (simulated loss)
                    continue

            # Send packet
            self.clientInfo['rtpSocket'].sendto(packet, (address, port))
            self.packets_sent += 1

        return packets_count
    
    def makeRtp(self, payload, frameNbr, marker):
        """Create RTP packet"""
        version = 2
        padding = 0
        extension = 0
        cc = 0
        pt = 26  # MJPEG
        seqnum = frameNbr
        ssrc = 0
        
        rtpPacket = RtpPacket()
        rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
        return rtpPacket.getPacket()
    
    def printPeriodicStats(self, frame_times):
        """Print periodic statistics"""
        if not frame_times:
            return
        
        avg_frame_time = sum(frame_times) / len(frame_times)
        actual_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
        
        runtime = time.time() - self.start_time if self.start_time else 0
        avg_bitrate = (self.bytes_sent * 8) / (runtime * 1_000_000) if runtime > 0 else 0
        
        print(f"\nPeriodic Stats (last 10s):")
        print(f"   Frames sent: {len(frame_times)}")
        print(f"   Avg frame time: {avg_frame_time*1000:.1f} ms")
        print(f"   Actual FPS: {actual_fps:.1f}")
    
    def printStatistics(self):
        """Print final statistics"""
        runtime = time.time() - self.start_time if self.start_time else 0
        
        if runtime == 0:
            return
        
        avg_bitrate = (self.bytes_sent * 8) / (runtime * 1_000_000)
        avg_fps = self.frames_sent / runtime
        avg_packets_per_frame = self.packets_sent / self.frames_sent if self.frames_sent > 0 else 0
        
        print("\n" + "="*60)
        print("SERVER STATISTICS")
        print("="*60)
        print(f"Runtime:              {runtime:.1f} seconds")
        print(f"Frames sent:          {self.frames_sent}")
        print(f"Packets sent:         {self.packets_sent}")
        print(f"Packets dropped:      {self.packets_dropped} (simulated loss: {self.PACKET_LOSS_RATE*100:.1f}%)")
        print(f"Total data:           {self.bytes_sent/(1024*1024):.2f} MB")
        print(f"Average bitrate:      {avg_bitrate:.2f} Mbps")
        print(f"Average FPS:          {avg_fps:.1f}")
        print(f"Packets per frame:    {avg_packets_per_frame:.1f}")
        print("="*60 + "\n")
    
    def replyRtsp(self, code, seq):
        """Send RTSP reply"""
        if code == self.OK_200:
            reply = f'RTSP/1.0 200 OK\nCSeq: {seq}\nSession: {self.clientInfo["session"]}'
            connSocket = self.clientInfo['rtspSocket'][0]
            connSocket.send(reply.encode())
        elif code == self.FILE_NOT_FOUND_404:
            print("404 FILE NOT FOUND")
        elif code == self.CON_ERR_500:
            print("500 CONNECTION ERROR")