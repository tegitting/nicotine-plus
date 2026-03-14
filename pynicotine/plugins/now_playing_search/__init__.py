from pynicotine.pluginsystem import BasePlugin
import time

# This metadata ensures it shows up as "Wishlist Searcher" in your settings
metadata = {
    "name": "Wishlist Searcher",
    "description": "Scans your wishlist and triggers searches automatically.",
    "author": "JD",
    "version": "1.1",
}

class WishlistSearcher(BasePlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = None

    def init(self):
        """Initialize the plugin and register the chat command."""
        # In Nicotine+ 3.3+, commands are registered via self.core.commands
        try:
            self.core.commands.register_command(
                "wishlist_start", 
                self.start_loop, 
                "Usage: /wishlist_start - Starts the automatic wishlist search loop"
            )
            self.log("Plugin initialized. Type /wishlist_start in any chat to begin.")
        except AttributeError:
            self.log("Critical Error: Could not find command registration system.")

    def start_loop(self, *args):
        """Starts the background search process."""
        self.log("Starting wishlist search loop...")
        
        # Get the wishlist items
        wishlist_items = self.core.wishlist.get_wishlist()
        
        if not wishlist_items:
            self.log("Wishlist is empty. Add items first!")
            return

        for item in wishlist_items:
            # item is usually the search string
            self.log(f"Searching for: {item}")
            self.core.search.search(item)
            
            # Sleep for 5 seconds between searches to avoid Soulseek spam filters
            time.sleep(5)
            
        self.log("Finished scanning wishlist.")

    def stop(self):
        """Clean up when plugin is disabled."""
        self.log("Wishlist Searcher disabled.")

# Crucial: This line tells Nicotine+ which class to load
Plugin = WishlistSearcher
