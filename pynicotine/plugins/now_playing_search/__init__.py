from pynicotine.pluginsystem import BasePlugin
from gi.repository import GLib
import random

class Plugin(BasePlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_id = None
        self.plugin_running = False
        self.current_index = 0 

    def init(self):
        self.plugin_running = True
        self.current_index = 0
        self.log("--- Now Playing Wishlist Searcher Enabled (one search per cycle) ---")
        # First search after a short random delay so you see it working quickly
        initial_delay = random.uniform(5, 15)
        self.log(f"First search scheduled in ~{initial_delay:.1f} seconds")
        self.loop_id = GLib.timeout_add_seconds(int(initial_delay), self.search_next)

    def search_next(self):
        if not self.plugin_running:
            return False

        try:
            wishlist = self.config.sections["server"]["autosearch"]
        except Exception as e:
            self.log(f"Config Error: {e}")
            self._reschedule()
            return False

        if not wishlist or not isinstance(wishlist, list) or len(wishlist) == 0:
            self.log("Autosearch list is empty — nothing to search.")
            self._reschedule()
            return False

        # Pick the current one (modulo to loop around)
        query = wishlist[self.current_index % len(wishlist)]
        self.log(f"→ Searching: {query}")

        try:
            self.core.search.do_search(query, mode="global")
        except Exception as e:
            self.log(f"Search failed for '{query}': {e}")

        # Move to next item for the following cycle
        self.current_index += 1

        # Always schedule the next one
        self._reschedule()
        return False  # Don't auto-repeat

    def _reschedule(self):
        if not self.plugin_running:
            return

        delay = random.uniform(30, 90)
        minutes = delay / 60
        self.log(f"Next search scheduled in ~{delay:.0f} seconds (~{minutes:.1f} min)")
        self.loop_id = GLib.timeout_add_seconds(int(delay), self.search_next)

    def disable(self):
        self.plugin_running = False
        self.log("--- Now Playing Wishlist Searcher Disabled ---")
        if self.loop_id:
            GLib.source_remove(self.loop_id)
            self.loop_id = None
