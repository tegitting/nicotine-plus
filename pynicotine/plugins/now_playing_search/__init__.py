from pynicotine.pluginsystem import BasePlugin
from gi.repository import GLib

class Plugin(BasePlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_id = None

    def init(self):
        # The CORRECT hook Nicotine+ calls when enabled
        self.log("--- [DEBUG] Reloop Runner Active! ---")
        # Trigger the loop every 60 seconds
        self.loop_id = GLib.timeout_add_seconds(60, self.force_search_loop)

    def force_search_loop(self):
        if not self.enabled:
            return False

        # Read the LIVE wishlist from Nicotine's memory (handles Discogs sync better)
        wishlist_items = list(getattr(self.core.wishlist, 'wishlist', {}).keys())
        
        if wishlist_items:
            self.log(f"Manual override: Searching {len(wishlist_items)} items...")
            for query in wishlist_items:
                try:
                    # Native 3.4.dev search command
                    self.core.search.search(query)
                except AttributeError:
                    # Fallback for older 3.x versions
                    self.core.search.search_request(query)
        else:
            self.log("Wishlist empty - loop skipping.")
            
        return True # Keep the loop running

    def stop(self):
        # The CORRECT hook Nicotine+ calls when disabled
        self.log("--- [DEBUG] Reloop Runner Stopped! ---")
        if self.loop_id:
            GLib.source_remove(self.loop_id)
            self.loop_id = None
