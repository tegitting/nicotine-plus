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
from pynicotine.utils import human_speed


class Plugin(BasePlugin):

    PLACEHOLDERS = {"%files%": "num_files", "%folders%": "num_folders"}

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.settings = {
            "enable_ban": False,
            "send_message": True,
            "open_private_chat": True,
            "message": "Please consider sharing more files if you would like to download from me again. Thanks :)",
            "num_files": 1,
            "num_folders": 1,
            "percent_threshold": 1,
            "detected_leechers": [],
        }
        self.metasettings = {
            "enable_ban": {
                "description": "Ban detected leechers",
                "type": "bool",
            },
            "send_message": {
                "description": "Send a private message to detected leechers",
                "type": "bool",
            },
            "open_private_chat": {
                "description": "Open chat tabs when sending the private messages",
                "type": "bool",
            },
            "message": {
                "description": (
                    "Private chat message to send to leechers. Each line is sent as a separate message, "
                    "too many message lines may get you temporarily banned for spam!"
                ),
                "type": "textview",
            },
            "num_files": {
                "description": "Require users to have a minimum number of shared files:",
                "type": "int",
                "minimum": 0,
            },
            "num_folders": {
                "description": "Require users to have a minimum number of shared folders:",
                "type": "int",
                "minimum": 1,
            },
            "percent_threshold": {
                "description": "Maximum percentage of locked/private folders allowed:",
                "type": "int",
                "minimum": 1,
                "maximum": 99,
            },
            "detected_leechers": {
                "description": "Detected leechers",
                "type": "list string",
            },
        }

        self.probed_users = {}

    def loaded_notification(self):

        min_num_files = self.metasettings["num_files"]["minimum"]
        min_num_folders = self.metasettings["num_folders"]["minimum"]
        percent_allowed = self.metasettings["percent_threshold"]["minimum"]

        if self.settings["num_files"] < min_num_files:
            self.settings["num_files"] = min_num_files

        if self.settings["num_folders"] < min_num_folders:
            self.settings["num_folders"] = min_num_folders

        if self.settings["percent_threshold"] < percent_allowed:
            self.settings["percent_threshold"] = percent_allowed

        self.log(
            "Require users have a minimum of %d files in %d shared public folders.",
            (self.settings["num_files"], self.settings["num_folders"]),
        )
        
    def check_user(self, user, files, folders, private_folders, locked_percent, total):

        if user not in self.probed_users:
            # We are not watching this user
            return

        if self.probed_users[user] == "okay":
            # User was already accepted previously, nothing to do
            return

        if self.probed_users[user] != "downloader":
            self.log(
                "[USER] %s shares are: %s files %s folders with %s private. %s percent of %s is locked",
                (
                    user,
                    files,
                    folders,
                    private_folders,
                    locked_percent,
                    human_size(total),
                ),
            )
            return
            
        # conditions to avoid detection
        is_user_validated = (
            files >= self.settings["num_files"]
            and folders >= self.settings["num_folders"]
            and locked_percent < self.settings["percentage_threshold"]
        )
        # when the user meets criteria or is a buddy
        if is_user_validated or user in self.core.buddies.users:
            # check if they exist in the leechers list
            if user in self.settings["detected_leechers"]:
                # and remove them
                self.settings["detected_leechers"].remove(user)

            # mark the user as OK
            self.probed_users[user] = "okay"

            if is_user_accepted:
                self.log(
                    "[USER] %s is OK. Sharing %s files %s folders with %s private. %s percent of %s is locked",
                    (
                        user,
                        files,
                        folders,
                        private_folders,
                        locked_percent,
                        human_size(total),
                    ),
                )
            else:
                self.log(
                    "[BUDDY] %s has %s files in %s folders with %s private. %s percent of %s is locked.",
                    (
                        user,
                        files,
                        folders,
                        private_folders,
                        locked_percent,
                        human_size(total),
                    ),
                )
            return

        if self.probed_users[user] != "downloader":
            # We already dealt with the user this session
            return

        if user in self.settings["detected_leechers"]:
            # We already messaged the user in a previous session
            self.probed_users[user] = "processed_leecher"
            return
        
        self.probed_users[user] = "pending_leecher"
        log_message = "[DETECTED LEECH] %s has %s files %s folders and %s private. %s percent of %s locked."
        self.log(
            log_message,
            (user, files, folders, private_folders, locked_percent, human_size(total)),
        )

        # no message configured
        if not self.settings["message"]:
            self.log(
                "[DETECTED LEECH] %s doesn't share enough. No message specified in plugin.",
                user,
            )

        # send the configured message
        else:
            for line in self.settings["message"].splitlines():
                for placeholder, option_key in self.PLACEHOLDERS.items():
                    # Replace message placeholders with actual values specified in the plugin settings
                    line = line.replace(placeholder, str(self.settings[option_key]))
                self.send_private(
                    user,
                    line,
                    show_ui=self.settings["open_private_chat"],
                    switch_page=False,
                )
            self.log(
                "[DETECTED LEECH] %s doesn't share enough. A message was sent.", user
            )

        # add the user to the detected leecher list
        if user not in self.settings["detected_leechers"]:
            self.settings["detected_leechers"].append(user)

        # if a ban is required
        if self.settings["enable_ban"] is True:
            self.core.networkfilter.ban_user(user)
            self.log("[DETECTED LEECH] %s has been banned.", user)

        # mark as processed
        self.probed_users[user] = "processed_leecher"

    def upload_queued_notification(self, user, virtual_path, real_path):

        # already probing the user - ignore.
        if user in self.probed_users:
            return

        self.probed_users[user] = "downloader"

        if user not in self.core.users.watched:
            # Transfer manager will request the stats from the server shortly
            return

        # a user has requested an upload, log it.
        self.log("[INFO] Upload requested by %s - asking for users shares...", user)

        # browse user which invokes a user_stats_notification
        self.core.userbrowse.browse_user(user)

    def user_stats_notification(self, user, stats):

        # only process if private_dirs - we only get this in our custom userbrowse
        if stats.get("private_dirs") is not None:
            # cleanup before processing
            files = stats["files"]
            folders = stats["dirs"]
            private_folders = stats["private_dirs"]
            # add up all the folders
            total_folders = folders + private_folders
            # calculate locked percentage
            if private_folders:
                locked_percent = round((private_folders / total_folders) * 100)
            else:
                locked_percent = 0
            share_total = stats["shared_size"]

            # log our progress
            self.log("[INFO] Processing %s shares...", user)

            # invoke check user
            self.check_user(
                user,
                files,
                folders,
                private_folders,
                locked_percent,
                share_total,
            )
