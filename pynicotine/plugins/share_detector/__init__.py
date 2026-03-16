# COPYRIGHT (C) 2020-2026 Nicotine+ Contributors
# COPYRIGHT (C) 2011 quinox <quinox@users.sf.net>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
# ...

# COPYRIGHT (C) 2020-2026 Nicotine+ Contributors
# COPYRIGHT (C) 2011 quinox <quinox@users.sf.net>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
# ...

from pynicotine.pluginsystem import BasePlugin
from pynicotine.utils import human_size
from dataclasses import dataclass
from typing import Dict

KB_IN_BYTES = 1024
MB_IN_BYTES = KB_IN_BYTES * 1024
GB_IN_BYTES = MB_IN_BYTES * 1024
AUTO_MESSAGE_PREFIX = "[Auto-Message] "

@dataclass
class ShareStats:
    files: int
    folders: int
    private_folders: int
    total_shared: int  # in bytes
    locked_percent: int


class Plugin(BasePlugin):

    __settings__ = {
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
        "min_files": 10,
        "min_files_ban": False,
        "min_files_pm": False,
        "min_files_message": "",
        "min_folders": 10,
        "min_folders_ban": False,
        "min_folders_pm": False,
        "min_folders_message": "",
        "max_locked_percent": 5,
        "max_locked_percent_ban": False,
        "max_locked_percent_pm": False,
        "max_locked_percent_message": "",
        "min_share_value": 10,
        "min_share_unit": "GB",
        "min_share_ban": True,
        "min_share_pm": True,
        "min_share_message": "",
    }

    __metasettings__ = {
        "open_private_chat": {
            "description": "Open private chat tabs when sending messages",
            "type": "bool",
        },
        "no_files_ban": {"description": "Ban users with 0 files/folders shared", "type": "bool"},
        "no_files_pm": {"description": "Send PM to users with 0 shares", "type": "bool"},
        "no_files_message": {"description": "Message for users with 0 shares", "type": "string"},
        "all_privates_ban": {"description": "Ban users with all folders locked/private", "type": "bool"},
        "all_privates_pm": {"description": "Send PM to users with all folders locked", "type": "bool"},
        "all_privates_message": {"description": "Message for all-private shares", "type": "string"},
        "empty_folders_ban": {"description": "Ban users with only empty folders", "type": "bool"},
        "empty_folders_pm": {"description": "Send PM to users with empty folders only", "type": "bool"},
        "empty_folders_message": {"description": "Message for empty-folder shares", "type": "string"},
        "min_files": {
            "description": "Minimum number of shared files required",
            "type": "int",
            "minimum": 0,
            "maximum": 10000,
        },
        "min_files_ban": {"description": "Ban if below minimum files", "type": "bool"},
        "min_files_pm": {"description": "Send PM if below minimum files", "type": "bool"},
        "min_files_message": {"description": "Message if below minimum files", "type": "string"},
        "min_folders": {
            "description": "Minimum number of shared folders required",
            "type": "int",
            "minimum": 0,
            "maximum": 5000,
        },
        "min_folders_ban": {"description": "Ban if below minimum folders", "type": "bool"},
        "min_folders_pm": {"description": "Send PM if below minimum folders", "type": "bool"},
        "min_folders_message": {"description": "Message if below minimum folders", "type": "string"},
        "max_locked_percent": {
            "description": "Maximum % of folders allowed to be locked/private",
            "type": "int",
            "minimum": 1,
            "maximum": 99,
        },
        "max_locked_percent_ban": {"description": "Ban if locked % exceeds maximum", "type": "bool"},
        "max_locked_percent_pm": {"description": "Send PM if locked % exceeds maximum", "type": "bool"},
        "max_locked_percent_message": {"description": "Message if locked % too high", "type": "string"},
        "min_share_value": {
            "description": "Minimum share size (numeric value)",
            "type": "int",
            "minimum": 1,
            "maximum": 1000,
            "step": 1,
        },
        "min_share_unit": {
            "description": "Unit for minimum share size",
            "type": "dropdown",
            "options": ["MB", "GB"],
        },
        "min_share_ban": {"description": "Ban if share size below minimum", "type": "bool"},
        "min_share_pm": {"description": "Send PM if share size below minimum", "type": "bool"},
        "min_share_message": {"description": "Message if share size below minimum", "type": "string"},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._required_share_bytes: int = 0
        self.probed_downloaders: Dict[str, str] = {}

    def loaded_notification(self):
        defaults = {
            "no_files_message": "You need to share some files to download from me.",
            "all_privates_message": "All your shared folders appear locked/private — please unlock some to download.",
            "empty_folders_message": "Your shared folders contain no files — please add content.",
            "min_files_message": "Please share at least {min_files} files to download from me.",
            "min_folders_message": "Please share at least {min_folders} folders.",
            "max_locked_percent_message": "Too many locked/private folders ({percent_threshold}% allowed).",
            "min_share_message": "You need to share at least {share_size} {share_unit} to download from me.",
        }
        for key, msg in defaults.items():
            if not self.settings.get(key):
                # Format placeholders if present (simple replace for now)
                formatted = msg.format(
                    min_files=self.settings["min_files"],
                    min_folders=self.settings["min_folders"],
                    percent_threshold=self.settings["max_locked_percent"],
                    share_size=self.settings["min_share_value"],
                    share_unit=self.settings["min_share_unit"],
                )
                self.settings[key] = formatted

        self._update_required_share_bytes()

        self.log(
            f"Anti-leech requirements loaded: ≥{self.settings['min_files']} files, "
            f"≥{self.settings['min_folders']} folders, ≤{self.settings['max_locked_percent']}% locked, "
            f"≥{self.settings['min_share_value']} {self.settings['min_share_unit']} shared."
        )
        self.log("Note: This plugin is community-maintained and not officially supported by Nicotine+ developers.")

    def _update_required_share_bytes(self):
        value = self.settings["min_share_value"]
        unit = self.settings["min_share_unit"]
        multiplier = MB_IN_BYTES if unit == "MB" else GB_IN_BYTES
        self._required_share_bytes = value * multiplier

    def _convert_size_to_bytes(self, value: int, unit: str) -> int:
        if unit == "MB":
            return value * MB_IN_BYTES
        if unit == "GB":
            return value * GB_IN_BYTES
        raise ValueError(f"Invalid share size unit: {unit}")

    def _log_and_ban_user(self, user: str):
        self.core.network_filter.ban_user(user)
        self.log(f"Banned user: {user}")

    def _log_and_message_user(self, user: str, message: str):
        full_msg = AUTO_MESSAGE_PREFIX + message
        self.send_private(user, full_msg, show_ui=self.settings["open_private_chat"], switch_page=False)
        self.log(f"PM sent to {user}: {full_msg}")

    def _handle_user_action(self, user: str, settings_prefix: str):
        ban_key = f"{settings_prefix}_ban"
        pm_key = f"{settings_prefix}_pm"
        msg_key = f"{settings_prefix}_message"

        if self.settings.get(ban_key, False):
            self._log_and_ban_user(user)

        if self.settings.get(pm_key, False) and self.settings.get(msg_key):
            self._log_and_message_user(user, self.settings[msg_key])

    def upload_queued_notification(self, user: str, virtual_path: str, real_path: str):
        if user in self.probed_downloaders:
            return
        self.probed_downloaders[user] = "DOWNLOADER"
        self.core.userbrowse.browse_user(user)
        self.log(f"Upload requested by {user} — browsing shares for check...")

    def _calculate_stats(self, stats: Dict[str, Any]) -> ShareStats:
        files = int(stats.get("files", 0))
        folders = int(stats.get("dirs", 0))
        private_folders = int(stats.get("private_dirs", 0))
        total_shared = int(stats.get("shared_size", 0))
        locked_percent = round((private_folders / folders * 100) if folders > 0 else 0)
        return ShareStats(files, folders, private_folders, total_shared, locked_percent)

    def user_stats_notification(self, user: str, stats: Dict[str, Any]):
        if stats.get("private_dirs") is None:
            return

        user_stats = self._calculate_stats(stats)

        self.log(
            f"[STATS] {user}: {user_stats.files} files, {user_stats.folders} folders "
            f"({user_stats.private_folders} private, {user_stats.locked_percent}%), "
            f"total {human_size(user_stats.total_shared)}"
        )

        if self.probed_downloaders.get(user) != "DOWNLOADER":
            return

        self.log(f"Checking leech status for {user}...")

        self._check_downloader(
            user,
            user_stats.files,
            user_stats.folders,
            user_stats.private_folders,
            user_stats.locked_percent,
            user_stats.total_shared,
        )

    def _check_downloader(self, user: str, files: int, folders: int, private_folders: int, locked_percent: int, total_shared: int):
        required_human = human_size(self._required_share_bytes)

        rules = [
            {"cond": not files and not folders, "msg": f"{user} shares nothing (0 files, 0 folders).", "prefix": "no_files"},
            {"cond": files > 0 and folders == private_folders, "msg": f"{user} has files but all folders locked/private.", "prefix": "all_privates"},
            {"cond": not files and folders > 0, "msg": f"{user} has only empty folders ({folders} folders, 0 files).", "prefix": "empty_folders"},
            {"cond": files < self.settings["min_files"], "msg": f"{user} has only {files} files (min {self.settings['min_files']}).", "prefix": "min_files"},
            {"cond": folders < self.settings["min_folders"], "msg": f"{user} has only {folders} folders (min {self.settings['min_folders']}).", "prefix": "min_folders"},
            {"cond": locked_percent > self.settings["max_locked_percent"], "msg": f"{user} has {locked_percent}% locked folders (max {self.settings['max_locked_percent']}%).", "prefix": "max_locked_percent"},
            {"cond": total_shared < self._required_share_bytes, "msg": f"{user} shares {human_size(total_shared)} (min {required_human}).", "prefix": "min_share"},
        ]

        for rule in rules:
            if rule["cond"]:
                self.log(f"CHECK FAILED: {rule['msg']}")
                self._handle_user_action(user, rule["prefix"])
                self.core.userbrowse.remove_user(user)
                return

        self.probed_downloaders[user] = "OK"
        self.log(f"{user} passed all share checks — uploads allowed.")