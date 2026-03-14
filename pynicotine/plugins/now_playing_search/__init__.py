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
        self.log("--- Sequential Now Playing Searcher Enabled (1 search per cycle) ---")
        initial_delay = random.uniform(5, 15)
        self.log(f"Starting in ~{initial_delay:.1f} seconds")
        self.loop_id = GLib.timeout_add_seconds(int(initial_delay), self.search_next)

    def search_next(self):
        if not self.plugin_running:
            return False

        try:
            wishlist = self.config.sections["server"]["autosearch"]
        except Exception as e:
            self.log(f"Cannot read autosearch list: {e}")
            self._reschedule()
            return False

        if not isinstance(wishlist, list) or len(wishlist) == 0:
            self.log("Wishlist/autosearch is empty.")
            self._reschedule()
            return False

        total = len(wishlist)
        idx = self.current_index % total
        query = wishlist[idx]
        position = f"{idx + 1}/{total}"

        self.log(f"[{position}] Searching: {query}")

        try:
            self.core.search.do_search(query, mode="global")
        except Exception as e:
            self.log(f"  └─ Failed: {e}")

        self.current_index += 1
        self._reschedule()
        return False

    def _reschedule(self):
        if not self.plugin_running:
            return

        # delay = random.uniform(45, 120)   # wider range alternative
        delay = random.uniform(30, 90)
        self.log(f"Next in ~{delay:.0f} s")
        self.loop_id = GLib.timeout_add_seconds(int(delay), self.search_next)

    def disable(self):
        self.plugin_running = False
        self.log("--- Sequential Searcher Disabled ---")
        if self.loop_id is not None:
            GLib.source_remove(self.loop_id)
            self.loop_id = None
