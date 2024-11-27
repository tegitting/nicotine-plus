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

    PLACEHOLDERS = {
        "%files%": "num_files",
        "%folders%": "num_folders",
        "%percent%": "percent_threshold",
    }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.settings = {
            "num_files": 1,
            "num_folders": 1,
            "percent_threshold": 1,
            "enforce_share_size": False,
            "share_size": 1,
            "share_size_unit": "Megabytes",
            "send_message": False,
            "open_private_chat": False,
            "message": "Please consider sharing more files if you would like to download from me again. Thanks :)",
            "enable_ban": False,
            "detected_leechers": [],
        }
        self.metasettings = {
            "num_files": {
                "description": "Minimum number of shared files:",
                "type": "int",
                "minimum": 1,
            },
            "num_folders": {
                "description": "Minimum number of shared folders:",
                "type": "int",
                "minimum": 1,
            },
            "percent_threshold": {
                "description": "Allowed percentage of locked/private folders:",
                "type": "int",
                "minimum": 1,
                "maximum": 99,
            },
            "enforce_share_size": {
                "description": "Enforce share sizes?",
                "type": "bool",
            },
            "share_size": {
                "description": "Size of share required:",
                "type": "int",
                "minimum": 1,
                "maximum": 1000,
            },
            "share_size_unit": {
                "description": "Unit of measurement:",
                "type": "dropdown",
                "options": ("Megabytes", "Gigabytes"),
            },
            "send_message": {
                "description": "Send a private message to detected leechers?",
                "type": "bool",
            },
            "open_private_chat": {
                "description": "Open chat tabs when sending the private messages?",
                "type": "bool",
            },
            "message": {
                "description": (
                    "Private chat message to send to leechers. Each line is sent as a separate message, "
                    "too many message lines may get you temporarily banned for spam!"
                ),
                "type": "textview",
            },
            "enable_ban": {
                "description": "Apply a ban to detected leechers?",
                "type": "bool",
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
        share_size = self.metasettings["share_size"]["minimum"]

        if self.settings["num_files"] < min_num_files:
            self.settings["num_files"] = min_num_files

        if self.settings["num_folders"] < min_num_folders:
            self.settings["num_folders"] = min_num_folders

        if self.settings["percent_threshold"] < percent_allowed:
            self.settings["percent_threshold"] = percent_allowed

        if self.settings["share_size"] < share_size:
            self.settings["share_size"] = share_size

    # convert bytes to mbs
    def convert_bytes_to_mbs(self, bytes_value):
        return round(bytes_value / 1048576)

    # convert bytes to gbs
    def convert_bytes_to_gbs(self, bytes_value):
        return round(bytes_value / 1073741824)

    # function to calculate percentage
    def calculate_percentage(self, part, whole):
        percent = (part / whole) * 100
        return percent

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
        # only process the notification when private_dirs is in stats
        # we only get this in our customised userbrowse function
        if stats.get("private_dirs") is not None:
            # create dictionary entry
            self.probed_users[user] = "processing"
            files = int(stats.get("files"))
            folders = int(stats.get("dirs"))
            private_folders = int(stats.get("private_dirs"))
            total_shared = int(stats.get("shared_size"))
            total_folders = folders + private_folders

            # prevent any division by zero error
            if total_folders != 0:
                # locked_percent = self.calculate_percentage(private_folders, int(total_folders))
                locked_percent = (private_folders / total_folders) * 100
                locked_percent = round(locked_percent)
            else:
                locked_percent = 0

            # display the users shares
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

            # if the user is a downloader
            if user in self.probed_downloaders:
                # log progress
                self.log("User %s is a downloader. Checking stats...", user)
                # then perform some analysis on the stats
                self.check_downloader(
                    user,
                    files,
                    folders,
                    private_folders,
                    int(locked_percent),
                    total_shared,
                )

    def check_downloader(
        self, user, files, folders, private_folders, locked_percent, total_shared
    ):

        if self.settings["share_size_unit"] == "Megabytes":
            self.convert_bytes_to_mbs(total_shared)

        if self.settings["share_size_unit"] == "Gigabytes":
            self.convert_bytes_to_gbs(total_shared)

        total_shared = self.convert_bytes(total_shared)
        # log progress
        # filecount
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
        # folder counts
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
        # percentage
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
        # share size
        if total_shared > self.settings["share_size"]:
            self.log(
                "User %s failed %s share size check - has %s vs %s required",
                (
                    user,
                    self.settings["share_size_unit"],
                    total_shared,
                    self.settings["share_size"],
                ),
            )
        else:
            self.log(
                "User %s passed %s share size check - has %s vs %s required",
                (
                    user,
                    self.settings["share_size_unit"],
                    total_shared,
                    self.settings["share_size"],
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
        # else:
        # the user is a detected leecher - log progress
        self.log("User %s is not sharing enough...", user)

        # user has files but all folders are locked/private
        if files > 0 and folders == private_folders:
            ban_reason = """[AUTO-MESSAGE] You cannot download from me when your files are private."""
            self.ban_with_reason(user, ban_reason)
            return

        # user is not sharing - send the wikihow link
        if not files and not folders:
            ban_reason = """[AUTO-MESSAGE] You cannot download from me when you are not sharing any files."""
            self.ban_with_reason(user, ban_reason)
            return

        # user trys to avoid being detected by regular slsk client by adding an empty directory
        if not files and folders > 0:
            ban_reason = """[AUTO-MESSAGE] You cannot download from me when your shared folders are empty."""
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

    def ban_with_reason(self, user, reason):
        self.core.network_filter.ban_user(user)
        self.send_private(
            user,
            reason,
            show_ui=self.settings["open_private_chat"],
            switch_page=False,
        )
        self.log(
            "User %s has been banned. The message sent was %s",
            (
                user,
                reason,
            ),
        )
