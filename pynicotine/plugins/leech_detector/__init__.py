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
            "share_size_unit": "MB",
            "send_message": False,
            "open_private_chat": False,
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
                "description": "Enforce share sizes:",
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
                "options": ("MB", "GB"),
            },
            "send_message": {
                "description": "Send a private message to detected leechers?",
                "type": "bool",
            },
            "open_private_chat": {
                "description": "Open chat tabs when sending messages?",
                "type": "bool",
            },
            "enable_ban": {
                "description": "Apply a ban to detected users?",
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

        self.log(
            "NOTE: This plugin is not endorsed or supported by the Nicotine+ Developers!"
        )
        self.log(
            "Users require %d files, %d folders with less than %d"
            + "%% locked and at least %s"
            + "%s of data to be shared.",
            (
                self.settings["num_files"],
                self.settings["num_folders"],
                self.settings["percent_threshold"],
                self.settings["share_size"],
                self.settings["share_size_unit"],
            ),
        )

    # convert bytes to mbs
    def convert_bytes_to_megs(self, bytes_value):
        return round(bytes_value / 1048576)

    # convert bytes to gbs
    def convert_bytes_to_gigs(self, bytes_value):
        return round(bytes_value / 1073741824)

    # function to calculate percentage
    def calculate_percentage(self, part, whole):
        percent = round((part / whole) * 100)
        return percent

    # an upload has been requested
    def upload_queued_notification(self, user, virtual_path, real_path):
        # user already dealt with
        if user in self.probed_downloaders:
            return
        # record the user as a downloader
        self.probed_downloaders[user] = "downloader"

        # browse user to invoke a user_stats_notification
        self.core.userbrowse.browse_user(user)
        # log it
        self.log("User %s requested an upload - browsing shares...", user)

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

            # prevent any division by zero error
            if folders:
                locked_percent = self.calculate_percentage(private_folders, folders)
            else:
                locked_percent = 0

            # log progress and display the users shares
            self.log(
                "User %s shares %s files %s folders with %s private. %s percent of %s is locked",
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
                # then perform some analysis on the stats
                self.check_downloader(
                    user,
                    files,
                    folders,
                    private_folders,
                    int(locked_percent),
                    total_shared,
                )

    # check the
    def check_downloader(
        self, user, files, folders, private_folders, locked_percent, total_shared
    ):

        # convert share size to the chosen conversion metric
        if self.settings["share_size_unit"] == "MB":
            converted_share = self.convert_bytes_to_megs(int(total_shared))

        # convert share size to the chosen conversion metric
        if self.settings["share_size_unit"] == "GB":
            converted_share = self.convert_bytes_to_gigs(int(total_shared))

        # if stats are good
        if (
            files >= self.settings["num_files"]
            and folders >= self.settings["num_folders"]
            and locked_percent < self.settings["percent_threshold"]
            and converted_share > self.settings["share_size"]
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
        # user is not sharing anything
        if not files and not folders:
            self.log("User %s no files or folders.", user)
            ban_reason = "[Auto-Message] You are not sharing any files"
            self.ban_with_reason(user, ban_reason)
            return

        # user has files but all folders are locked/private
        if files > 0 and folders == private_folders:
            self.log(
                "User %s has shared files but all of their folders are private.", user
            )
            ban_reason = "[Auto-Message] All your files are private"
            self.ban_with_reason(user, ban_reason)
            return

        # user no files but only empty folders
        if not files and folders > 0:
            self.log("User %s no files, only empty folders", user)
            ban_reason = "[Auto-Message] All your shared folders are empty"
            self.ban_with_reason(user, ban_reason)
            return

        # begin some checks & logs
        # files check
        if files <= self.settings["num_files"]:
            self.log(
                "User %s shares %s files but the plugin requires %s",
                (
                    user,
                    files,
                    self.settings["num_files"],
                ),
            )
            # is messaging enabled?
            if self.settings["send_message"] is True:
                file_msg = "[Auto-Message] Please consider adding more shared files"
                self.send_private(
                    user,
                    file_msg,
                    show_ui=self.settings["open_private_chat"],
                    switch_page=False,
                )

        # folder check
        if folders < self.settings["num_folders"]:
            self.log(
                "User %s has %s folders but the plugin requires %s",
                (
                    user,
                    folders,
                    self.settings["num_folders"],
                ),
            )
            # is messaging enabled?
            if self.settings["send_message"] is True:
                folder_msg = "[Auto-Message] Please consider adding more shared folders"
                self.send_private(
                    user,
                    folder_msg,
                    show_ui=self.settings["open_private_chat"],
                    switch_page=False,
                )

        if locked_percent > self.settings["percent_threshold"]:
            self.log(
                "User %s has %s" + "%% of folders locked, plugin requires less than %s",
                (
                    user,
                    locked_percent,
                    self.settings["percent_threshold"],
                ),
            )
            # is messaging enabled?
            if self.settings["send_message"] is True:
                percent_msg = "[Auto-Message] You have too many locked/private files."
                self.send_private(
                    user,
                    percent_msg,
                    show_ui=self.settings["open_private_chat"],
                    switch_page=False,
                )

        # share size
        if converted_share < self.settings["share_size"]:
            self.log(
                "User %s shares %s but the plugin requires %s" + "%s",
                (
                    user,
                    human_size(total_shared),
                    self.settings["share_size"],
                    self.settings["share_unit"],
                ),
            )
            # is messaging enabled?
            if self.settings["send_message"] is True:
                data_msg = "[Auto-Message] Please consider sharing more data"
                self.send_private(
                    user,
                    data_msg,
                    show_ui=self.settings["open_private_chat"],
                    switch_page=False,
                )

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
            "User %s has been banned. Message sent: %s",
            (
                user,
                reason,
            ),
        )
