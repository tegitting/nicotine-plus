#
# Leech Detector Plugin for Nicotine+
# GNU GENERAL PUBLIC LICENSE Version 3
#

from pynicotine.pluginsystem import BasePlugin
from pynicotine.utils import human_size
import time
import threading

GB_IN_BYTES = 1024 ** 3
AUTO_MESSAGE_PREFIX = "[Auto-Message] "


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

            # Primary modern checks (size-based)
            "min_public_percent": 80,
            "min_public_gib": 50,
            "size_ratio_ban": True,
            "size_ratio_pm": True,
            "size_ratio_message": "Your public share is too small or too much is locked/private. Please share more openly.",
        }

        self.metasettings = {
            "open_private_chat": {"description": "Open private chat tabs when sending messages?", "type": "bool"},

            "no_files_ban": {"description": "Ban users with 0 files/folders shared?", "type": "bool"},
            "no_files_pm": {"description": "Send message to users with 0 shares?", "type": "bool"},
            "no_files_message": {"type": "string"},

            "all_privates_ban": {"description": "Ban users with all shared folders locked?", "type": "bool"},
            "all_privates_pm": {"description": "Send a message to users with all shares locked?", "type": "bool"},
            "all_privates_message": {"type": "string"},

            "empty_folders_ban": {"description": "Ban users with no files (only empty shared folders)?", "type": "bool"},
            "empty_folders_pm": {"description": "Send a message to users with no files?", "type": "bool"},
            "empty_folders_message": {"type": "string"},

            "num_files": {"description": "Minimum number of shared files required:", "type": "int", "minimum": 0},
            "num_files_ban": {"description": "Apply a ban for file counts below minimum?", "type": "bool"},
            "num_files_pm": {"description": "Send a message to users below file threshold?", "type": "bool"},
            "num_files_message": {"type": "string"},

            "num_folders": {"description": "Minimum number of shared folders required:", "type": "int", "minimum": 0},
            "num_folders_ban": {"description": "Apply a ban for folder counts below minimum?", "type": "bool"},
            "num_folders_pm": {"description": "Send a message to users below folder threshold?", "type": "bool"},
            "num_folders_message": {"type": "string"},

            "share_size": {"description": "Minimum total share size required:", "type": "int", "minimum": 0, "maximum": 1000},
            "share_size_unit": {"description": "Unit of measurement:", "type": "dropdown", "options": ("MB", "GB")},
            "share_size_ban": {"description": "Apply a ban for total share sizes below minimum?", "type": "bool"},
            "share_size_pm": {"description": "Send a message about total share sizes?", "type": "bool"},
            "share_size_message": {"type": "string"},

            "min_public_percent": {"description": "Minimum % of total share that must be PUBLIC (70-90 recommended):", "type": "int", "minimum": 0, "maximum": 100},
            "min_public_gib": {"description": "Minimum public share size in GiB (0 = disabled):", "type": "int", "minimum": 0},
            "size_ratio_ban": {"description": "Ban users who fail the public size ratio check?", "type": "bool"},
            "size_ratio_pm": {"description": "Send message to users who fail the public size ratio check?", "type": "bool"},
            "size_ratio_message": {"type": "string"},
        }

        self.probed_users = {}
        self.lock = threading.Lock()

    def loaded_notification(self):
        self.log("Leech Detector loaded – now fires on every upload_queued_notification.")
        self.log(f"→ Requires at least {self.settings['min_public_percent']}% public + "
                 f"{self.settings['min_public_gib']} GiB of public data.")
        self.log("NOTE: This plugin is not endorsed or supported by the Nicotine+ Developers!")

    # ==================== THIS IS THE PART THAT WAS MISSING ====================
    def upload_queued_notification(self, user, virtual_path, real_path):
        """Fires the moment someone queues a download from you."""
        now = time.time()
        cooldown = 30  # prevent spamming the same user

        with self.lock:
            if now - self.probed_users.get(user, 0) < cooldown:
                return
            self.probed_users[user] = now
            self.core.userbrowse.request_user_shares(user)

        # Timeout protection for spoofers
        threading.Thread(target=self._check_timeout, args=(user, now), daemon=True).start()

    def _check_timeout(self, user, request_time):
        time.sleep(25)
        with self.lock:
            if user not in self.probed_users or self.probed_users[user] != request_time:
                return
            self.probed_users.pop(user, None)

        self.log(f"TIMEOUT: No stats from {user} → cancelling uploads")
        self._cancel_all_uploads_from_user(user)

    def user_stats_notification(self, user, stats):
        if stats.get('source') != 'peer':
            return

        with self.lock:
            if user not in self.probed_users:
                return
            del self.probed_users[user]

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

        self.log(f"[STATS] {username} shares {files:,} files, {dirs:,} folders ({private_dirs:,} private). "
                 f"Public: {human_size(public_bytes)} ({public_percent:.1f}%) | "
                 f"Locked: {human_size(private_bytes)}")

        # Primary size-based check
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

        self._run_legacy_checks(username, files, dirs, private_dirs, total_bytes, public_bytes, public_percent)

    def _run_legacy_checks(self, user, files, dirs, private_dirs, total_bytes, public_bytes, public_percent):
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

    def _cancel_all_uploads_from_user(self, user):
        try:
            for transfer in list(getattr(self.core.transfers, 'uploads', [])):
                if getattr(transfer, 'user', None) == user:
                    try:
                        self.core.transfers.abort_upload(transfer.user, transfer.virtual_path)
                    except:
                        self.core.transfers.cancel_transfer(transfer)
        except Exception as e:
            self.log(f"Error cancelling uploads for {user}: {e}")
