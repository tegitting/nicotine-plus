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
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from pynicotine.pluginsystem import BasePlugin
from pynicotine.utils import human_size

# Define constants to improve readability and maintainability
KB_IN_BYTES = 1024
MB_IN_BYTES = KB_IN_BYTES * 1024
GB_IN_BYTES = MB_IN_BYTES * 1024
AUTO_MESSAGE_PREFIX = "[Auto-Message] "


class Plugin(BasePlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
            # no files options
            "no_files_ban": {
                "description": "Ban users with 0 shares?",
                "type": "bool",
            },
            "no_files_pm": {
                "description": "Send message to users with 0 shares?",
                "type": "bool",
            },
            "no_files_message": {
                "type": "string",
            },
            # all private files options
            "all_privates_ban": {
                "description": "Ban users with all shares locked?",
                "type": "bool",
            },
            "all_privates_pm": {
                "description": "Send a message to users with all shares locked?",
                "type": "bool",
            },
            "all_privates_message": {
                "type": "string",
            },
            # empty folders options
            "empty_folders_ban": {
                "description": "Ban users with empty shared folders?",
                "type": "bool",
            },
            "empty_folders_pm": {
                "description": "Send a message to users empty shared folders?",
                "type": "bool",
            },
            "empty_folders_message": {
                "type": "string",
            },
            # num file options
            "num_files": {
                "description": "Minimum number of shared files:",
                "type": "int",
                "minimum": 0,
            },
            "num_files_ban": {
                "description": "Apply a ban for file counts?",
                "type": "bool",
            },
            "num_files_pm": {
                "description": "Send a message to users below file threshold?",
                "type": "bool",
            },
            "num_files_message": {
                "type": "string",
            },
            # num folder options
            "num_folders": {
                "description": "Minimum number of shared folders:",
                "type": "int",
                "minimum": 0,
            },
            "num_folders_ban": {
                "description": "Apply a ban for folder counts?",
                "type": "bool",
            },
            "num_folders_pm": {
                "description": "Send a message to users below folder threshold?",
                "type": "bool",
            },
            "num_folders_message": {
                "type": "string",
            },
            # percentage options
            "percent_threshold": {
                "description": "Max percentage of locked/private folders:",
                "type": "int",
                "minimum": 1,
                "maximum": 99,
            },
            "percent_threshold_ban": {
                "description": "Apply a ban for locked/private counts?",
                "type": "bool",
            },
            "percent_threshold_pm": {
                "description": "Send a message about locked/private counts?",
                "type": "bool",
            },
            "percent_threshold_message": {
                "type": "string",
            },
            "share_size": {
                "description": "Size of share required:",
                "type": "int",
                "minimum": 0,
                "maximum": 1000,
            },
            "share_size_unit": {
                "description": "Unit of measurement:",
                "type": "dropdown",
                "options": ("MB", "GB"),
            },
            "share_size_ban": {
                "description": "Apply a ban for share sizes?",
                "type": "bool",
            },
            "share_size_pm": {
                "description": "Send a message about share sizes?",
                "type": "bool",
            },
            "share_size_message": {
                "type": "string",
            },
        }
        self.probed_downloaders = {}

    def loaded_notification(self):
        # Use a more consistent approach for populating messages
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
            if not self.settings.get(key):
                self.settings[key] = default_message

        # Ensure settings are within their defined bounds
        self.settings["num_files"] = max(self.settings["num_files"], self.metasettings["num_files"]["minimum"])
        self.settings["num_folders"] = max(self.settings["num_folders"], self.metasettings["num_folders"]["minimum"])
        self.settings["percent_threshold"] = max(self.settings["percent_threshold"], self.metasettings["percent_threshold"]["minimum"])
        self.settings["share_size"] = max(self.settings["share_size"], self.metasettings["share_size"]["minimum"])

        # Use a single function for size conversion
        required_share_bytes = self._convert_size_to_bytes(self.settings["share_size"], self.settings["share_size_unit"])

        self.log(
            "Users require %d files, %d folders with less than %d%% locked and at least %s of data to be shared.",
            self.settings["num_files"],
            self.settings["num_folders"],
            self.settings["percent_threshold"],
            human_size(required_share_bytes),
        )
        self.log(
            "NOTE: This plugin is not endorsed or supported by the Nicotine+ Developers!"
        )

    def _convert_size_to_bytes(self, value, unit):
        """Converts a given size to bytes based on the unit."""
        if unit == "MB":
            return value * MB_IN_BYTES
        elif unit == "GB":
            return value * GB_IN_BYTES
        return 0

    def _convert_bytes_to_unit(self, bytes_value, unit):
        """Converts bytes to the given unit (MB or GB)."""
        if unit == "MB":
            return bytes_value / MB_IN_BYTES
        elif unit == "GB":
            return bytes_value / GB_IN_BYTES
        return 0

    def _handle_user_action(self, user, ban_setting, message_setting, message_text):
        """Helper function to handle banning and messaging users."""
        if ban_setting:
            self.ld_ban_user(user)
        if message_setting and message_text:
            self.ld_message_user(user, AUTO_MESSAGE_PREFIX + message_text)
        elif message_setting:
            self.log("Message configured for this action is empty.")

    def calculate_percentage(self, part, whole):
        """Calculate percentage safely to avoid division by zero."""
        return round((part / whole) * 100) if whole else 0

    def ld_ban_user(self, user):
        """Bans a user and logs the action."""
        self.core.network_filter.ban_user(user)
        self.log(f"User {user} has been banned.")

    def ld_message_user(self, user, message):
        """Messages a user and logs the action."""
        self.send_private(user, message, show_ui=self.settings["open_private_chat"], switch_page=False)
        self.log(f"Message sent to {user} was '{message}'.")

    def upload_queued_notification(self, user, virtual_path, real_path):
        """An upload has been requested."""
        if user in self.probed_downloaders:
            return

        self.probed_downloaders[user] = "downloader"
        self.core.userbrowse.browse_user(user)
        self.log(f"User {user} requested an upload - browsing shares...")

    def user_stats_notification(self, user, stats):
        """Receives and processes stats for a user."""
        if stats.get("private_dirs") is not None:
            # Safely get stats with default values to prevent errors
            files = int(stats.get("files", 0))
            folders = int(stats.get("dirs", 0))
            private_folders = int(stats.get("private_dirs", 0))
            total_shared = int(stats.get("shared_size", 0))

            locked_percent = self.calculate_percentage(private_folders, folders)

            self.log(
                f"User {user} shares {files} files, {folders} folders with {private_folders} private. "
                f"{locked_percent}% of {human_size(total_shared)} is locked."
            )

            if user in self.probed_downloaders:
                self.check_downloader(
                    user,
                    files,
                    folders,
                    private_folders,
                    locked_percent,
                    total_shared,
                )

    def check_downloader(self, user, files, folders, private_folders, locked_percent, total_shared):
        """Performs analysis on a downloader's stats."""
        required_share_bytes = self._convert_size_to_bytes(
            self.settings["share_size"], self.settings["share_size_unit"]
        )
        required_share_human = human_size(required_share_bytes)

        # Check for non-regular sharing conditions first
        if not files and not folders:
            self.log(f"User {user} shares no files or folders.")
            self.core.userbrowse.remove_user(user)
            self._handle_user_action(
                user,
                self.settings["no_files_ban"],
                self.settings["no_files_pm"],
                self.settings["no_files_message"],
            )
            return

        if files > 0 and folders == private_folders:
            self.log(f"User {user} has shares files but all of their folders are private.")
            self.core.userbrowse.remove_user(user)
            self._handle_user_action(
                user,
                self.settings["all_privates_ban"],
                self.settings["all_privates_pm"],
                self.settings["all_privates_message"],
            )
            return

        if not files and folders > 0:
            self.log(f"User {user} shares no files, only empty folders.")
            self.core.userbrowse.remove_user(user)
            self._handle_user_action(
                user,
                self.settings["empty_folders_ban"],
                self.settings["empty_folders_pm"],
                self.settings["empty_folders_message"],
            )
            return

        # Regular sharing conditions
        if files < self.settings["num_files"]:
            self.log(f"User {user} shares {files} files but requires {self.settings['num_files']}.")
            self._handle_user_action(
                user,
                self.settings["num_files_ban"],
                self.settings["num_files_pm"],
                self.settings["num_files_message"],
            )
            return

        if folders < self.settings["num_folders"]:
            self.log(f"User {user} has {folders} folders but requires {self.settings['num_folders']}.")
            self._handle_user_action(
                user,
                self.settings["num_folders_ban"],
                self.settings["num_folders_pm"],
                self.settings["num_folders_message"],
            )
            return

        if locked_percent > self.settings["percent_threshold"]:
            self.log(f"User {user} has {locked_percent}% of folders locked, requires less than {self.settings['percent_threshold']}%.")
            self._handle_user_action(
                user,
                self.settings["percent_threshold_ban"],
                self.settings["percent_threshold_pm"],
                self.settings["percent_threshold_message"],
            )
            return

        if total_shared < required_share_bytes:
            self.log(f"User {user} shares {human_size(total_shared)} but requires {required_share_human}.")
            self._handle_user_action(
                user,
                self.settings["share_size_ban"],
                self.settings["share_size_pm"],
                self.settings["share_size_message"],
            )
            return

        # If all checks pass
        self.probed_downloaders[user] = "OK"
        if user in self.core.buddies.users:
            self.log(f"Buddy {user} is OK.")
        else:
            self.log(f"User {user} is OK.")
