class VBSXStrategy:
    def __init__(self, ema_period=12):
        self.ema_period = ema_period
        self.ema_value = None
        self.k = 2 / (ema_period + 1)
        self.history = []

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
        if len(self.history) < 2: return None
        
        prev_ema = self.history[-2]
        curr_ema = self.history[-1]

        # 1. DCA IN (BUY/LONG Hook): Prev was low (<20) and now increasing
        if prev_ema < 20 and curr_ema > prev_ema:
            return "BUY"
            
        # 2. DCA OUT (SELL/SHORT Hook): Prev was high (>80) and now decreasing
        if prev_ema > 80 and curr_ema < prev_ema:
            return "SELL"
            
        return None
