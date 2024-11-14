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
            "send_message": False,
            "open_private_chat": False,
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
        self.probed_downloaders = {}

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

    def upload_queued_notification(self, user, virtual_path, real_path):

        # already know the user is a downloader - ignore
        if user in self.probed_downloaders:
            return

        # a user has requested an upload, log it.
        self.log("[USER] %s requested an upload - asking user for shares...", user)

        # add the user to downloaders dict
        self.probed_downloaders[user] = "downloader"

        # browse user to invoke a user_stats_notification
        self.core.userbrowse.browse_user(user)

    def user_stats_notification(self, user, stats):

        # only process if private_dirs in stats
        # we only get this in our customised userbrowse

        if stats.get("private_dirs") is not None:
            # add user to probed_users dict with a value
            self.probed_users[user] = "processing_stats"
            # convert stats to parameters
            files = int(stats.get("files"))
            folders = int(stats.get("dirs"))
            private_folders = int(stats.get("private_dirs"))
            # count all folders
            total_folders = folders + private_folders
            # calculate locked percentage
            if stats.get("private_dirs"):
                locked_percent = int(round((private_folders / total_folders) * 100))
            else:
                locked_percent = 0
            # clean share size
            if stats.get("shared_size") is not None:
                share_total = int(stats.get("shared_size"))
            else:
                share_total = 0

            # display the users shares
            self.log(
                "[USER] %s shares are: %s files %s folders with %s private. %s percent of %s is locked",
                (
                    user,
                    files,
                    folders,
                    private_folders,
                    locked_percent,
                    human_size(share_total),
                ),
            )

            if user in self.probed_downloaders:
                # user is a downloader, check him
                self.log(
                    "[USER] %s is a downloader - checking...", 
                    (
                        user,
                    ),
                )
                self.check_downloader(user, files, folders, locked_percent)

    def check_downloader(self, user, files, folders, locked_percent):

        # conditions to avoid detection

        if files >= self.settings["num_files"]:
            self.log(
                "[USER] files OK - %s vs %s", 
                (
                    files, 
                    self.settings["num_files"],
                )
            )
        else:
            self.log(
                "[USER] files not OK - %s vs %s", 
                (
                    files, 
                    self.settings["num_files"],
                )
            )

        if folders >= self.settings["num_folders"]:
            self.log(
                "[USER] folders OK - %s vs %s", 
                (
                    folders, 
                    self.settings["num_folders"],
                )
            )
        else:
            self.log(
                "[USER] folders not OK - %s vs %s", 
                (
                    files, 
                    self.settings["num_files"],
                )
            )

        if locked_percent < self.settings["percent_threshold"]:
            self.log(
                "[USER] percentage OK - %s vs %s",
                (
                    locked_percent,
                    self.settings["percent_threshold"],
                )
            )
        else:
            self.log(
                "[USER] percentage not OK - %s vs %s",
                (
                    locked_percent,
                    self.settings["percent_threshold"],
                )
            )

        user_validated = (
            files >= self.settings["num_files"]
            and folders >= self.settings["num_folders"]
            and locked_percent < self.settings["percent_threshold"]
        )

        # when the user meets criteria or is a buddy..
        if user_validated or user in self.core.buddies.users:
            # check if they exist in the leechers list
            if user in self.settings["detected_leechers"]:
                # and remove them
                self.settings["detected_leechers"].remove(user)
                # mark the user as OK
                self.probed_users[user] = "okay"

                # log progress
                if user_validated:
                    self.log("[USER] %s is OK.", user)
                else:
                    self.log("[BUDDY] %s is OK.", user)
                return

        # if we got here, the user is a detected leecher - log progress
        self.log("[DETECTED LEECH] %s is not sharing enough...", user)

        # if messaging turned on
        if self.settings["send_message"] is True:

            # if no message is configured
            if not self.settings["message"]:
                # log it
                self.log(
                    "[DETECTED LEECH] No message sent to %s - not configured in plugin",
                    user,
                )

            # else send the message
            else:
                for line in self.settings["message"].splitlines():
                    for placeholder, option_key in self.PLACEHOLDERS.items():
                        # peplace message placeholders with actual values specified in the plugin settings
                        line = line.replace(placeholder, str(self.settings[option_key]))
                    self.send_private(
                        user,
                        line,
                        show_ui=self.settings["open_private_chat"],
                        switch_page=False,
                    )
                # log progress
                self.log("[DETECTED LEECH] A message was sent to %s", user)

        # add the user to the detected leecher list
        if user not in self.settings["detected_leechers"]:
            self.settings["detected_leechers"].append(user)

        # if a ban is required
        if self.settings["enable_ban"] is True:
            self.core.network_filter.ban_user(user)
            self.log("[DETECTED LEECH] %s has been banned.", user)
