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
                locked_percent = int(round((private_folders / total_folders) * 100))
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
                self.check_downloader(user, files, folders, int(locked_percent))

    def check_downloader(self, user, files, folders, locked_percent):

        # conditions to avoid detection
        if files < self.settings["num_files"]:
            self.log(
                "User %s failed file check - has %s vs %s required",
                (
                    user,
                    files,
                    self.settings["num_files"],
                ),
            )

        if folders < self.settings["num_folders"]:
            self.log(
                "User %s failed folder check - has %s vs %s required",
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
            else:
                self.log("User %s is OK.", user)
                return

        # stats are not good
        else:
            # the user is a detected leecher - log progress
            self.log("User %s is not sharing enough...", user)

            # if messaging turned on
            if self.settings["send_message"] == True:

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
