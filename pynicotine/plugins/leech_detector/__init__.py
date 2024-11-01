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


class Plugin(BasePlugin):

    PLACEHOLDERS = {
        "%files%": "num_files",
        "%folders%": "num_folders",
        "%locked%": "percentage_locked"
    }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        url = "https://www.wikihow.com/Avoid-Being-Banned-on-Soulseek"
        self.settings = {
            "message": "To avoid being banned please configure your shares - " + url,
            "open_private_chat": True,
            "num_files": 1,
            "num_folders": 1,
            "percentage_locked": 1,
            "min_shared_size": 1,
            "detected_leechers": []
        }
        self.metasettings = {
            "message": {
                "description": ("Message to send to leechers. Each line is a separate message. Don't Spam!"),
                "type": "textview"
            },
            "open_private_chat": {
                "description": "Open chat tab when sending messages to leechers",
                "type": "bool"
            },
            "num_files": {
                "description": "Require users to have a minimum number of shared files:",
                "type": "int", "minimum": 1
            },
            "num_folders": {
                "description": "Require users to have a minimum number of shared folders:",
                "type": "int", "minimum": 1
            },
            "percentage_locked": {
                "description": "The max percentage of locked/private folders allowed:",
                "type": "int", "minimum": 1, "maximum": 100
            },
            "min_shared_size": {
                "description": "The minimum (MBs) that must be shared by users",
                "type": "int", "minimum": 1
            },
            "detected_leechers": {
                "description": "Detected leechers",
                "type": "list string"
            }
        }

        self.probed_users = {}

    def loaded_notification(self):
        min_num_files = self.metasettings["num_files"]["minimum"]
        min_num_folders = self.metasettings["num_folders"]["minimum"]
        percentage_locked = self.metasettings["percentage_locked"]["minimum"]
        if self.settings["num_files"] < min_num_files:
            self.settings["num_files"] = min_num_files
        if self.settings["num_folders"] < min_num_folders:
            self.settings["num_folders"] = min_num_folders
        if self.settings["percentage_locked"] < percentage_locked:
            self.settings["percentage_locked"] = percentage_locked
        self.log(
            "Users require %d files in %d shared folders and no more than %d percent locked/private.",
            (self.settings["num_files"], self.settings["num_folders"], self.settings["percentage_locked"])
        )

    def check_user(self, user, num_files, num_folders, num_locked_folders, shared_size, source="server"):

        if user not in self.probed_users:
            # We are not watching this user
            return

        if self.probed_users[user] == "okay":
            # User was already accepted previously, nothing to do
            return

        if self.probed_users[user] == "requesting_shares" and source != "peer":
            # Waiting for stats from peer, but received stats from server. Ignore.
            return

        is_user_accepted = (num_files >= self.settings["num_files"] and num_folders >= self.settings["num_folders"])

        if is_user_accepted or user in self.core.buddies.users:
            if user in self.settings["detected_leechers"]:
                self.settings["detected_leechers"].remove(user)

            self.probed_users[user] = "okay"

            if is_user_accepted:
                self.log("[USER] %s OK - %s files %s folders %s locked/private",
                         (user, num_files, num_folders, num_locked_folders))
            else:
                self.log("[BUDDY] %s OK - %s files %s folders %s locked/private",
                         (user, num_files, num_folders, num_locked_folders))
            return

        if not self.probed_users[user].startswith("requesting"):
            # We already dealt with the user this session
            return

        # if user is already in our leechers list
        if user in self.settings["detected_leechers"]:
            # We already messaged the user in a previous session - class as processed
            self.probed_users[user] = "processed_leecher"
            return

        # users stats are empty, check their shares
        if (num_files <= 0 or num_folders <= 0) and self.probed_users[user] != "requesting_shares":
            # SoulseekQt only sends the number of shared files/folders to the server once on startup.
            # Verify user's actual number of files/folders.
            self.log("[USER] %s has no shared files according to the server, requesting shares…", user)
            self.probed_users[user] = "requesting_shares"
            self.core.userbrowse.request_user_shares(user)
            return

        if self.settings["message"]:
            log_message = ("[LEECHER DETECTED] - %s is only sharing %s files in %s folders. Message sent.")
        else:
            log_message = ("[LEECHER DETECTED] - %s is only sharing %s files in %s folders. No message sent.")

        self.probed_users[user] = "pending_leecher"
        self.log(log_message, (user, num_files, num_folders))
        if not self.settings["message"]:
            self.log("[LEECHER] %s doesn't share enough files. No message is specified in plugin settings.", user)
            return

        for line in self.settings["message"].splitlines():
            for placeholder, option_key in self.PLACEHOLDERS.items():
                # Replace message placeholders with actual values specified in the plugin settings
                line = line.replace(placeholder, str(self.settings[option_key]))

            self.send_private(user, line, show_ui=self.settings["open_private_chat"], switch_page=False)

        if user not in self.settings["detected_leechers"]:
            self.settings["detected_leechers"].append(user)
            self.core.network_filter.ban_user(user)

        self.log("[LEECHER] %s doesn't share enough files. Message sent.", user)

    def upload_queued_notification(self, user, virtual_path, real_path):

        if user in self.probed_users:
            return

        self.probed_users[user] = "requesting_stats"

        if user not in self.core.users.watched:
            # Transfer manager will request the stats from the server shortly
            return

        # We've received the user's stats in the past. They could be outdated by
        # now, so request them again.
        self.core.users.request_user_stats(user)

    def user_stats_notification(self, user, stats):
        self.check_user(user, num_files=stats["files"], num_folders=stats["dirs"],
                        num_locked_folders=stats["priv_dirs"], num_shared_size=stats["shared_size"],
                        source=stats["source"])
