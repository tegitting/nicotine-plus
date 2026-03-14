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
        # This makes it show up in the Plugins list
        self.register_command("start_heritage", self.start_loop)
        self.register_command("stop_heritage", self.stop_loop)
        self.log("Heritage Searcher Ready. Type /start_heritage in chat.")

    def start_loop(self, *args):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.search_loop, daemon=True)
            self.thread.start()
            return "Heritage Searcher: Started."
        return "Already running."

    def stop_loop(self, *args):
        self.running = False
        return "Heritage Searcher: Stopping..."

    def search_loop(self):
        while self.running:
            # Get your actual wishlist from the Nicotine core
            wishlist = self.core.wishlist.get_wishlist()
            if not wishlist:
                break

            item = random.choice(list(wishlist.keys()))
            self.core.search.search_request(item)
            
            # Randomized 'Human' delay for your M5
            time.sleep(random.randint(60, 180))

    def log(self, msg):
        print(f"[HeritageSearch] {msg}")
