from pynicotine.pluginsystem import BasePlugin
from gi.repository import GLib
import time

class Plugin(BasePlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_id = None
        self.plugin_running = False

    def init(self):
        self.plugin_running = True
        self.log("--- Plugin Enabled ---")
        # Start the loop (first run after 10s so we're connected, then every 60s)
        self.loop_id = GLib.timeout_add_seconds(10, self.force_search_loop)

    def force_search_loop(self):
        if not self.plugin_running:
            return False

        # Correct config access (autosearch lives under [server])
        try:
            wishlist = self.config.sections["server"]["autosearch"]
        except Exception as e:
            self.log(f"Config Error: {e}")
            return True

        if wishlist and isinstance(wishlist, list):
            self.log(f"Manual override: Triggering {len(wishlist)} searches...")
            for query in wishlist:
                if not self.plugin_running:
                    break

                self.log(f"Forcing search for: {query}")
                try:
                    # Correct search call - use "global" or "wishlist" depending on what you want
                    self.core.search.do_search(query, mode="global")
                    # Optional: tiny non-blocking delay if you really need it
                    # GLib.timeout_add(2000, lambda: None)  # but usually not needed
                except Exception as e:
                    self.log(f"Search failed: {e}")
        else:
            self.log("Autosearch list is empty or not found.")

        return True

    def disable(self):  # <-- renamed from stop
        self.plugin_running = False
        self.log("--- Plugin Disabled ---")
        if self.loop_id:
            GLib.source_remove(self.loop_id)
            self.loop_id = None
