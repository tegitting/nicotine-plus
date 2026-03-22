from pynicotine.pluginsystem import BasePlugin
from gi.repository import GLib
import random

class Plugin(BasePlugin):

    settings = {
        "min_delay": 30,
        "max_delay": 90
    }

    metasettings = {
        "min_delay": {
            "type": "int",
            "min": 10,
            "max": 600,
            "label": "Minimum delay between searches (seconds)"
        },
        "max_delay": {
            "type": "int",
            "min": 10,
            "max": 600,
            "label": "Maximum delay between searches (seconds)"
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_id = None
        self.plugin_running = False
        self.current_index = 0
        self.connected = False   # ← connection flag

    def init(self):
        self.plugin_running = True
        self.current_index = 0

        # Safe initial connection check
        try:
            self.connected = bool(getattr(getattr(self.core, "networkserver", None), "connected", False))
        except Exception:
            self.connected = False

        self.log("--- Searcher Enabled (1 search per cycle) ---")
        self.log(f"Current range: {self.settings['min_delay']}–{self.settings['max_delay']} seconds")
        self.log(f"Initial status: {'CONNECTED ✓' if self.connected else 'OFFLINE — waiting for connection'}")

        initial_delay = random.uniform(5, 15)
        self.log(f"Starting in ~{initial_delay:.1f} seconds")
        self.loop_id = GLib.timeout_add_seconds(int(initial_delay), self.search_next)

    def server_connect_notification(self):
        self.connected = True
        self.log("Connected to Soulseek — searches enabled")

    def server_disconnect_notification(self, userchoice):
        self.connected = False
        self.log("Disconnected from Soulseek — searches paused until reconnect")

    def search_next(self):
        if not self.plugin_running:
            return False

        if not self.connected:
            self.log("Not connected — skipping this cycle")
            self._reschedule()
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

        min_d = min(self.settings["min_delay"], self.settings["max_delay"])
        max_d = max(self.settings["min_delay"], self.settings["max_delay"])
        delay = random.uniform(min_d, max_d)

        self.log(f"Next in ~{delay:.0f} s (range: {min_d}–{max_d})")
        self.loop_id = GLib.timeout_add_seconds(int(delay), self.search_next)

    def disable(self):
        self.plugin_running = False
        self.log("--- Wishlist Plugin Disabled ---")
        if self.loop_id is not None:
            GLib.source_remove(self.loop_id)
            self.loop_id = None
