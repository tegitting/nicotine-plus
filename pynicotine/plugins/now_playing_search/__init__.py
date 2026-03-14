from pynicotine.pluginsystem import BasePlugin
from gi.repository import GLib

class Plugin(BasePlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_id = None
        # Our custom switch
        self.plugin_running = False 

    def init(self):
        # Flip the switch to ON
        self.plugin_running = True
        self.log("--- [DEBUG] Reloop Runner Active! ---")
        # Trigger the loop every 60 seconds
        self.loop_id = GLib.timeout_add_seconds(60, self.force_search_loop)

    def force_search_loop(self):
        # Check our custom switch instead of 'self.enabled'
        if not self.plugin_running:
            return False

        wishlist_items = list(getattr(self.core.wishlist, 'wishlist', {}).keys())
        
        if wishlist_items:
            self.log(f"Manual override: Searching {len(wishlist_items)} items...")
            for query in wishlist_items:
                try:
                    self.core.search.search(query)
                except AttributeError:
                    self.core.search.search_request(query)
        else:
            self.log("Wishlist empty - loop skipping.")
            
        return True # Keep the loop running

    def stop(self):
        # Flip the switch to OFF
        self.plugin_running = False
        self.log("--- [DEBUG] Reloop Runner Stopped! ---")
        if self.loop_id:
            GLib.source_remove(self.loop_id)
            self.loop_id = None
