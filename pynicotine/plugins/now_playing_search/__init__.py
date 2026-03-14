from pynicotine.pluginsystem import BasePlugin
from gi.repository import GLib

class Plugin(BasePlugin):
    metadata = {
        "name": "Reloop Wishlist Runner", # Unique name for verification
        "desc": "Forces wishlist searches every 60 seconds",
        "authors": ["Gemini"],
        "version": "2.2",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_id = None

    def plugin_enabled(self):
        # Using a 2-second delay to ensure the server connection is stable
        self.log("--- [DEBUG] Reloop Runner Active! ---")
        self.loop_id = GLib.timeout_add_seconds(60, self.force_search_loop)

    def force_search_loop(self):
        if not self.enabled:
            return False

        wishlist = self.core.config.get_sections_list("wishlist")
        if wishlist:
            self.log(f"Manual override: Searching {len(wishlist)} items...")
            for item in wishlist:
                # item[0] is the search term
                self.core.search.search(item[0])
        else:
            self.log("Wishlist empty - loop skipping.")
            
        return True # Keep the loop running

    def plugin_disabled(self):
        if self.loop_id:
            GLib.source_remove(self.loop_id)
            self.loop_id = None
