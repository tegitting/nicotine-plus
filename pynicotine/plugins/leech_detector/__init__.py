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
                "minimum": 2,
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

    # function to calculate percentage
    def calculate_percentage(self, part, whole):
        percent = (part / whole) * 100
        return round(percent)

    # an upload has been requested
    def upload_queued_notification(self, user, virtual_path, real_path):
        # user already dealt with
        if user in self.probed_downloaders:
            return
        # record the user as a downloader
        self.probed_downloaders[user] = "downloader"
        # a user has requested an upload, log it.
        self.log("User %s requested an upload - browsing users shares...", user)
        # browse user to invoke a user_stats_notification
        self.core.userbrowse.browse_user(user)

    # receive stats for a user
    def user_stats_notification(self, user, stats):
        # only process the notification if private_dirs in stats
        # we only get this in our customised userbrowse
        if stats.get("private_dirs") is not None:
            # create dictionary entry
            self.probed_users[user] = "processing"
            files = int(stats.get("files"))
            folders = int(stats.get("dirs"))
            private_folders = int(stats.get("private_dirs"))
            total_shared = int(stats.get("shared_size"))
            total_folders = folders + private_folders
            # catch division by zero error and only divide when total_folders is not 0
            if total_folders != 0:
                # locked_percent = self.calculate_percentage(private_folders, int(total_folders))
                locked_percent = round((private_folders / total_folders) * 100)
            else:
                locked_percent = 0

            # display the users shares / log progress
            self.log(
                "User %s shares are: %s files %s folders with %s private. %s percent of %s is locked",
                (
                    user,
                    files,
                    folders,
                    private_folders,
                    locked_percent,
                    human_size(total_shared),
                ),
            )

            # since user is downloader, check stats
            if user in self.probed_downloaders:
                # user is a downloader, check him
                self.log("User %s is a downloader. Checking stats...", user)
                self.check_downloader(
                    user,
                    files,
                    folders,
                    private_folders,
                    int(locked_percent),
                    total_shared,
                )

    def ban_with_reason(self, user, reason):
        self.core.network_filter.ban_user(user)
        self.send_private(
            user,
            reason,
            show_ui=self.settings["open_private_chat"],
            switch_page=False,
        )
        self.log("User %s has been banned and a message was sent.", user)

    def check_downloader(self, user, files, folders, private_folders, locked_percent, total_shared):

        # log progress START
        if files <= self.settings["num_files"]:
            self.log(
                "User %s failed file check - has %s vs %s required",
                (
                    user,
                    files,
                    self.settings["num_files"],
                ),
            )
        else:
            self.log(
                "User %s passed file check - has %s vs %s required",
                (
                    user,
                    files,
                    self.settings["num_files"],
                ),
            )

        if folders <= self.settings["num_folders"]:
            self.log(
                "User %s failed folder check - has %s vs %s required",
                (
                    user,
                    folders,
                    self.settings["num_folders"],
                ),
            )
        else:
            self.log(
                "User %s passed folder check - has %s vs %s required",
                (
                    user,
                    folders,
                    self.settings["num_folders"],
                ),
            )

        if locked_percent > self.settings["percent_threshold"]:
            self.log(
                "User %s failed locked percentage check - %s vs %s",
                (
                    user,
                    locked_percent,
                    self.settings["percent_threshold"],
                ),
            )
        else:
            self.log(
                "User %s passed percentage check - %s vs %s",
                (
                    user,
                    locked_percent,
                    self.settings["percent_threshold"],
                ),
            )
            # log progress END

        # if stats are good
        if (
            files >= self.settings["num_files"]
            and folders >= self.settings["num_folders"]
            and locked_percent < self.settings["percent_threshold"]
        ):
            # mark the user as OK
            self.probed_downloaders[user] = "OK"

            # if they exist in the leechers list
            if user in self.settings["detected_leechers"]:
                # and remove them
                self.settings["detected_leechers"].remove(user)

            # log progress
            if user in self.core.buddies.users:
                self.log("Buddy %s is OK.", user)
                return
            self.log("User %s is OK.", user)
            return

        # stats are not good
        else:
            # the user is a detected leecher - log progress
            self.log("User %s is not sharing enough...", user)
            
            if files > 0 and folders == private_folders:
                ban_reason = """[AUTO-MESSAGE] You tried to download from me but all your files are private. 
Because of this you are banned."""
                self.ban_with_reason(user, ban_reason)
                return
                
            if files == 0 and folders == 0:
                ban_reason = """[AUTO-MESSAGE] You tried to download from me but you are not sharing any files. 
https://www.wikihow.com/Avoid-Being-Banned-on-Soulseek"""
                self.ban_with_reason(user, ban_reason)
                return
                
            if files == 0 and folders == 1:
                ban_reason = """[AUTO-MESSAGE] You tried to download from me but you have 0 files and 1 empty folder. 
You know how to add shared folders but chose to share one with 0 files. Now you are banned."""
                self.ban_with_reason(user, ban_reason)
                return

            # if messaging turned on
            if self.settings["send_message"] is True:

                # if no message is configured
                if not self.settings["message"]:
                    # log it
                    self.log(
                        "User %s is leeching, no message configured in plugin",
                        user,
                    )

                # else send the message
                else:
                    for line in self.settings["message"].splitlines():
                        for placeholder, option_key in self.PLACEHOLDERS.items():
                            # peplace message placeholders with actual values specified in the plugin settings
                            line = line.replace(
                                placeholder, str(self.settings[option_key])
                            )
                        self.send_private(
                            user,
                            line,
                            show_ui=self.settings["open_private_chat"],
                            switch_page=False,
                        )
                    # log progress
                    self.log("User %s is leeching - a message was sent", user)

            # add the user to the detected leecher list
            if user not in self.settings["detected_leechers"]:
                self.settings["detected_leechers"].append(user)
            # if a ban is required
            if self.settings["enable_ban"] is True:
                self.core.network_filter.ban_user(user)
                self.log("User %s has been banned", user)
