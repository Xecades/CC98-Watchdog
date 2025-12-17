import os
import re

import requests
import urllib3
from dotenv import load_dotenv
from loguru import logger as L

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CC98Client:
    """
    A client for interacting with the CC98 Forum API.
    Handles authentication and provides methods for common operations.
    """

    API_BASE_URL = "https://api.cc98.org"
    OPENID_BASE_URL = "https://openid.cc98.org"
    WWW_BASE_URL = "https://www.cc98.org"

    def __init__(self):
        load_dotenv()
        self.username = os.getenv("CC98_USERNAME")
        self.password = os.getenv("CC98_PASSWORD")

        if not self.username or not self.password:
            raise ValueError("Please set CC98_USERNAME and CC98_PASSWORD in .env file")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

        self.client_id = None
        self.client_secret = None

        self.access_token = None
        self.refresh_token = None

        self.board_map = {}

        # Try to fetch dynamic credentials
        self._update_credentials_from_web()

    def _refresh_board_map(self):
        """
        Fetch all boards and build a map of board_id -> board_name.
        """
        L.info("Refreshing board map...")
        try:
            root_boards = self.get_all_boards()
            for root in root_boards:
                # Map root board itself if needed, though usually we post in sub-boards
                self.board_map[root.get("id")] = root.get("name")

                # Map sub-boards
                for board in root.get("boards", []):
                    self.board_map[board.get("id")] = board.get("name")
            L.info(f"Board map refreshed. Found {len(self.board_map)} boards.")
        except Exception as e:
            L.error(f"Failed to refresh board map: {e}")

    def get_board_name(self, board_id):
        """
        Get board name by ID. Refreshes map if not found.
        """
        if not self.board_map:
            self._refresh_board_map()

        name = self.board_map.get(board_id)
        if not name:
            # Try refreshing once more if not found
            self._refresh_board_map()
            name = self.board_map.get(board_id)

        return name or f"Unknown Board ({board_id})"

    def _update_credentials_from_web(self):
        """
        Dynamically fetch the latest client_id and client_secret from the CC98 frontend.
        """
        L.info("Fetching latest credentials from CC98...")
        try:
            response = self.session.get(self.WWW_BASE_URL)
            if response.status_code != 200:
                L.error("Failed to load CC98 homepage.")
                return

            match = re.search(r"(main-[a-f0-9]+\.js)", response.text)
            if not match:
                L.error("Could not find main JS filename in page source.")
                return

            js_filename = match.group(1)
            js_url = f"{self.WWW_BASE_URL}/static/scripts/{js_filename}"
            L.info(f"Found JS bundle: {js_url}")

            js_response = self.session.get(js_url)
            if js_response.status_code != 200:
                L.error("Failed to load JS bundle.")
                return

            content = js_response.text
            id_match = re.search(r'client_id\s*[:=]\s*["\']([^"\']+)["\']', content)
            secret_match = re.search(r'client_secret\s*[:=]\s*["\']([^"\']+)["\']', content)

            if id_match and secret_match:
                self.client_id = id_match.group(1)
                self.client_secret = secret_match.group(1)
                L.info("Credentials found!")
            else:
                L.error("Could not parse credentials from JS.")

        except Exception as e:
            L.error(f"Error fetching dynamic credentials: {e}")

    def login(self):
        """
        Log in to CC98 using OAuth2 Password Grant.
        """
        if not self.client_id or not self.client_secret:
            L.error("Client ID or Secret not found. Cannot login.")
            return False

        L.info("Attempting to login via OAuth2 Password Grant...")
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
                "scope": "cc98-api openid offline_access",
            }

            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            token_url = f"{self.OPENID_BASE_URL}/connect/token"

            response = self.session.post(token_url, data=data, headers=headers, verify=False)

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                self.refresh_token = token_data.get("refresh_token")
                L.info("Login successful!")

                self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
                return True
            else:
                L.error(f"Login failed. Status: {response.status_code}")
                L.error(f"Response: {response.text}")
                return False

        except Exception as e:
            L.error(f"Login error: {e}")
            return False

    def get(self, endpoint, params=None):
        """
        Helper method to make GET requests to the API.
        """
        url = f"{self.API_BASE_URL}{endpoint}"
        return self.session.get(url, params=params)

    def get_me(self):
        """
        Get current user information.
        """
        response = self.get("/me")
        if response.status_code == 200:
            return response.json()
        return None

    def get_topics(self, board_id, from_index=0, size=20):
        """
        Get topics from a specific board.
        """
        params = {"from": from_index, "size": size}
        response = self.get(f"/board/{board_id}/topic", params=params)
        if response.status_code == 200:
            return response.json()
        return []

    def get_new_topics(self, from_index=0, size=20):
        """
        Get new topics from all boards.
        """
        params = {"from": from_index, "size": size}
        response = self.get("/topic/new", params=params)
        if response.status_code == 200:
            return response.json()
        return []

    def get_topic(self, topic_id):
        """
        Get topic information.
        """
        response = self.get(f"/topic/{topic_id}")
        if response.status_code == 200:
            return response.json()
        return None

    def get_posts(self, topic_id, from_index=0, size=10):
        """
        Get posts from a specific topic.
        """
        params = {"from": from_index, "size": size}
        response = self.get(f"/topic/{topic_id}/post", params=params)
        if response.status_code == 200:
            return response.json()
        return []

    def get_all_boards(self):
        """
        Get all boards hierarchy.
        """
        response = self.get("/board/all")
        if response.status_code == 200:
            return response.json()
        return []
