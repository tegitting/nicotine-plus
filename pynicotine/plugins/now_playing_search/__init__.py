import random
import time
import threading
from pynicotine.pluginsystem import BasePlugin

# This metadata dictionary tells Nicotine+ exactly what to call the plugin
metadata = {
    "name": "Wishlist Searcher",
    "description": "Automatically searches for random items from your wishlist at safe intervals.",
    "version": "1.0",
}

class WishlistSearcher(BasePlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = False
        self.thread = None

    def init(self):
        # Commands for the chat bar
        self.register_command("start_wishlist", self.start_loop)
        self.register_command("stop_wishlist", self.stop_loop)
        self.log("Wishlist Searcher Ready. Type /start_wishlist to begin.")

    def start_loop(self, *args):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.search_loop, daemon=True)
            self.thread.start()
            return "Wishlist Searcher: **Online** and scouting."
        return "Already running."

    def stop_loop(self, *args):
        self.running = False
        return "Wishlist Searcher: **Offline**."

    def search_loop(self):
        while self.running:
            wishlist = self.core.wishlist.get_wishlist()
            if not wishlist:
                self.log("Wishlist is empty. Stopping.")
                self.running = False
                break

            item = random.choice(list(wishlist.keys()))
            self.log(f"Searching for: {item}")
            self.core.search.search_request(item)
            
            # 60 to 180 seconds to keep your soulseek account safe
            delay = random.randint(60, 180)
            time.sleep(delay)

    def log(self, msg):
        print(f"[WishlistSearcher] {msg}")

# Tells Nicotine+ which class to load
Plugin = WishlistSearcher
