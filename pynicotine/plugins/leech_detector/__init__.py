# COPYRIGHT (C) 2020-2024 Nicotine+ Contributors
# COPYRIGHT (C) 2011 quinox <quinox@users.sf.net>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# ...

from pynicotine.pluginsystem import BasePlugin
from pynicotine.utils import human_size
from dataclasses import dataclass

# Define constants
KB_IN_BYTES = 1024
MB_IN_BYTES = KB_IN_BYTES * 1024
GB_IN_BYTES = MB_IN_BYTES * 1024
AUTO_MESSAGE_PREFIX = "[Auto-Message] "


@dataclass
class ShareStats:
    """Simple structure for user share statistics."""
    files: int
    folders: int
    private_folders: int
    total_shared: int
    locked_percent: int


class Plugin(BasePlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._required_share_bytes = 0

        self.settings = {
            "open_private_chat": False,
            "no_files_ban": True,
            "no_files_pm": True,
            "no_files_message": "",
            "all_privates_ban": True,
            "all_privates_pm": True,
            "all_privates_message": "",
            "empty_folders_ban": True,
            "empty_folders_pm": True,
            "empty_folders_message": "",
            "num_files": 10,
            "num_files_ban": False,
            "num_files_pm": False,
            "num_files_message": "",
            "num_folders": 10,
            "num_folders_ban": False,
            "num_folders_pm": False,
            "num_folders_message": "",
            "percent_threshold": 1,
            "percent_threshold_ban": False,
            "percent_threshold_pm": False,
            "percent_threshold_message": "",
            "share_size": 10,
            "share_size_unit": "MB",
            "share_size_ban": False,
            "share_size_pm": False,
            "share_size_message": "",
        }

        self.metasettings = {
            "open_private_chat": {"description": "Open chat tabs when sending messages?", "type": "bool"},
            # Zero/Private Share Checks
            "no_files_ban": {"description": "Ban users with 0 files/folders shared?", "type": "bool"},
            "no_files_pm": {"description": "Send message to users with 0 shares?", "type": "bool"},
            "no_files_message": {"type": "string"},
            "all_privates_ban": {"description": "Ban users with all shared folders locked?", "type": "bool"},
            "all_privates_pm": {"description": "Send a message to users with all shares locked?", "type": "bool"},
            "all_privates_message": {"type": "string"},
            "empty_folders_ban": {"description": "Ban users with no files (only empty shared folders)?", "type": "bool"},
            "empty_folders_pm": {"description": "Send a message to users with no files?", "type": "bool"},
            "empty_folders_message": {"type": "string"},
            # Minimum Count Checks
            "num_files": {"description": "Minimum number of shared files required:", "type": "int", "minimum": 0},
            "num_files_ban": {"description": "Apply a ban for file counts below minimum?", "type": "bool"},
            "num_files_pm": {"description": "Send a message to users below file threshold?", "type": "bool"},
            "num_files_message": {"type": "string"},
            "num_folders": {"description": "Minimum number of shared folders required:", "type": "int", "minimum": 0},
            "num_folders_ban": {"description": "Apply a ban for folder counts below minimum?", "type": "bool"},
            "num_folders_pm": {"description": "Send a message to users below folder threshold?", "type": "bool"},
            "num_folders_message": {"type": "string"},
            # Privacy Threshold Check
            "percent_threshold": {"description": "Max percentage of locked/private folders allowed (1-99):", "type": "int", "minimum": 1, "maximum": 99},
            "percent_threshold_ban": {"description": "Apply a ban for exceeding private folder percentage?", "type": "bool"},
            "percent_threshold_pm": {"description": "Send a message about locked/private counts?", "type": "bool"},
            "percent_threshold_message": {"type": "string"},
            # Share Size Check
            "share_size": {"description": "Minimum size of share required:", "type": "int", "minimum": 0, "maximum": 1000},
            "share_size_unit": {"description": "Unit of measurement:", "type": "dropdown", "options": ("MB", "GB")},
            "share_size_ban": {"description": "Apply a ban for share sizes below minimum?", "type": "bool"},
            "share_size_pm": {"description": "Send a message about share sizes?", "type": "bool"},
            "share_size_message": {"type": "string"},
        }

        self.probed_downloaders = {}   # "DOWNLOADER" → "OK"

    def loaded_notification(self):
        messages = {
            "no_files_message": "You need shared files to download from me",
            "all_privates_message": "You cannot download from me when all your files are private/locked.",
            "empty_folders_message": "You cannot download from me with only empty folders.",
            "num_files_message": "Please consider sharing more files.",
            "num_folders_message": "Please consider sharing more folders.",
            "percent_threshold_message": "You have too many locked/private folders.",
            "share_size_message": "You are not sharing enough data.",
        }
        for key, default in messages.items():
            self.settings.setdefault(key, default)

        try:
            self._required_share_bytes = self._convert_size_to_bytes(
                self.settings["share_size"], self.settings["share_size_unit"])
        except ValueError as e:
            self.log(f"Invalid share size setting: {e}")
            self._required_share_bytes = 0

        self.log(
            f"Requirements → min {self.settings['num_files']} files, "
            f"{self.settings['num_folders']} folders, "
            f"< {self.settings['percent_threshold']}% locked, "
            f"≥ {self.settings['share_size']} {self.settings['share_size_unit']}"
        )
        self.log("Note: This plugin is **not** officially supported by Nicotine+.")

    def _convert_size_to_bytes(self, value: int, unit: str) -> int:
        if unit == "MB":
            return value * MB_IN_BYTES
        if unit == "GB":
            return value * GB_IN_BYTES
        raise ValueError(f"Unsupported unit: {unit!r} (only MB/GB allowed)")

    def _log_and_ban_user(self, user: str) -> None:
        self.core.network_filter.ban_user(user)
        self.log(f"BANNED: {user}")

    def _log_and_message_user(self, user: str, message: str) -> None:
        full_msg = AUTO_MESSAGE_PREFIX + message
        self.send_private(
            user,
            full_msg,
            show_ui=self.settings["open_private_chat"],
            switch_page=False
        )
        self.log(f"PM → {user}: {full_msg!r}")

    def _handle_user_action(self, user: str, settings_prefix: str) -> None:
        ban_key    = f"{settings_prefix}_ban"
        pm_key     = f"{settings_prefix}_pm"
        msg_key    = f"{settings_prefix}_message"

        if self.settings.get(ban_key):
            self._log_and_ban_user(user)

        if self.settings.get(pm_key):
            msg = self.settings.get(msg_key, "").strip()
            if msg:
                self._log_and_message_user(user, msg)
            else:
                self.log(f"Warning: {pm_key} enabled but message is empty")

    def upload_queued_notification(self, user: str, virtual_path: str, real_path: str) -> None:
        if user in self.probed_downloaders:
            return

        self.probed_downloaders[user] = "DOWNLOADER"
        self.core.userbrowse.browse_user(user)
        self.log(f"Upload requested → browsing {user} ...")

    def _calculate_stats(self, stats: dict) -> ShareStats:
        # Current Nicotine+ (2024–2026) keys:
        #   files_count, folders_count, password_protected_folders_count, shared_size
        files   = stats.get("files_count", 0)
        folders = stats.get("folders_count", 0)
        priv    = stats.get("password_protected_folders_count", 0)
        size    = stats.get("shared_size", 0)

        percent_locked = round((priv / folders * 100)) if folders > 0 else 0

        return ShareStats(files, folders, priv, size, percent_locked)

    def user_stats_notification(self, user: str, stats: dict) -> None:
        if "password_protected_folders_count" not in stats:
            return  # incomplete stats → ignore

        user_stats = self._calculate_stats(stats)

        self.log(
            f"[STAT] {user}: {user_stats.files:,} files • {user_stats.folders:,} folders "
            f"({user_stats.private_folders:,} locked) • {user_stats.locked_percent}% locked • "
            f"{human_size(user_stats.total_shared)}"
        )

        if self.probed_downloaders.get(user) != "DOWNLOADER":
            return

        self.log(f"→ Performing leech check on {user}")

        self._check_downloader(
            user,
            user_stats.files,
            user_stats.folders,
            user_stats.private_folders,
            user_stats.locked_percent,
            user_stats.total_shared,
        )

    def _check_downloader(
        self,
        user: str,
        files: int,
        folders: int,
        private_folders: int,
        locked_percent: int,
        total_shared: int
    ) -> None:
        required_human = human_size(self._required_share_bytes)

        checks = [
            (not files and not folders,               "no_files",        f"{user} has zero files & zero folders"),
            (files > 0 and folders == private_folders, "all_privates",    f"{user} → all folders are locked"),
            (not files and folders > 0,               "empty_folders",   f"{user} → only empty folders"),
            (files   < self.settings["num_files"],    "num_files",       f"{user} has only {files} files (need ≥{self.settings['num_files']})"),
            (folders < self.settings["num_folders"],  "num_folders",     f"{user} has only {folders} folders (need ≥{self.settings['num_folders']})"),
            (locked_percent > self.settings["percent_threshold"], "percent_threshold",
             f"{user} → {locked_percent}% locked folders (max {self.settings['percent_threshold']}%)"),
            (total_shared < self._required_share_bytes, "share_size",
             f"{user} shares {human_size(total_shared)} (need ≥ {required_human})"),
        ]

        for failed, prefix, log_text in checks:
            if failed:
                self.log(f"REJECT → {log_text}")
                self._handle_user_action(user, prefix)
                # Optional: self.core.userbrowse.collapse_user_results(user)
                return

        self.probed_downloaders[user] = "OK"
        self.log(f"{user} → PASSED all share requirements")
