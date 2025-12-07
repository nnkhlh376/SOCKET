EOI_MARKER = b'\xff\xd9'

class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0

	def nextFrame(self):
			"""
			Get next frame. 
			Modified to parse standard MJPEG files by finding the EOI marker (\xff\xd9).
			"""
			CHUNK_SIZE = 65536  
			frame_data = b''
			
			while True:
				# bắt đầu find
				current_pos = self.file.tell()
				
				# tìm end
				chunk = self.file.read(CHUNK_SIZE)
				
				if not chunk:
					if frame_data:
						self.frameNum += 1
						return frame_data
					return None 

				eoi_index_in_chunk = chunk.find(EOI_MARKER)
				
				if eoi_index_in_chunk != -1:
					# nếu end: trích xuất frame và cập nhật con trỏ
					frame_end_index = eoi_index_in_chunk + len(EOI_MARKER) 
					frame_data += chunk[:frame_end_index]
					
					# Đặt lại con trỏ về vị trí bắt đầu frame tiếp theo
					self.file.seek(current_pos + frame_end_index)
					
					self.frameNum += 1
					return frame_data
				else:
					# Nếu ko thấy end: Thêm toàn bộ chunk vào frame và tiếp tục đọc
					frame_data += chunk

	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	
	def close(self):
		"""Đóng file khi xong."""
		if self.file:
			self.file.close()
			self.file = None