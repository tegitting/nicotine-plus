from pynicotine.pluginsystem import BasePlugin
from gi.repository import GLib
import random

class Plugin(BasePlugin):

    # Simple preset system
    settings = {
        "frequency": "medium"          # default
    }

    metasettings = {
        "frequency": {
            "type": "option",
            "options": ["fast", "medium", "slow"],
            "label": "Search frequency (lower = more spaced out / safer from bot detection)"
        }
    }

    # Internal ranges (you can tweak these if you ever want)
    RANGES = {
        "fast":   (20,  60),   # more frequent
        "medium": (45, 120),   # balanced
        "slow":   (90, 300)    # very spaced out (recommended for long sessions)
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_id = None
        self.plugin_running = False
        self.current_index = 0
        self.connected = False

    def init(self):
        self.plugin_running = True
        self.current_index = 0

        # Safe initial connection check
        try:
            self.connected = bool(getattr(getattr(self.core, "networkserver", None), "connected", False))
        except Exception:
            self.connected = False

        freq = self.settings["frequency"]
        min_d, max_d = self.RANGES[freq]

        self.log("--- Wishlist Plugin Enabled (1 search per cycle) ---")
        self.log(f"Frequency: {freq.upper()} → {min_d}–{max_d} seconds (randomised)")
        self.log(f"Initial status: {'CONNECTED ✓' if self.connected else 'OFFLINE — waiting'}")

        initial_delay = random.uniform(5, 15)
        self.log(f"Starting in ~{initial_delay:.1f} seconds")
        self.loop_id = GLib.timeout_add_seconds(int(initial_delay), self.search_next)

    def server_connect_notification(self):
        self.connected = True
        self.log("Connected — searches active")

    def server_disconnect_notification(self, userchoice):
        self.connected = False
        self.log("Disconnected — searches paused")

    def search_next(self):
        if not self.plugin_running:
            return False

        if not self.connected:
            self.log("Not connected — skipping cycle")
            self._reschedule()
            return False

        try:
            wishlist = self.config.sections["server"]["autosearch"]
        except Exception as e:
            self.log(f"Cannot read autosearch list: {e}")
            self._reschedule()
            return False

        if not isinstance(wishlist, list) or len(wishlist) == 0:
            self.log("Wishlist is empty.")
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

        freq = self.settings["frequency"]
        min_d, max_d = self.RANGES[freq]
        delay = random.uniform(min_d, max_d)

        self.log(f"Next search in ~{delay:.0f} s (frequency: {freq})")
        self.loop_id = GLib.timeout_add_seconds(int(delay), self.search_next)

    def disable(self):
        self.plugin_running = False
        self.log("--- Wishlist Plugin Disabled ---")
        if self.loop_id is not None:
            GLib.source_remove(self.loop_id)
            self.loop_id = None
