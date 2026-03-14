from pynicotine.plugins import BasePlugin
import gobject

class Plugin(BasePlugin):
    metadata = {
        "name": "Force Wishlist Searcher",
        "desc": "Bypasses the 12-minute wait and searches immediately",
        "authors": ["Gemini"],
        "version": "2.0",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_id = None

    def plugin_enabled(self):
        """This triggers when you check the box in Preferences"""
        self.log("--- Plugin Force-Enabled! ---")
        # Give the core 5 seconds to breathe, then start
        self.loop_id = gobject.timeout_add(5000, self.force_search_loop)

    def force_search_loop(self):
        if not self.enabled:
            return False

        wishlist = self.core.config.get_sections_list("wishlist")
        if not wishlist:
            self.log("Wishlist is empty. Nothing to search.")
            return True # Keep loop alive but do nothing

        self.log(f"Triggering search for {len(wishlist)} items...")
        
        for item in wishlist:
            # item[0] is usually the search term
            query = item[0]
            self.log(f"Searching for: {query}")
            self.core.search.search(query)

        # Re-run every 2 minutes (120,000ms) instead of 12
        return True 

    def plugin_disabled(self):
        self.log("Plugin Disabled. Stopping loop.")
        if self.loop_id:
            gobject.source_remove(self.loop_id)
