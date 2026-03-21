import random
import time
import threading
from pynicotine.pluginsystem import BasePlugin

class HeritageSearch(BasePlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = False
        self.thread = None

    def init(self):
        # Adds a manual command to start/stop the loop in the chat bar
        self.register_command("start_heritage", self.start_loop)
        self.register_command("stop_heritage", self.stop_loop)
        self.log("Heritage Searcher loaded. Type /start_heritage to begin.")

    def start_loop(self, *args):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.search_loop, daemon=True)
            self.thread.start()
            return "Wishlist Searcher: Started."
        return "Already running."

    def stop_loop(self, *args):
        self.running = False
        return "Wishlist Searcher: Stopping after current task..."

    def search_loop(self):
        while self.running:
            # Get your current wishlist items
            wishlist = self.core.wishlist.get_wishlist()
            if not wishlist:
                self.log("Wishlist is empty. Stopping.")
                break

            # Pick a random item or iterate (we'll pick a random one to be "human-like")
            item = random.choice(list(wishlist.keys()))
            
            self.log(f"Searching for: {item}")
            self.core.search.search_request(item)

            # --- THE SAFE TIMER ---
            # Wait between 45 and 120 seconds (highly recommended for 2k lists)
            delay = random.randint(45, 120)
            self.log(f"Sleeping for {delay} seconds...")
            
            for _ in range(delay):
                if not self.running: break
                time.sleep(1)

    def log(self, msg):
        print(f"[WishlistSearch] {msg}")
