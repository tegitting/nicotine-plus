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

    # plugin loaded notifications
    def loaded_notification(self):
        min_num_files = self.metasettings["num_files"]["minimum"]
        min_num_folders = self.metasettings["num_folders"]["minimum"]
        percent_allowed = self.metasettings["percent_threshold"]["minimum"]
        share_size = self.metasettings["share_size"]["minimum"]
        req_share = 0

        # try and populate the text boxes
        if not self.settings["no_files_message"]:
            self.settings["no_files_message"] = "You need shared files to download from me"

        if not self.settings["all_privates_message"]:
            self.settings["all_privates_message"] = "You cannot download from me when your files are all private"

        if not self.settings["empty_folders_message"]:
            self.settings["empty_folders_message"] = "You cannot download from me when your shared folders are empty"

        if not self.settings["num_files_message"]:
            self.settings["num_files_message"] = "Please consider adding more shared files"

        if not self.settings["num_folders_message"]:
            self.settings["num_folders_message"] = "Please consider having more shared folders"

        if not self.settings["percent_threshold_message"]:
            self.settings["percent_threshold_message"] = "You have too many locked/private folders"

        if not self.settings["share_size_message"]:
            self.settings["share_size_message"] = "You are not sharing enough media"

        if self.settings["num_files"] < min_num_files:
            self.settings["num_files"] = min_num_files

        if self.settings["num_folders"] < min_num_folders:
            self.settings["num_folders"] = min_num_folders

        if self.settings["percent_threshold"] < percent_allowed:
            self.settings["percent_threshold"] = percent_allowed

        if self.settings["share_size"] < share_size:
            self.settings["share_size"] = share_size

        if self.settings["share_size_unit"] == "MB":
            req_share = human_size(self.convert_megs_to_bytes(self.settings["share_size"]))

        if self.settings["share_size_unit"] == "GB":
            req_share = human_size(self.convert_gigs_to_bytes(self.settings["share_size"]))

        self.log(
            "Users require %d files, %d folders with less than %d"
            + "%% locked and at least %s of data to be shared.",
            (
                self.settings["num_files"],
                self.settings["num_folders"],
                self.settings["percent_threshold"],
                req_share,
            ),
        )
        self.log(
            "NOTE: This plugin is not endorsed or supported by the Nicotine+ Developers!"
        )

    # convert bytes to mbs
    def convert_bytes_to_megs(self, bytes_value):
        return round(bytes_value / 1048576)

    # convert bytes to gbs
    def convert_bytes_to_gigs(self, bytes_value):
        return round(bytes_value / 1073741824)

    # convert megs to bytes
    def convert_megs_to_bytes(self, megs_value):
        return megs_value * 1048576

    # convert gigs to bytes
    def convert_gigs_to_bytes(self, gigs_value):
        return gigs_value * 1073741824

    # function to calculate percentage
    def calculate_percentage(self, part, whole):
        percent = round((part / whole) * 100)
        return percent

    # ban a user
    def ld_ban_user(self, user):
        self.core.network_filter.ban_user(user)
        self.log("User %s has been banned", user)

    # message a user
    def ld_message_user(self, user, message):
        self.send_private(user, message, show_ui=self.settings["open_private_chat"], switch_page=False)
        # log what we sent
        self.log(
            "Message sent to %s was %s",
            (
                user,
                message,
            ),
        )

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
        # we only get this in the customised userbrowse function
        if stats.get("private_dirs") is not None:
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

        required_share = 0
        converted_share = 0
        # convert share size to the chosen conversion metric
        if self.settings["share_size_unit"] == "MB":
            converted_share = self.convert_bytes_to_megs(int(total_shared))
            required_share = self.convert_megs_to_bytes(self.settings["share_size"])
        # convert share size to the chosen conversion metric
        if self.settings["share_size_unit"] == "GB":
            converted_share = self.convert_bytes_to_gigs(int(total_shared))
            required_share = self.convert_gigs_to_bytes(self.settings["share_size"])

        # check stats
        if (
            files >= self.settings["num_files"]
            and folders >= self.settings["num_folders"]
            and locked_percent < self.settings["percent_threshold"]
            and converted_share > self.settings["share_size"]
        ):
            # stats are goo - mark the user as OK
            self.probed_downloaders[user] = "OK"

            # log progress
            if user in self.core.buddies.users:
                self.log("Buddy %s is OK.", user)
                return
            self.log("User %s is OK.", user)
            return

        # non-regular sharing conditions
        # user is not sharing anything
        if not files and not folders:
            self.log("User %s shares no files or folders.", user)
            # close down the tab for the browsed user
            self.core.userbrowse.remove_user(user)
            # if a ban is required
            if self.settings["no_files_ban"] is True:
                self.ld_ban_user(user)
            if self.settings["no_files_pm"] is True:
                if not self.settings["no_files_message"]:
                    self.log("[NO-FILES] There is no message configured in plugin")
                else:
                    message = "[Auto-Message] " + self.settings["no_files_message"]
                    self.ld_message_user(user, message)
            return

        # user has files but all folders are locked/private
        if files > 0 and folders == private_folders:
            self.log("User %s has shares files but all of their folders are private.", user)
            # close down the tab for the browsed user
            self.core.userbrowse.remove_user(user)
            # if a ban is required
            if self.settings["all_privates_ban"] is True:
                self.ld_ban_user(user)
            if self.settings["all_privates_pm"] is True:
                if not self.settings["all_privates_message"]:
                    self.log("[ALL-PRIVATES] - There is no message configured in plugin")
                else:
                    message = "[Auto-Message] " + self.settings["all_privates_message"]
                    self.ld_message_user(user, message)
            return

        # user no files but has empty shared folders
        if not files and folders > 0:
            self.log("User %s shares no files, only empty folders.", user)
            # close down the tab for the browsed user
            self.core.userbrowse.remove_user(user)
            # if a ban is required
            if self.settings["empty_folders_ban"] is True:
                self.ld_ban_user(user)
            if self.settings["empty_folders_pm"] is True:
                if not self.settings["empty_folders_message"]:
                    self.log("[ALL-PRIVATES] - There is no message configured in plugin")
                else:
                    message = "[Auto-Message] " + self.settings["empty_folders_message"]
                    self.ld_message_user(user, message)
            return

        # regular sharing conditions
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
            # is banning enabled?
            if self.settings["num_files_ban"] is True:
                self.ld_ban_user(user)
            # is messaging enabled?
            if self.settings["num_files_pm"] is True:
                if not self.settings["num_files_message"]:
                    self.log("[FILE-COUNT] - There is no message configured in plugin")
                else:
                    message = "[Auto-Message] " + self.settings["num_files_message"]
                    self.ld_message_user(user, message)
            return

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
            # is ban enabled?
            if self.settings["num_folders_ban"] is True:
                self.ld_ban_user(user)
            # is messaging enabled?
            if self.settings["num_folders_pm"] is True:
                if not self.settings["num_folders_message"]:
                    self.log("[FOLDER-COUNT] - There is no message configured in plugin")
                else:
                    message = "[Auto-Message] " + self.settings["num_folders_message"]
                    self.ld_message_user(user, message)
            return

        # percentage check
        if locked_percent > self.settings["percent_threshold"]:
            self.log(
                "User %s has %s" + "%% of folders locked, plugin requires less than %s",
                (
                    user,
                    locked_percent,
                    self.settings["percent_threshold"],
                ),
            )
            # is ban enabled?
            if self.settings["percent_threshold_ban"] is True:
                self.ld_ban_user(user)
            # is messaging enabled?
            if self.settings["percent_threshold_pm"] is True:
                if not self.settings["percent_threshold_message"]:
                    self.log("[LOCKED-PERCENT] - There is no message configured in plugin")
                else:
                    message = "[Auto-Message] " + self.settings["percent_threshold_message"]
                    self.ld_message_user(user, message)
            return

        # share size check
        if converted_share < self.settings["share_size"]:
            self.log(
                "User %s shares %s but the plugin requires %s",
                (
                    user,
                    human_size(total_shared),
                    human_size(required_share),
                ),
            )
            # is ban enabled?
            if self.settings["share_size_ban"] is True:
                self.ld_ban_user(user)
            # is messaging enabled?
            if self.settings["share_size_pm"] is True:
                if not self.settings["share_size_message"]:
                    self.log("[SHARE-SIZE] - There is no message configured in plugin")
                else:
                    message = "[Auto-Message] " + self.settings["share_size_message"]
                    self.ld_message_user(user, message)
            return
