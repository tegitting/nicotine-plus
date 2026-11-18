# SPDX-FileCopyrightText: 2026 tegitting
# SPDX-FileCopyrightText: 2020-2026 Nicotine+ Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""GateKeeper: check the shares of users who queue uploads.

Lives in its own plugin folder (instead of editing leech_detector) so that
upstream Nicotine+ updates never conflict with it.

Share sizes, including how much of a share is private/locked, are computed
from the user's shared file list directly, so no changes to Nicotine+ core
files are needed.
"""

import time

from pynicotine.events import events
from pynicotine.pluginsystem import BasePlugin
from pynicotine.utils import human_size

MIB_IN_BYTES = 1024 ** 2
GIB_IN_BYTES = 1024 ** 3
AUTO_MESSAGE_PREFIX = "[Auto-Message] "


class Plugin(BasePlugin):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.settings = {
            "skip_buddies": True,
            "open_private_chat": False,
            "auto_open_browse": True,
            "keep_browse_open": True,
            "browse_delay_seconds": 2,
            "probe_cooldown_seconds": 30,
            "cancel_on_timeout": True,
            "timeout_seconds": 25,

            "no_files_ban": True,
            "no_files_pm": True,
            "no_files_message": "You need shared files to download from me",

            "all_privates_ban": True,
            "all_privates_pm": True,
            "all_privates_message": "You cannot download from me when your files are all private",

            "empty_folders_ban": True,
            "empty_folders_pm": True,
            "empty_folders_message": "You cannot download from me when your shared folders are empty",

            "min_public_percent": 80,
            "min_public_gib": 50,
            "size_ratio_ban": True,
            "size_ratio_pm": True,
            "size_ratio_message": ("Your public share is too small or too much is locked/private. "
                                   "Please share more openly."),

            "num_files": 10,
            "num_files_ban": False,
            "num_files_pm": False,
            "num_files_message": "Please consider adding more shared files",

            "num_folders": 10,
            "num_folders_ban": False,
            "num_folders_pm": False,
            "num_folders_message": "Please consider having more shared folders",

            "share_size": 10,
            "share_size_unit": "GB",
            "share_size_ban": False,
            "share_size_pm": False,
            "share_size_message": "You are not sharing enough media",
        }

        def check_group(group, ban_desc, pm_desc):
            return {
                f"{group}_ban": {"description": ban_desc, "type": "bool", "group": group_names[group]},
                f"{group}_pm": {"description": pm_desc, "type": "bool", "group": group_names[group]},
                f"{group}_message": {"description": "Message:", "type": "string", "group": group_names[group]},
            }

        group_names = {
            "no_files": "No Shares",
            "empty_folders": "Empty Folders",
            "all_privates": "All Private",
            "size_ratio": "Public Share Size",
            "num_files": "File Count",
            "num_folders": "Folder Count",
            "share_size": "Total Share Size",
        }

        self.metasettings = {
            "skip_buddies": {
                "description": "Never check buddies", "type": "bool", "group": "General"},
            "open_private_chat": {
                "description": "Open private chat tabs when sending messages", "type": "bool", "group": "General"},
            "auto_open_browse": {
                "description": "Open the user's Browse tab when they queue", "type": "bool", "group": "General"},
            "keep_browse_open": {
                "description": "Switch to the Browse tab when it opens", "type": "bool", "group": "General"},
            "browse_delay_seconds": {
                "description": "Delay (seconds) before opening the Browse tab:",
                "type": "int", "minimum": 0, "maximum": 10, "group": "General"},
            "probe_cooldown_seconds": {
                "description": "Seconds before the same user can be checked again:",
                "type": "int", "minimum": 0, "group": "General"},
            "cancel_on_timeout": {
                "description": "Cancel a user's uploads if their shares never arrive", "type": "bool",
                "group": "General"},
            "timeout_seconds": {
                "description": "Seconds to wait for a user's shares:",
                "type": "int", "minimum": 5, "maximum": 300, "group": "General"},

            **check_group("no_files", "Ban users sharing nothing", "Message users sharing nothing"),
            **check_group("empty_folders", "Ban users with only empty folders",
                          "Message users with only empty folders"),
            **check_group("all_privates", "Ban users whose shares are all private",
                          "Message users whose shares are all private"),

            "min_public_percent": {
                "description": "Minimum % of total share that must be public (70-90 recommended):",
                "type": "int", "minimum": 0, "maximum": 100, "group": group_names["size_ratio"]},
            "min_public_gib": {
                "description": "Minimum public share size in GiB (0 = disabled):",
                "type": "int", "minimum": 0, "group": group_names["size_ratio"]},
            **check_group("size_ratio", "Ban users who fail the public share check",
                          "Message users who fail the public share check"),

            "num_files": {
                "description": "Minimum number of shared files:", "type": "int", "minimum": 0,
                "group": group_names["num_files"]},
            **check_group("num_files", "Ban users below the file minimum", "Message users below the file minimum"),

            "num_folders": {
                "description": "Minimum number of shared folders:", "type": "int", "minimum": 0,
                "group": group_names["num_folders"]},
            **check_group("num_folders", "Ban users below the folder minimum",
                          "Message users below the folder minimum"),

            "share_size": {
                "description": "Minimum total share size:", "type": "int", "minimum": 0, "maximum": 100000,
                "group": group_names["share_size"]},
            "share_size_unit": {
                "description": "Unit:", "type": "dropdown", "options": ("MB", "GB"),
                "group": group_names["share_size"]},
            **check_group("share_size", "Ban users below the size minimum", "Message users below the size minimum"),
        }

        self.probed_users = {}      # username -> time the check started
        self.timeout_events = {}    # username -> scheduler event id
        self.passed_users = set()   # users who passed this session
        self.last_checked = {}      # username -> time of last check (for the cooldown)
        self.browse_events = set()

    # Plugin lifecycle #

    def init(self):
        events.connect("shared-file-list-response", self._shared_file_list_response)

    def loaded_notification(self):
        self.log("Loaded. Public share check: at least %s%% public and %s GiB",
                 (self.settings["min_public_percent"], self.settings["min_public_gib"]))

    def disable(self):

        events.disconnect("shared-file-list-response", self._shared_file_list_response)

        for event_id in list(self.timeout_events.values()) + list(self.browse_events):
            events.cancel_scheduled(event_id)

        self.timeout_events.clear()
        self.browse_events.clear()
        self.probed_users.clear()

    # Probing #

    def upload_queued_notification(self, user, virtual_path, real_path):

        if user in self.passed_users:
            return

        if self.settings["skip_buddies"] and user in self.core.buddies.users:
            return

        if user in self.probed_users:
            # Already waiting for this user's shares
            return

        now = time.monotonic()
        last_check = self.last_checked.get(user, float("-inf"))

        if now - last_check < self.settings["probe_cooldown_seconds"]:
            return

        self.probed_users[user] = now
        self.last_checked[user] = now

        if self.settings["auto_open_browse"]:
            delay = self.settings["browse_delay_seconds"]

            if delay > 0:
                event_id = events.schedule(delay=delay, callback=self._open_browse, callback_args=(user,))
                self.browse_events.add(event_id)
            else:
                self._open_browse(user)
        else:
            self.core.userbrowse.request_user_shares(user)

        if self.settings["cancel_on_timeout"]:
            self.timeout_events[user] = events.schedule(
                delay=self.settings["timeout_seconds"], callback=self._check_timeout, callback_args=(user, now))

    def _open_browse(self, user):

        # new_request=True makes sure fresh shares are requested, even if the
        # user's Browse tab was already open
        self.core.userbrowse.browse_user(
            user, new_request=True, switch_page=self.settings["keep_browse_open"])

    def _check_timeout(self, user, request_time):

        self.timeout_events.pop(user, None)

        if self.probed_users.get(user) != request_time:
            return

        del self.probed_users[user]
        self.log("No shares received from %s in time, cancelling their uploads", user)
        self._cancel_uploads(user)

    def _cancel_uploads(self, user):

        uploads = {
            transfer: None for transfer in self.core.uploads.transfers.values() if transfer.username == user
        }

        if uploads:
            self.core.uploads.abort_uploads(uploads, denied_message="Cancelled")
            self.log("Cancelled %s upload(s) from %s", (len(uploads), user))

    # Checking #

    def _shared_file_list_response(self, msg):

        user = msg.username

        if user not in self.probed_users:
            return

        del self.probed_users[user]
        event_id = self.timeout_events.pop(user, None)

        if event_id is not None:
            events.cancel_scheduled(event_id)

        public_files = public_bytes = 0
        private_files = private_bytes = 0

        for _folder_path, files in msg.public_folders:
            public_files += len(files)
            public_bytes += sum(file_data.size for file_data in files)

        for _folder_path, files in msg.private_folders:
            private_files += len(files)
            private_bytes += sum(file_data.size for file_data in files)

        num_public_dirs = len(msg.public_folders)
        num_private_dirs = len(msg.private_folders)
        dirs = num_public_dirs + num_private_dirs
        files = public_files + private_files
        total_bytes = public_bytes + private_bytes
        public_percent = (public_bytes / total_bytes * 100) if total_bytes else 0.0

        self.log("%s: %s files in %s folders (%s private) | Public: %s (%.1f%%) | Private: %s",
                 (user, f"{files:,}", f"{dirs:,}", f"{num_private_dirs:,}",
                  human_size(public_bytes), public_percent, human_size(private_bytes)))

        reason = self._find_failure(files, dirs, num_private_dirs, total_bytes, public_bytes, public_percent)

        if reason is None:
            self.passed_users.add(user)
            self.log("%s passed", user)
            return

        self._handle_leech(user, reason)

    def _find_failure(self, files, dirs, num_private_dirs, total_bytes, public_bytes, public_percent):
        """Return the name of the first failed check, or None if the user passes."""

        settings = self.settings

        if files == 0:
            return "empty_folders" if dirs > 0 else "no_files"

        if dirs > 0 and num_private_dirs == dirs:
            return "all_privates"

        min_public_bytes = settings["min_public_gib"] * GIB_IN_BYTES

        if public_percent < settings["min_public_percent"] or public_bytes < min_public_bytes:
            return "size_ratio"

        if files < settings["num_files"]:
            return "num_files"

        if dirs < settings["num_folders"]:
            return "num_folders"

        unit_bytes = MIB_IN_BYTES if settings["share_size_unit"] == "MB" else GIB_IN_BYTES

        if total_bytes < settings["share_size"] * unit_bytes:
            return "share_size"

        return None

    def _handle_leech(self, user, reason):

        should_ban = self.settings[f"{reason}_ban"]
        should_message = self.settings[f"{reason}_pm"]

        if not should_ban and not should_message:
            self.log("%s failed check '%s' (no action enabled for this check)", (user, reason))
            return

        # Message first, so the user can still receive it before the ban
        if should_message:
            self._send_message(user, self.settings[f"{reason}_message"])

        if should_ban:
            # Banning also cancels the user's queued uploads
            self.core.network_filter.ban_user(user)
            self.log("Banned %s (failed check '%s')", (user, reason))

    def _send_message(self, user, message):

        if not message:
            return

        self.send_private(user, AUTO_MESSAGE_PREFIX + message,
                          show_ui=self.settings["open_private_chat"], switch_page=False)
        self.log("Messaged %s: %s", (user, message))
