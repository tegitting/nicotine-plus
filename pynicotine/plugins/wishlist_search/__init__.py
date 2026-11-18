# SPDX-FileCopyrightText: 2026 tegitting
# SPDX-License-Identifier: GPL-3.0-or-later

"""Wishlist Search: search wishlist items more often than the server's
wishlist interval, one item per cycle, with a randomised delay.

Lives in its own plugin folder (instead of editing now_playing_search) so that
upstream Nicotine+ updates never conflict with it.

Searches go through Nicotine+'s own wishlist machinery, so results land in the
matching wishlist item (with its filters and ignored users), items with
auto-search turned off are skipped, and no new search tabs or search history
entries are created.
"""

import random

from pynicotine.events import events
from pynicotine.pluginsystem import BasePlugin
from pynicotine.slskmessages import UserStatus


class Plugin(BasePlugin):

    RANGES = {
        "fast": (20, 60),
        "medium": (45, 120),
        "slow": (90, 300)
    }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.settings = {
            "frequency": "medium"
        }
        self.metasettings = {
            "frequency": {
                "description": "Search frequency (slower = more spaced out, safer from flood detection):",
                "type": "dropdown",
                "options": ("fast", "medium", "slow")
            }
        }

        self.timer_id = None

    def init(self):
        self._schedule_next(delay=random.uniform(5, 15))

    def loaded_notification(self):

        min_delay, max_delay = self._get_range()
        self.log("Searching one wishlist item every %s-%s seconds (%s)",
                 (min_delay, max_delay, self.settings["frequency"]))

    def disable(self):

        if self.timer_id is not None:
            events.cancel_scheduled(self.timer_id)
            self.timer_id = None

    def server_connect_notification(self):
        self.log("Connected, wishlist searches resumed")

    def server_disconnect_notification(self, userchoice):
        self.log("Disconnected, wishlist searches paused until reconnect")

    def _get_range(self):
        return self.RANGES.get(self.settings["frequency"], self.RANGES["medium"])

    def _schedule_next(self, delay=None):

        if delay is None:
            delay = random.uniform(*self._get_range())

        # events.schedule() runs the callback on the main thread
        self.timer_id = events.schedule(delay=max(1, int(delay)), callback=self._search_next)

    def _search_next(self):

        self.timer_id = None

        try:
            if self.core.users.login_status == UserStatus.OFFLINE:
                return

            search = self.core.search

            if not any(item.auto_search for item in search.wishlist.values()):
                return

            # Same call Nicotine+ makes on its own wishlist timer: it rotates
            # through items with auto-search enabled, one per call
            search._do_next_wishlist_search()  # pylint: disable=protected-access

        except Exception as error:
            self.log("Wishlist search failed: %s", error)

        finally:
            self._schedule_next()
