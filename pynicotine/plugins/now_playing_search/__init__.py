import random
import time
import threading
from pynicotine.pluginsystem import BasePlugin

metadata = {
    "name": "Wishlist Searcher", # This changes the UI name
    "description": "Automatically scans wishlist items for your DVS collection.",
    "author": "JD",
    "version": "2.0",
}

class WishlistSearcher(BasePlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = False

    def init(self):
        """Called when plugin is enabled."""
        self.running = True
        # Using a daemon thread so it doesn't hang Nicotine+ on exit
        self.thread = threading.Thread(target=self.search_loop, daemon=True)
        self.thread.start()
        self.log("Wishlist Searcher: **Active** and monitoring.")

    def search_loop(self):
        # 15s delay to let the app finish connecting to Soulseek
        time.sleep(15) 
        
        while self.running:
            try:
                # 3.4.dev uses .core.wishlist.wishlist as a dictionary
                wishlist = getattr(self.core.wishlist, 'wishlist', {})
                items = list(wishlist.keys())

                if items:
                    target = random.choice(items)
                    self.log(f"Auto-searching for: {target}")
                    self.core.search.search_request(target)
                else:
                    self.log("Wishlist empty. Waiting 10 minutes...")

            except Exception as e:
                self.log(f"Loop error: {str(e)}")

            # Wait 8 to 15 minutes to stay under the radar
            wait = random.randint(480, 900)
            time.sleep(wait)

    def stop(self):
        """Called when plugin is disabled."""
        self.running = False
        self.log("Wishlist Searcher: **Stopped**.")

    def log(self, msg):
        # This will show up in your Nicotine+ logs
        print(f"[WishlistSearcher] {msg}")

Plugin = WishlistSearcher
