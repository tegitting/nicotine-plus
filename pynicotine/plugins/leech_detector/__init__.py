#
# Leech Detector Plugin for Nicotine+
# GNU GENERAL PUBLIC LICENSE Version 3
#

from pynicotine.pluginsystem import BasePlugin
from pynicotine.utils import human_size
from dataclasses import dataclass
import time
import threading

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

            # Primary modern checks (size-based)
            "min_public_percent": 80,
            "min_public_gib": 50,
            "size_ratio_ban": True,
            "size_ratio_pm": True,
            "size_ratio_message": "Your public share is too small or too much is locked/private. Please share more openly.",
        }

        self.metasettings = { ... }   # ← your entire metasettings block stays exactly the same

        self.probed_users = {}        # NEW: tracks users we requested stats for
        self.lock = threading.Lock()

    def loaded_notification(self):
        self.log("Leech Detector loaded – now fires on every upload_queued_notification.")
        self.log(f"→ Requires at least {self.settings['min_public_percent']}% public + "
                 f"{self.settings['min_public_gib']} GiB of public data.")
        self.log("NOTE: This plugin is not endorsed or supported by the Nicotine+ Developers!")

    # ==================== NEW: THIS IS WHAT MAKES IT FIRE ====================
    def upload_queued_notification(self, user, virtual_path, real_path):
        """Fires the moment someone queues a download from you."""
        now = time.time()
        cooldown = 30  # seconds – prevent spamming the same user

        with self.lock:
            if now - self.probed_users.get(user, 0) < cooldown:
                return
            self.probed_users[user] = now
            self.core.userbrowse.request_user_shares(user)   # ← this forces the rich stats

        # Start timeout timer in case the user never replies (spoofer)
        threading.Thread(target=self._check_timeout, args=(user, now), daemon=True).start()

    def _check_timeout(self, user, request_time):
        time.sleep(25)  # wait up to 25 seconds for stats
        with self.lock:
            if user not in self.probed_users or self.probed_users[user] != request_time:
                return
            self.probed_users.pop(user, None)

        self.log(f"TIMEOUT: No stats received from {user} → cancelling uploads")
        self._cancel_all_uploads_from_user(user)

    # ==================== EXISTING CODE (unchanged) ====================
    def user_stats_notification(self, user, stats):
        if stats.get('source') != 'peer':
            return

        with self.lock:
            if user not in self.probed_users:
                return
            del self.probed_users[user]   # stats arrived → cancel timeout

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

    # ... the rest of your methods stay 100% unchanged (_run_legacy_checks, _handle_no_share, _handle_leech, _send_message, _convert_size_to_bytes) ...

    def _cancel_all_uploads_from_user(self, user):
        """Helper to cancel uploads on timeout (optional but useful)."""
        try:
            for transfer in list(getattr(self.core.transfers, 'uploads', [])):
                if getattr(transfer, 'user', None) == user:
                    try:
                        self.core.transfers.abort_upload(transfer.user, transfer.virtual_path)
                    except:
                        self.core.transfers.cancel_transfer(transfer)
        except Exception as e:
            self.log(f"Error cancelling uploads for {user}: {e}")
