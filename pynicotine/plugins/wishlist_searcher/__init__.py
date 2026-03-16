from pynicotine.pluginsystem import BasePlugin
from gi.repository import GLib
import random

class Plugin(BasePlugin):

    __settings__ = {
        # Nicotine+ auto-creates UI elements from this dict in 3.2+ / 3.3+
        # Key = setting name, Value = default + optional metadata
        "base_delay": 180.0,           # default 3 minutes
        "jitter_percent": 50.0,        # ±50% randomization → e.g. 90–270 s around 180
        "min_delay": 60.0,             # hard floor to avoid too aggressive
    }

    # Optional: human-readable labels and ranges (Nicotine+ uses these if present)
    __metasettings__ = {
        "base_delay": {
            "description": "Base delay between searches (seconds)",
            "type": "float",
            "minimum": 30.0,
            "maximum": 1800.0,         # up to 30 min
            "step": 30.0,
            "digits": 0,               # show as whole seconds
        },
        "jitter_percent": {
            "description": "Randomization range (±%)",
            "type": "float",
            "minimum": 10.0,
            "maximum": 100.0,
            "step": 5.0,
            "digits": 0,
        },
        "min_delay": {
            "description": "Minimum allowed delay (seconds)",
            "type": "float",
            "minimum": 30.0,
            "maximum": 600.0,
            "step": 15.0,
            "digits": 0,
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_id = None
        self.plugin_running = False
        self.current_index = 0

    def init(self):
        self.plugin_running = True
        self.current_index = 0
        self.log("--- Sequential Now Playing Searcher Enabled ---")
        self.log(f"Base delay: {self.settings['base_delay']:.0f}s ±{self.settings['jitter_percent']}%")
        
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

        base = self.settings["base_delay"]
        jitter_pct = self.settings["jitter_percent"] / 100.0
        min_d = self.settings["min_delay"]

        # Randomized delay: base * (1 ± jitter)
        multiplier = random.uniform(1 - jitter_pct, 1 + jitter_pct)
        delay = base * multiplier
        delay = max(min_d, delay)  # enforce minimum

        self.log(f"Next search in ~{delay:.0f} seconds")
        self.loop_id = GLib.timeout_add_seconds(int(delay), self.search_next)

    def disable(self):
        self.plugin_running = False
        self.log("--- Sequential Searcher Disabled ---")
        if self.loop_id is not None:
            GLib.source_remove(self.loop_id)
            self.loop_id = None