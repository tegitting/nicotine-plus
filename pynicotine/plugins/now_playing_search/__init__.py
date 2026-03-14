from pynicotine.pluginsystem import BasePlugin
from gi.repository import GLib

class Plugin(BasePlugin):
    metadata = {
        "name": "Force Wishlist Searcher",
        "desc": "Bypasses the 12-minute wait and searches immediately",
        "version": "2.1",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_id = None

    def plugin_enabled(self):
        self.log("--- Plugin Force-Enabled! ---")
        # Using GLib for modern GTK4 compatibility
        self.loop_id = GLib.timeout_add(5000, self.force_search_loop)

    def force_search_loop(self):
        if not self.enabled:
            return False

        wishlist = self.core.config.get_sections_list("wishlist")
        if not wishlist:
            self.log("Wishlist is empty. Nothing to search.")
            return True 

        self.log(f"Triggering search for {len(wishlist)} items...")
        for item in wishlist:
            query = item[0]
            self.log(f"Searching for: {query}")
            self.core.search.search(query)

        return True # Repeats every 2 mins (default)

    def plugin_disabled(self):
        self.log("Plugin Disabled. Stopping loop.")
        if self.loop_id:
            GLib.source_remove(self.loop_id)
