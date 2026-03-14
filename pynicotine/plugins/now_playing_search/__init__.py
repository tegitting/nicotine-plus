import random
import time
import threading
from pynicotine.pluginsystem import BasePlugin

metadata = {
    "name": "Wishlist Searcher",
    "description": "Automatically searches for wishlist items at safe intervals.",
    "author": "JD",
    "version": "1.2",
}

class WishlistSearcher(BasePlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = False
        self.thread = None

    def init(self):
        # Universal registration for Nicotine+ 3.x and 3.4.dev
        cmd_name = "wishlist_start"
        callback = self.start_loop
        
        try:
            # Method 1: Modern Dev Build (core.command_handler)
            if hasattr(self.core, 'command_handler'):
                self.core.command_handler.register_command(cmd_name, callback)
            # Method 2: Stable 3.x (core.commands)
            elif hasattr(self.core, 'commands'):
                self.core.commands.register_command(cmd_name, callback)
            # Method 3: Plugin Base (BasePlugin legacy)
            else:
                self.register_command(cmd_name, callback)
            
            self.log("Successfully registered /wishlist_start")
        except Exception as e:
            self.log(f"Registration failed: {str(e)}")

    def start_loop(self, *args):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.search_loop, daemon=True)
            self.thread.start()
            return "Wishlist Searcher: **Online**."
        return "Already running."

    def search_loop(self):
        while self.running:
            wishlist = self.core.wishlist.get_wishlist()
            if not wishlist:
                self.log("Wishlist is empty.")
                self.running = False
                break

            item = random.choice(list(wishlist.keys()))
            self.log(f"Auto-searching: {item}")
            self.core.search.search_request(item)
            
            # Wait 90-180 seconds (Safety delay for Soulseek)
            time.sleep(random.randint(90, 180))

    def log(self, msg):
        print(f"[WishlistSearcher] {msg}")

Plugin = WishlistSearcher
