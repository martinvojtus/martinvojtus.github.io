import requests
import concurrent.futures

class VBSXClient:
    def __init__(self, base_url="https://mv-backend-ak8l.onrender.com"):
        self.base_url = base_url

    def fetch_interval_score(self, asset, mode, interval):
        try:
            payload = {"asset": asset, "mode": mode, "interval": interval}
            response = requests.post(f"{self.base_url}/analyze", json=payload, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return data.get("cycle_score", 50.0)
            return 50.0
        except Exception as e:
            print(f"Error fetching {interval}: {e}")
            return 50.0

    def get_mtf_scores(self, asset="BTC"):
        """Fetches scores for 1d, 4h, 2h, 1h in parallel."""
        intervals = ["1d", "4h", "2h", "1h"]
        scores = {}
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_interval = {executor.submit(self.fetch_interval_score, asset, "TRADING", i): i for i in intervals}
            for future in concurrent.futures.as_completed(future_to_interval):
                interval = future_to_interval[future]
                scores[interval] = future.result()
        
        return scores
