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
        print("[Wishlist Searcher] --- Plugin Enabled ---")
        # Start the loop: wait 10 seconds for initial connection, then every 60s
        self.loop_id = GLib.timeout_add_seconds(60, self.force_search_loop)

    def force_search_loop(self):
        if not self.plugin_running:
            return False

        # Get the 'autosearch' list that wants2wishes.py updates
        try:
            wishlist = self.core.config.get("search", "autosearch")
        except Exception as e:
            print(f"[Wishlist Searcher] Config Error: {e}")
            return True

        if wishlist and isinstance(wishlist, list):
            print(f"[Wishlist Searcher] Manual override: Triggering {len(wishlist)} searches...")
            for query in wishlist:
                if not self.plugin_running: 
                    break
                
                # wants2wishes writes strings directly, so 'query' is the artist - title
                print(f"[Wishlist Searcher] Forcing search for: {query}")
                try:
                    self.core.search.search(query)
                    # Spreading searches out by 2 seconds to be safe on macOS Tahoe
                    time.sleep(2) 
                except Exception as e:
                    print(f"[Wishlist Searcher] Search failed: {e}")
        else:
            print("[Wishlist Searcher] Autosearch list is empty or not found.")
            
        return True 

    def stop(self):
        self.plugin_running = False
        print("[Wishlist Searcher] --- Plugin Disabled ---")
        if self.loop_id:
            GLib.source_remove(self.loop_id)
            self.loop_id = None
