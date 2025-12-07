import time

class AdaptiveController:
    """Điều khiển quality dựa trên network conditions"""
    
    QUALITY_LEVELS = {
        'LOW': 800,      
        'MEDIUM': 1200,  
        'HIGH': 1400,    
        'ULTRA': 1450   
    }
    
    def __init__(self, initial_quality='MEDIUM'):
        self.current_quality = initial_quality
        self.mtu = self.QUALITY_LEVELS[initial_quality]
        
        # Thresholds
        self.loss_threshold_up = 1.0    # < 1% loss -> increase quality
        self.loss_threshold_down = 5.0  # > 5% loss -> decrease quality
        self.jitter_threshold = 50.0    # > 50ms jitter -> decrease
        
        # History
        self.adjustment_history = []
        self.last_adjustment_time = time.time()
        self.min_adjustment_interval = 5.0  # 5 seconds
    
    def should_adjust(self, stats):
        """Kiểm tra có nên điều chỉnh quality không"""
        # Chỉ adjust sau một khoảng thời gian
        if time.time() - self.last_adjustment_time < self.min_adjustment_interval:
            return None
        
        loss_rate = stats['loss_rate']
        jitter = stats['jitter_ms']
        
        # Decrease quality nếu network kém
        if loss_rate > self.loss_threshold_down or jitter > self.jitter_threshold:
            return 'DECREASE'
        
        # Increase quality nếu network tốt
        if loss_rate < self.loss_threshold_up and jitter < self.jitter_threshold / 2:
            return 'INCREASE'
        
        return None
    
    def adjust_quality(self, direction):
        """Điều chỉnh quality level"""
        levels = list(self.QUALITY_LEVELS.keys())
        current_index = levels.index(self.current_quality)
        
        if direction == 'INCREASE' and current_index < len(levels) - 1:
            self.current_quality = levels[current_index + 1]
            self.mtu = self.QUALITY_LEVELS[self.current_quality]
            self.last_adjustment_time = time.time()
            self.adjustment_history.append((time.time(), 'UP', self.current_quality))
            print(f"Tăng quality lên {self.current_quality} (MTU={self.mtu})")
            return True
            
        elif direction == 'DECREASE' and current_index > 0:
            self.current_quality = levels[current_index - 1]
            self.mtu = self.QUALITY_LEVELS[self.current_quality]
            self.last_adjustment_time = time.time()
            self.adjustment_history.append((time.time(), 'DOWN', self.current_quality))
            print(f"Giảm quality xuống {self.current_quality} (MTU={self.mtu})")
            return True
        
        return False
    
    def get_mtu(self):
        """Lấy MTU hiện tại"""
        return self.mtu
    
    def get_quality(self):
        """Lấy quality level hiện tại"""
        return self.current_quality