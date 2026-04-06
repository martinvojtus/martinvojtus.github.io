class VBSXStrategy:
    def __init__(self, ema_period=5):
        self.ema_period = ema_period
        self.ema_value = None
        self.k = 2 / (ema_period + 1)
        self.history = []
        self.raw_history = []

    def calculate_weighted_score(self, scores):
        """
        Weights: 1d (40%), 4h (30%), 2h (20%), 1h (10%)
        """
        w1d = scores.get("1d", 50.0) * 0.4
        w4h = scores.get("4h", 50.0) * 0.3
        w2h = scores.get("2h", 50.0) * 0.2
        w1h = scores.get("1h", 50.0) * 0.1
        return round(w1d + w4h + w2h + w1h, 2)

    def update_ema(self, new_score):
        # Save raw score for emergency signals
        self.raw_history.append(new_score)
        if len(self.raw_history) > 50: self.raw_history.pop(0)

        # Update EMA
        if self.ema_value is None:
            self.ema_value = new_score
        else:
            self.ema_value = (new_score * self.k) + (self.ema_value * (1 - self.k))
        
        self.ema_value = round(self.ema_value, 2)
        self.history.append(self.ema_value)
        if len(self.history) > 50: self.history.pop(0)
        return self.ema_value

    def check_hook(self):
        """
        Checks for the 'Hook' (reversal) after burnout.
        Returns: 'BUY', 'SELL', or None
        """
        if len(self.history) < 2 or len(self.raw_history) < 2: return None
        
        # 1. EMERGENCY SIGNALS (Raw Score Spikes)
        prev_raw = self.raw_history[-2]
        curr_raw = self.raw_history[-1]
        
        if prev_raw >= 95 and curr_raw < prev_raw:
            return "SELL" # Emergency SHORT
            
        if prev_raw <= 5 and curr_raw > prev_raw:
            return "BUY" # Emergency LONG

        # 2. STANDARD SWING SIGNALS (EMA 5 Hook)
        prev_ema = self.history[-2]
        curr_ema = self.history[-1]

        # DCA IN (BUY/LONG Hook): Prev was low (<20) and now increasing
        if prev_ema < 20 and curr_ema > prev_ema:
            return "BUY"
            
        # DCA OUT (SELL/SHORT Hook): Prev was high (>80) and now decreasing
        if prev_ema > 80 and curr_ema < prev_ema:
            return "SELL"
            
        return None
