#
# Leech Detector Plugin for Nicotine+
# GNU GENERAL PUBLIC LICENSE Version 3
#

from pynicotine.pluginsystem import BasePlugin
from pynicotine.utils import human_size
from dataclasses import dataclass

GB_IN_BYTES = 1024 ** 3
AUTO_MESSAGE_PREFIX = "[Auto-Message] "


@dataclass
class ShareStats:
    """Simple structure for user share statistics."""
    files: int
    folders: int
    private_folders: int
    total_shared: int          # bytes
    private_shared: int        # bytes
    public_shared: int         # bytes
    public_percent: float


class Plugin(BasePlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.settings = {
            "open_private_chat": False,

            # Essential checks
            "no_files_ban": True,
            "no_files_pm": True,
            "no_files_message": "You need shared files to download from me",

            "all_privates_ban": True,
            "all_privates_pm": True,
            "all_privates_message": "You cannot download from me when your files are all private",

            "empty_folders_ban": True,
            "empty_folders_pm": True,
            "empty_folders_message": "You cannot download from me when your shared folders are empty",

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

            # === Primary modern checks (size-based) ===
            "min_public_percent": 80,        # Minimum % of total share that must be public
            "min_public_gib": 50,            # Minimum public size in GiB
            "size_ratio_ban": True,
            "size_ratio_pm": True,
            "size_ratio_message": "Your public share is too small or too much is locked/private. Please share more openly.",
        }

        self.metasettings = {
            "open_private_chat": {
                "description": "Open private chat tabs when sending messages?",
                "type": "bool"
            },

            # Zero / all-private / empty checks
            "no_files_ban": {"description": "Ban users with 0 files/folders shared?", "type": "bool"},
            "no_files_pm": {"description": "Send message to users with 0 shares?", "type": "bool"},
            "no_files_message": {"type": "string"},

            "all_privates_ban": {"description": "Ban users with all shared folders locked?", "type": "bool"},
            "all_privates_pm": {"description": "Send a message to users with all shares locked?", "type": "bool"},
            "all_privates_message": {"type": "string"},

            "empty_folders_ban": {"description": "Ban users with no files (only empty shared folders)?", "type": "bool"},
            "empty_folders_pm": {"description": "Send a message to users with no files?", "type": "bool"},
            "empty_folders_message": {"type": "string"},

            # Minimum count checks
            "num_files": {"description": "Minimum number of shared files required:", "type": "int", "minimum": 0},
            "num_files_ban": {"description": "Apply a ban for file counts below minimum?", "type": "bool"},
            "num_files_pm": {"description": "Send a message to users below file threshold?", "type": "bool"},
            "num_files_message": {"type": "string"},

            "num_folders": {"description": "Minimum number of shared folders required:", "type": "int", "minimum": 0},
            "num_folders_ban": {"description": "Apply a ban for folder counts below minimum?", "type": "bool"},
            "num_folders_pm": {"description": "Send a message to users below folder threshold?", "type": "bool"},
            "num_folders_message": {"type": "string"},

            # Old total size check
            "share_size": {"description": "Minimum total share size required:", "type": "int", "minimum": 0, "maximum": 1000},
            "share_size_unit": {"description": "Unit of measurement:", "type": "dropdown", "options": ("MB", "GB")},
            "share_size_ban": {"description": "Apply a ban for total share sizes below minimum?", "type": "bool"},
            "share_size_pm": {"description": "Send a message about total share sizes?", "type": "bool"},
            "share_size_message": {"type": "string"},

            # === Primary: Size-based public ratio ===
            "min_public_percent": {
                "description": "Minimum % of total share that must be PUBLIC (recommended: 70-90):",
                "type": "int",
                "minimum": 0,
                "maximum": 100
            },
            "min_public_gib": {
                "description": "Minimum public share size in GiB (0 = disabled):",
                "type": "int",
                "minimum": 0
            },
            "size_ratio_ban": {"description": "Ban users who fail the public size ratio check?", "type": "bool"},
            "size_ratio_pm": {"description": "Send message to users who fail the public size ratio check?", "type": "bool"},
            "size_ratio_message": {"type": "string"},
        }

        self.probed_downloaders = {}

    def loaded_notification(self):
        self.log("Leech Detector loaded – using modern size-based public ratio logic.")
        self.log(f"→ Requires at least {self.settings['min_public_percent']}% public + "
                 f"{self.settings['min_public_gib']} GiB of public data.")
        self.log("NOTE: This plugin is not endorsed or supported by the Nicotine+ Developers!")

    def user_stats_notification(self, user, stats):
        if stats.get('source') != 'peer':
            return

        username = stats['username']
        files = stats.get('files', 0)
        dirs = stats.get('dirs', 0)
        private_dirs = stats.get('private_dirs', 0)
        total_bytes = stats.get('shared_size', 0)
        private_bytes = stats.get('private_shared_size', 0)
        public_bytes = total_bytes - private_bytes

        if total_bytes == 0:
            self._handle_no_share(username)
            return

        public_percent = (public_bytes / total_bytes * 100) if total_bytes > 0 else 0.0

        # Nice human-readable logging
        self.log(f"[STATS] {username} shares {files:,} files, {dirs:,} folders ({private_dirs:,} private). "
                 f"Public: {human_size(public_bytes)} ({public_percent:.1f}%) | "
                 f"Locked: {human_size(private_bytes)}")

        # === PRIMARY CHECK: Size-based public ratio ===
        min_pub_pct = self.settings.get("min_public_percent", 80)
        min_pub_gib = self.settings.get("min_public_gib", 50)
        min_pub_bytes = min_pub_gib * GB_IN_BYTES

        fails_size_ratio = (public_percent < min_pub_pct) or (min_pub_gib > 0 and public_bytes < min_pub_bytes)

        if fails_size_ratio:
            if self.settings.get("size_ratio_ban", True):
                self._handle_leech(username, self.settings.get("size_ratio_message"), "size_ratio")
                return
            if self.settings.get("size_ratio_pm", True):
                self._send_message(username, self.settings.get("size_ratio_message"))
                return

        # Only run legacy checks if user passed the modern size ratio
        self._run_legacy_checks(username, files, dirs, private_dirs, total_bytes, public_bytes, public_percent)

    def _run_legacy_checks(self, user, files, dirs, private_dirs, total_bytes, public_bytes, public_percent):
        """Remaining useful legacy checks (old folder % removed completely)."""

        if files == 0:
            if self.settings["no_files_ban"]:
                self._handle_leech(user, self.settings["no_files_message"], "no_files")
            elif self.settings["no_files_pm"]:
                self._send_message(user, self.settings["no_files_message"])
            return

        if files == 0 and dirs > 0 and self.settings["empty_folders_ban"]:
            self._handle_leech(user, self.settings["empty_folders_message"], "empty_folders")
            return

        if dirs > 0 and private_dirs == dirs and self.settings["all_privates_ban"]:
            self._handle_leech(user, self.settings["all_privates_message"], "all_private")
            return

        if files < self.settings["num_files"] and self.settings["num_files_ban"]:
            self._handle_leech(user, self.settings["num_files_message"], "num_files")
            return

        if dirs < self.settings["num_folders"] and self.settings["num_folders_ban"]:
            self._handle_leech(user, self.settings["num_folders_message"], "num_folders")
            return

        # Old total share size check
        required_bytes = self._convert_size_to_bytes(self.settings["share_size"], self.settings["share_size_unit"])
        if total_bytes < required_bytes and self.settings["share_size_ban"]:
            self._handle_leech(user, self.settings["share_size_message"], "share_size")
            return

        self.log(f"✓ {user} passed all checks (public: {human_size(public_bytes)} / {public_percent:.1f}%)")

    def _handle_no_share(self, user):
        if self.settings["no_files_ban"]:
            self._handle_leech(user, self.settings["no_files_message"], "no_files")
        elif self.settings["no_files_pm"]:
            self._send_message(user, self.settings["no_files_message"])

    def _handle_leech(self, user, message, reason):
        if self.settings.get(f"{reason}_ban", False):
            self.core.network_filter.ban_user(user)
            self.log(f"ACTION: Banned {user} (reason: {reason})")

        if self.settings.get(f"{reason}_pm", False) or self.settings["open_private_chat"]:
            self._send_message(user, message)

    def _send_message(self, user, message):
        if not message:
            return
        full_msg = AUTO_MESSAGE_PREFIX + message
        self.core.privatechat.send_message(user, full_msg)
        if self.settings["open_private_chat"]:
            self.core.privatechat.show_user(user)
        self.log(f"→ Message sent to {user}: {message}")

    def _convert_size_to_bytes(self, value, unit):
        if unit == "MB":
            return value * (1024 ** 2)
        elif unit == "GB":
            return value * (1024 ** 3)
        return 0
