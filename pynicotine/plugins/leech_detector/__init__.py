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
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU GENERAL PUBLIC LICENSE for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from pynicotine.pluginsystem import BasePlugin
from pynicotine.utils import human_size
from dataclasses import dataclass

# Define constants for clarity and maintainability (Using powers of 2 is idiomatic)
KB_IN_BYTES = 1024
MB_IN_BYTES = KB_IN_BYTES * 1024
GB_IN_BYTES = MB_IN_BYTES * 1024
AUTO_MESSAGE_PREFIX = "[Auto-Message] "

@dataclass
class ShareStats:
    """A simple structure for organizing user share statistics."""
    files: int
    folders: int
    private_folders: int
    total_shared: int
    locked_percent: int


class Plugin(BasePlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store required share size in bytes after calculation
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
            "open_private_chat": {
                "description": "Open chat tabs when sending messages?",
                "type": "bool",
            },
            # --- Zero/Private Share Checks ---
            "no_files_ban": {"description": "Ban users with 0 files/folders shared?", "type": "bool"},
            "no_files_pm": {"description": "Send message to users with 0 shares?", "type": "bool"},
            "no_files_message": {"type": "string"},
            "all_privates_ban": {"description": "Ban users with all shared folders locked?", "type": "bool"},
            "all_privates_pm": {"description": "Send a message to users with all shares locked?", "type": "bool"},
            "all_privates_message": {"type": "string"},
            "empty_folders_ban": {"description": "Ban users with no files (only empty shared folders)?", "type": "bool"},
            "empty_folders_pm": {"description": "Send a message to users with no files?", "type": "bool"},
            "empty_folders_message": {"type": "string"},
            # --- Minimum Count Checks ---
            "num_files": {"description": "Minimum number of shared files required:", "type": "int", "minimum": 0},
            "num_files_ban": {"description": "Apply a ban for file counts below minimum?", "type": "bool"},
            "num_files_pm": {"description": "Send a message to users below file threshold?", "type": "bool"},
            "num_files_message": {"type": "string"},
            "num_folders": {"description": "Minimum number of shared folders required:", "type": "int", "minimum": 0},
            "num_folders_ban": {"description": "Apply a ban for folder counts below minimum?", "type": "bool"},
            "num_folders_pm": {"description": "Send a message to users below folder threshold?", "type": "bool"},
            "num_folders_message": {"type": "string"},
            # --- Privacy Threshold Check ---
            "percent_threshold": {"description": "Max percentage of locked/private folders allowed (1-99):", "type": "int", "minimum": 1, "maximum": 99},
            "percent_threshold_ban": {"description": "Apply a ban for exceeding private folder percentage?", "type": "bool"},
            "percent_threshold_pm": {"description": "Send a message about locked/private counts?", "type": "bool"},
            "percent_threshold_message": {"type": "string"},
            # --- Share Size Check ---
            "share_size": {"description": "Minimum size of share required:", "type": "int", "minimum": 0, "maximum": 1000},
            "share_size_unit": {"description": "Unit of measurement:", "type": "dropdown", "options": ("MB", "GB")},
            "share_size_ban": {"description": "Apply a ban for share sizes below minimum?", "type": "bool"},
            "share_size_pm": {"description": "Send a message about share sizes?", "type": "bool"},
            "share_size_message": {"type": "string"},
        }
        # Tracks users who have requested a download and their current status
        # Status: "DOWNLOADER" (needs check), "OK" (passed check)
        self.probed_downloaders = {}

    def loaded_notification(self):
        # Set default messages if not already configured using the concise setdefault
        messages = {
            "no_files_message": "You need shared files to download from me",
            "all_privates_message": "You cannot download from me when your files are all private",
            "empty_folders_message": "You cannot download from me when your shared folders are empty",
            "num_files_message": "Please consider adding more shared files",
            "num_folders_message": "Please consider having more shared folders",
            "percent_threshold_message": "You have too many locked/private folders",
            "share_size_message": "You are not sharing enough media",
        }
        for key, default_message in messages.items():
            self.settings.setdefault(key, default_message)

        # Calculate and store the required share size in bytes once
        try:
            self._required_share_bytes = self._convert_size_to_bytes(
                self.settings["share_size"], self.settings["share_size_unit"]
            )
        except ValueError as e:
            self.log(f"Configuration Error: {e}")
            self._required_share_bytes = 0 # Default to 0 to prevent issues

        self.log(
            f"Requirements: {self.settings['num_files']} files, {self.settings['num_folders']} folders, "
            f"less than {self.settings['percent_threshold']}% locked, and at least "
            f"{self.settings['share_size']} {self.settings['share_size_unit']} of data shared."
        )
        self.log("NOTE: This plugin is not endorsed or supported by the Nicotine+ Developers!")

    def _convert_size_to_bytes(self, value, unit):
        """Converts a given size to bytes based on the unit. Robust error handling added."""
        if unit == "MB":
            return value * MB_IN_BYTES
        elif unit == "GB":
            return value * GB_IN_BYTES
        # Raise an error for an unknown unit instead of silently returning 0
        raise ValueError(f"Unknown size unit '{unit}' configured for share_size_unit.")

    def _log_and_ban_user(self, user):
        """Logs the ban and calls the core ban function."""
        self.core.network_filter.ban_user(user)
        self.log(f"ACTION: User {user} has been banned.")

    def _log_and_message_user(self, user, message):
        """Logs the message and sends it to the user."""
        # Use f-string for clearer logging
        self.send_private(user, message, show_ui=self.settings["open_private_chat"], switch_page=False)
        self.log(f"ACTION: Message sent to {user}: '{message}'.")

    def _handle_user_action(self, user, settings_prefix):
        """Centralized handler for user actions (ban and message)."""
        ban_enabled = self.settings.get(f"{settings_prefix}_ban")
        message_enabled = self.settings.get(f"{settings_prefix}_pm")
        message_text = self.settings.get(f"{settings_prefix}_message")

        if ban_enabled:
            self._log_and_ban_user(user)
        
        # Check for message text before sending to prevent empty messages
        if message_enabled and message_text:
            self._log_and_message_user(user, AUTO_MESSAGE_PREFIX + message_text)
        elif message_enabled:
            self.log(f"WARNING: Message for action '{settings_prefix}' is enabled but no text is configured.")

    def upload_queued_notification(self, user, virtual_path, real_path):
        """An upload has been requested. Marks user for leech check."""
        # Only process if user isn't already being tracked
        if user in self.probed_downloaders:
            return

        # ONLY mark the user for a check if they initiated an upload
        self.probed_downloaders[user] = "DOWNLOADER"
        self.core.userbrowse.browse_user(user)
        self.log(f"User {user} requested an upload - browsing shares for leech check...")
        
    def _calculate_stats(self, stats):
        """Helper to extract and calculate share statistics."""
        files = int(stats.get("files", 0))
        folders = int(stats.get("dirs", 0))
        private_folders = int(stats.get("private_dirs", 0))
        total_shared = int(stats.get("shared_size", 0))

        # Safe calculation for locked percentage
        locked_percent = round((private_folders / folders) * 100) if folders else 0
        
        return ShareStats(files, folders, private_folders, total_shared, locked_percent)

    def user_stats_notification(self, user, stats):
        """
        Receives and processes stats for a user.
        Stats are always logged, but leech checks only run if user is marked as "DOWNLOADER".
        """
        # Ensure complete stats were received
        if stats.get("private_dirs") is None:
            return

        # Calculate Stats (for logging and potential check)
        user_stats = self._calculate_stats(stats)

        # 1. Log Enhanced Stats (View-Only/Transparency) - ALWAYS run this
        self.log(
            f"[STATS] User {user} shares {user_stats.files} files, {user_stats.folders} folders with "
            f"{user_stats.private_folders} private. {user_stats.locked_percent}% of "
            f"{human_size(user_stats.total_shared)} is locked."
        )

        # 2. Conditional Leech Check - ONLY runs if status is "DOWNLOADER"
        if self.probed_downloaders.get(user) == "DOWNLOADER":
            self.log(f"User {user} is an active downloader; initiating leech check...")

            self._check_downloader(
                user,
                user_stats.files,
                user_stats.folders,
                user_stats.private_folders,
                user_stats.locked_percent,
                user_stats.total_shared,
            )
        # For non-downloaders or users already checked ("OK"), processing stops here.

    def _check_downloader(self, user, files, folders, private_folders, locked_percent, total_shared):
        """Performs analysis on a downloader's stats using a data-driven approach."""
        
        required_share_human = human_size(self._required_share_bytes)

        # Define all rules in a list of dictionaries
        # NOTE: Rules are ordered by severity/certainty for early exit
        rules = [
            {"condition": not files and not folders, "log_msg": f"User {user} shares no files or folders.", "settings_prefix": "no_files"},
            {"condition": files > 0 and folders == private_folders, "log_msg": f"User {user} has shares files but all of their folders are private.", "settings_prefix": "all_privates"},
            {"condition": not files and folders > 0, "log_msg": f"User {user} shares no files, only empty folders.", "settings_prefix": "empty_folders"},
            {"condition": files < self.settings["num_files"], "log_msg": f"User {user} shares {files} files but requires {self.settings['num_files']}.", "settings_prefix": "num_files"},
            {"condition": folders < self.settings["num_folders"], "log_msg": f"User {user} has {folders} folders but requires {self.settings['num_folders']}.", "settings_prefix": "num_folders"},
            {"condition": locked_percent > self.settings["percent_threshold"], "log_msg": f"User {user} has {locked_percent}% of folders locked, requires less than {self.settings['percent_threshold']}%.", "settings_prefix": "percent_threshold"},
            {"condition": total_shared < self._required_share_bytes, "log_msg": f"User {user} shares {human_size(total_shared)} but requires {required_share_human}.", "settings_prefix": "share_size"},
        ]

        for rule in rules:
            if rule["condition"]:
                self.log(f"FAILED CHECK: {rule['log_msg']}")
                self._handle_user_action(user, rule["settings_prefix"])
                self.core.userbrowse.remove_user(user) # Stop browsing immediately
                return # Exit on first failed check

        # If all checks pass
        self.probed_downloaders[user] = "OK"
        self.log(f"User {user} passed all checks and can download.")
