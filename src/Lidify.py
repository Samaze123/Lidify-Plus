import json
import time
import logging
import os
import random
import string
import threading
import urllib.parse
from logging import Logger

from flask import Flask, render_template, request
from flask_socketio import SocketIO
import requests
import musicbrainzngs
from thefuzz import fuzz
from unidecode import unidecode
import pylast
from dotenv import load_dotenv

from src.functions.formar_numbers import format_numbers

load_dotenv()



class DataHandler:
    def __init__(self):
        # Initialize variables
        self.LIDARR_API_TIMEOUT:float = 0
        self.FALLBACK_TO_TOP_RESULT:bool = False
        self.settings_config_file:str = ""
        self.ROOT_FOLDER_PATH:str = ""
        self.LIDARR_API_KEY:str = ""
        self.LIDARR_ADDRESS:str = ""
        self.full_lidarr_artist_list:list = []

        logging.basicConfig(level=logging.INFO, format="%(message)s")
        self.lidify_logger:Logger = logging.getLogger()
        self.musicbrainzngs_logger = logging.getLogger("musicbrainzngs")
        self.musicbrainzngs_logger.setLevel("WARNING")
        self.pylast_logger = logging.getLogger("pylast")
        self.pylast_logger.setLevel("WARNING")

        app_name_text = os.path.basename(__file__).replace(".py", "")
        release_version = os.environ.get("RELEASE_VERSION", "unknown")
        self.lidify_logger.warning(f"{'*' * 50}\n")
        self.lidify_logger.warning(f"{app_name_text} Version: {release_version}\n")
        self.lidify_logger.warning(f"{'*' * 50}")

        self.search_in_progress_flag = False
        self.new_found_artists_counter = 0
        self.clients_connected_counter = 0
        self.config_folder = "config"
        self.recommended_artists = []
        self.lidarr_items = []
        self.cleaned_lidarr_items = []
        self.stop_event = threading.Event()
        self.stop_event.set()
        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)
        self.load_environ_or_config_settings()
        if self.AUTO_START:
            try:
                auto_start_thread = threading.Timer(self.AUTO_START_DELAY, self.automated_startup)
                auto_start_thread.daemon = True
                auto_start_thread.start()

            except Exception as e:
                self.lidify_logger.error(f"Auto Start Error: {str(e)}")

    def load_environ_or_config_settings(self):
        # Defaults
        default_settings = {
            "LIDARR_ADDRESS": "http://lidarr:8686",
            "LIDARR_API_KEY": "",
            "ROOT_FOLDER_PATH": "/data/media/music/",
            "FALLBACK_TO_TOP_RESULT": False,
            "LIDARR_API_TIMEOUT": 120.0,
            "QUALITY_PROFILE_ID": 1,
            "METADATA_PROFILE_ID": 1,
            "SEARCH_FOR_MISSING_ALBUMS": False,
            "DRY_RUN_ADDING_TO_LIDARR": False,
            "app_name": "Lidify",
            "APP_REV": "0.10",
            "APP_URL": f"http://{"".join(random.choices(string.ascii_lowercase, k=10))}.com",
            "LAST_FM_API_KEY": "",
            "LAST_FM_API_SECRET": "",
            "MODE": "LastFM",
            "AUTO_START": False,
            "AUTO_START_DELAY": 60,
        }

        # Load settings from environmental variables (which take precedence) over the configuration file.
        self.LIDARR_ADDRESS = os.environ.get("LIDARR_ADDRESS", "")
        self.LIDARR_API_KEY = os.environ.get("LIDARR_API_KEY", "")
        self.LIDARR_API_TIMEOUT = float(os.environ.get("LIDARR_API_TIMEOUT", ""))
        self.ROOT_FOLDER_PATH = os.environ.get("ROOT_FOLDER_PATH", "")

        self.FALLBACK_TO_TOP_RESULT = os.environ.get("FALLBACK_TO_TOP_RESULT", "").lower() == "true"
        QUALITY_PROFILE_ID = os.environ.get("QUALITY_PROFILE_ID", "")
        self.QUALITY_PROFILE_ID = int(QUALITY_PROFILE_ID) if QUALITY_PROFILE_ID else ""
        METADATA_PROFILE_ID = os.environ.get("METADATA_PROFILE_ID", "")
        self.METADATA_PROFILE_ID = int(METADATA_PROFILE_ID) if METADATA_PROFILE_ID else ""
        SEARCH_FOR_MISSING_ALBUMS = os.environ.get("SEARCH_FOR_MISSING_ALBUMS", "")
        self.SEARCH_FOR_MISSING_ALBUMS = SEARCH_FOR_MISSING_ALBUMS.lower() == "true" if SEARCH_FOR_MISSING_ALBUMS != "" else ""
        DRY_RUN_ADDING_TO_LIDARR = os.environ.get("DRY_RUN_ADDING_TO_LIDARR", "")
        self.DRY_RUN_ADDING_TO_LIDARR = DRY_RUN_ADDING_TO_LIDARR.lower() == "true" if DRY_RUN_ADDING_TO_LIDARR != "" else ""
        self.APP_NAME = os.environ.get("APP_NAME", "")
        self.APP_REV = os.environ.get("APP_REV", "")
        self.APP_URL = os.environ.get("APP_URL", "")
        self.LAST_FM_API_KEY = os.environ.get("LAST_FM_API_KEY", "")
        self.LAST_FM_API_SECRET = os.environ.get("LAST_FM_API_SECRET", "")
        self.MODE = os.environ.get("MODE", "")
        AUTO_START = os.environ.get("AUTO_START", "")
        self.AUTO_START = AUTO_START.lower() == "true" if AUTO_START != "" else ""
        AUTO_START_DELAY = os.environ.get("AUTO_START_DELAY", "")
        self.AUTO_START_DELAY = float(AUTO_START_DELAY) if AUTO_START_DELAY else ""

        # Load variables from the configuration file if not set by environmental variables.
        try:
            self.settings_config_file = os.path.join(self.config_folder, "settings_config.json")
            if os.path.exists(self.settings_config_file):
                self.lidify_logger.info("Loading Config via file")
                with open(self.settings_config_file, "r") as json_file:
                    ret = json.load(json_file)
                    for key in ret:
                        if getattr(self, key) == "":
                            setattr(self, key, ret[key])
        except Exception as e:
            self.lidify_logger.error(f"Error Loading Config: {str(e)}")

        # Load defaults if not set by an environmental variable or configuration file.
        for key, value in default_settings.items():
            if getattr(self, key) == "":
                setattr(self, key, value)

        # Save config.
        self.save_config_to_file()

    def automated_startup(self):
        self.get_artists_from_lidarr(checked=True)
        artists = [x["name"] for x in self.lidarr_items]
        self.start(artists)

    def connection(self):
        if self.recommended_artists:
            if self.clients_connected_counter == 0:
                if len(self.recommended_artists) > 25:
                    self.recommended_artists = random.sample(self.recommended_artists, 25)
                else:
                    self.lidify_logger.info("Shuffling Artists")
                    random.shuffle(self.recommended_artists)
            socketio.emit("more_artists_loaded", self.recommended_artists)

        self.clients_connected_counter += 1

    def disconnection(self):
        self.clients_connected_counter = max(0, self.clients_connected_counter - 1)

    def start(self, data):
        try:
            socketio.emit("clear")
            self.new_found_artists_counter = 1
            self.artists_to_use_in_search = []
            self.recommended_artists = []

            for item in self.lidarr_items:
                item_name = item["name"]
                if item_name in data:
                    item["checked"] = True
                    self.artists_to_use_in_search.append(item_name)
                else:
                    item["checked"] = False

            if self.artists_to_use_in_search:
                self.stop_event.clear()
            else:
                self.stop_event.set()
                raise ValueError("No Lidarr Artists Selected")

        except Exception as e:
            self.lidify_logger.error(f"Startup Error: {str(e)}")
            self.stop_event.set()
            ret = {"Status": "Error", "Code": str(e), "Data": self.lidarr_items, "Running": not self.stop_event.is_set()}
            socketio.emit("lidarr_sidebar_update", ret)

        else:
            self.find_similar_artists()

    def get_artists_from_lidarr(self, checked=False):
        ret={}
        try:
            self.lidify_logger.info("Getting Artists from Lidarr")
            self.lidarr_items = []
            endpoint = f"{self.LIDARR_ADDRESS}/api/v1/artist"
            headers = {"X-Api-Key": self.LIDARR_API_KEY}
            response = requests.get(endpoint, headers=headers, timeout=self.LIDARR_API_TIMEOUT)

            if response.status_code == 200:
                self.full_lidarr_artist_list = response.json()
                self.lidarr_items = [{"name": unidecode(artist["artistName"], replace_str=" "), "checked": checked} for artist in self.full_lidarr_artist_list]
                self.lidarr_items.sort(key=lambda x: x["name"].lower())
                self.cleaned_lidarr_items = [item["name"].lower() for item in self.lidarr_items]
                status = "Success"
                data = self.lidarr_items
            else:
                status = "Error"
                data = response.text

            ret = {"Status": status, "Code": response.status_code if status == "Error" else None, "Data": data, "Running": not self.stop_event.is_set()}

        except Exception as e:
            self.lidify_logger.error(f"Getting Artist Error: {str(e)}")
            ret = {"Status": "Error", "Code": 500, "Data": str(e), "Running": not self.stop_event.is_set()}

        finally:
            socketio.emit("lidarr_sidebar_update", ret)

    def find_similar_artists(self):
        if self.stop_event.is_set() or self.search_in_progress_flag:
            return

        elif self.MODE == "LastFM" and self.new_found_artists_counter > 0:
            try:
                self.lidify_logger.info(f"Searching for new artists via {self.MODE}")
                self.new_found_artists_counter = 0
                self.search_in_progress_flag = True
                random_artists = random.sample(self.artists_to_use_in_search, min(7, len(self.artists_to_use_in_search)))

                lfm = pylast.LastFMNetwork(api_key=self.LAST_FM_API_KEY, api_secret=self.LAST_FM_API_SECRET)
                for artist_name in random_artists:
                    if self.stop_event.is_set():
                        break

                    try:
                        chosen_artist = lfm.get_artist(artist_name)
                        related_artists = chosen_artist.get_similar()

                    except Exception as e:
                        self.lidify_logger.error(f"Error with LastFM on artist - '{artist_name}': {str(e)}")
                        self.lidify_logger.info("Trying next artist...")
                        continue

                    random_related_artists = random.sample(related_artists, min(30, len(related_artists)))
                    for related_artist in random_related_artists:
                        if self.stop_event.is_set():
                            break
                        cleaned_artist = unidecode(related_artist.item.name).lower()
                        if cleaned_artist not in self.cleaned_lidarr_items:
                            for item in self.recommended_artists:
                                if related_artist.item.name == item["Name"]:
                                    break
                            else:
                                artist_obj = lfm.get_artist(related_artist.item.name)
                                genres = ", ".join([tag.item.get_name().title() for tag in artist_obj.get_top_tags()[:5]]) or "Unknown Genre"
                                listeners = artist_obj.get_listener_count() or 0
                                play_count = artist_obj.get_playcount() or 0
                                img_link:str = "https://via.placeholder.com/300x200"
                                try:
                                    endpoint = "https://api.deezer.com/search/artist"
                                    params = {"q": related_artist.item.name}
                                    response = requests.get(endpoint, params=params)
                                    data = response.json()
                                    if "data" in data and data["data"]:
                                        artist_info = data["data"][0]
                                        img_link = artist_info.get("picture_xl", artist_info.get("picture_large", artist_info.get("picture_medium", artist_info.get("picture", ""))))

                                except Exception as e:
                                    self.lidify_logger.error(f"Deezer Error: {str(e)}")

                                exclusive_artist = {
                                    "Name": related_artist.item.name,
                                    "Genre": genres,
                                    "Status": "",
                                    "Img_Link": img_link,
                                    "Popularity": f"Play Count: {format_numbers(play_count)}",
                                    "Followers": f"Listeners: {format_numbers(listeners)}",
                                }
                                self.recommended_artists.append(exclusive_artist)
                                socketio.emit("more_artists_loaded", [exclusive_artist])
                                self.new_found_artists_counter += 1

                if self.new_found_artists_counter == 0:
                    self.lidify_logger.info("Search Exhausted - Try selecting more artists from existing Lidarr library")
                    socketio.emit("new_toast_msg", {"title": "Search Exhausted", "message": "Try selecting more artists from existing Lidarr library"})

            except Exception as e:
                self.lidify_logger.error(f"LastFM Error: {str(e)}")

            finally:
                self.search_in_progress_flag = False

        elif self.new_found_artists_counter == 0:
            try:
                self.search_in_progress_flag = True
                self.lidify_logger.info("Search Exhausted - Try selecting more artists from existing Lidarr library")
                socketio.emit("new_toast_msg", {"title": "Search Exhausted", "message": "Try selecting more artists from existing Lidarr library"})
                time.sleep(2)

            except Exception as e:
                self.lidify_logger.error(f"Search Exhausted Error: {str(e)}")

            finally:
                self.search_in_progress_flag = False

    def add_artists(self, raw_artist_name):
        try:
            artist_name = urllib.parse.unquote(raw_artist_name)
            artist_folder = artist_name.replace("/", " ")
            musicbrainzngs.set_useragent(self.APP_NAME, self.APP_REV, self.APP_URL)
            mbid = self.get_mbid_from_musicbrainz(artist_name)
            if mbid:
                lidarr_url = f"{self.LIDARR_ADDRESS}/api/v1/artist"
                headers = {"X-Api-Key": self.LIDARR_API_KEY}
                payload = {
                    "ArtistName": artist_name,
                    "qualityProfileId": self.QUALITY_PROFILE_ID,
                    "metadataProfileId": self.METADATA_PROFILE_ID,
                    "path": os.path.join(self.ROOT_FOLDER_PATH, artist_folder, ""),
                    "rootFolderPath": self.ROOT_FOLDER_PATH,
                    "foreignArtistId": mbid,
                    "monitored": True,
                    "addOptions": {"searchForMissingAlbums": self.SEARCH_FOR_MISSING_ALBUMS},
                }
                if self.DRY_RUN_ADDING_TO_LIDARR:
                    response = requests.Response()
                    response.status_code = 201
                else:
                    response = requests.post(lidarr_url, headers=headers, json=payload)

                if response.status_code == 201:
                    self.lidify_logger.info(f"Artist '{artist_name}' added successfully to Lidarr.")
                    status = "Added"
                    self.lidarr_items.append({"name": artist_name, "checked": False})
                    self.cleaned_lidarr_items.append(unidecode(artist_name).lower())
                else:
                    self.lidify_logger.error(f"Failed to add artist '{artist_name}' to Lidarr.")
                    error_data = json.loads(response.content)
                    error_message = error_data[0].get("errorMessage", "No Error Message Returned") if error_data else "Error Unknown"
                    self.lidify_logger.error(error_message)
                    if "already been added" in error_message:
                        status = "Already in Lidarr"
                        self.lidify_logger.info(f"Artist '{artist_name}' is already in Lidarr.")
                    elif "configured for an existing artist" in error_message:
                        status = "Already in Lidarr"
                        self.lidify_logger.info(f"'{artist_folder}' folder already configured for an existing artist.")
                    elif "Invalid Path" in error_message:
                        status = "Invalid Path"
                        self.lidify_logger.info(f"Path: {os.path.join(self.ROOT_FOLDER_PATH, artist_folder, '')} not valid.")
                    else:
                        status = "Failed to Add"

            else:
                status = "Failed to Add"
                self.lidify_logger.info(f"No Matching Artist for: '{artist_name}' in MusicBrainz.")
                socketio.emit("new_toast_msg", {"title": "Failed to add Artist", "message": f"No Matching Artist for: '{artist_name}' in MusicBrainz."})

            for item in self.recommended_artists:
                if item["Name"] == artist_name:
                    item["Status"] = status
                    socketio.emit("refresh_artist", item)
                    break

        except Exception as e:
            self.lidify_logger.error(f"Adding Artist Error: {str(e)}")

    def get_mbid_from_musicbrainz(self, artist_name):
        result = musicbrainzngs.search_artists(artist=artist_name)
        mbid = None

        if "artist-list" in result:
            artists = result["artist-list"]

            for artist in artists:
                match_ratio = fuzz.ratio(artist_name.lower(), artist["name"].lower())
                decoded_match_ratio = fuzz.ratio(unidecode(artist_name.lower()), unidecode(artist["name"].lower()))
                if match_ratio > 90 or decoded_match_ratio > 90:
                    mbid = artist["id"]
                    self.lidify_logger.info(f"Artist '{artist_name}' matched '{artist['name']}' with MBID: {mbid}  Match Ratio: {max(match_ratio, decoded_match_ratio)}")
                    break
            else:
                if self.FALLBACK_TO_TOP_RESULT and artists:
                    mbid = artists[0]["id"]
                    self.lidify_logger.info(f"Artist '{artist_name}' matched '{artists[0]['name']}' with MBID: {mbid}  Match Ratio: {max(match_ratio, decoded_match_ratio)}")

        return mbid

    def load_settings(self):
        try:
            data = {
                "LIDARR_ADDRESS": self.LIDARR_ADDRESS,
                "LIDARR_API_KEY": self.LIDARR_API_KEY,
                "ROOT_FOLDER_PATH": self.ROOT_FOLDER_PATH,
            }
            socketio.emit("settingsLoaded", data)
        except Exception as e:
            self.lidify_logger.error(f"Failed to load settings: {str(e)}")

    def update_settings(self, data):
        try:
            self.LIDARR_ADDRESS = data["LIDARR_ADDRESS"]
            self.LIDARR_API_KEY = data["LIDARR_API_KEY"]
            self.ROOT_FOLDER_PATH = data["ROOT_FOLDER_PATH"]
        except Exception as e:
            self.lidify_logger.error(f"Failed to update settings: {str(e)}")

    def save_config_to_file(self):
        try:
            with open(self.settings_config_file, "w") as json_file:
                json.dump(
                    {
                        "LIDARR_ADDRESS": self.LIDARR_ADDRESS,
                        "LIDARR_API_KEY": self.LIDARR_API_KEY,
                        "ROOT_FOLDER_PATH": self.ROOT_FOLDER_PATH,
                        "FALLBACK_TO_TOP_RESULT": self.FALLBACK_TO_TOP_RESULT,
                        "LIDARR_API_TIMEOUT": float(self.LIDARR_API_TIMEOUT),
                        "QUALITY_PROFILE_ID": self.QUALITY_PROFILE_ID,
                        "METADATA_PROFILE_ID": self.METADATA_PROFILE_ID,
                        "SEARCH_FOR_MISSING_ALBUMS": self.SEARCH_FOR_MISSING_ALBUMS,
                        "DRY_RUN_ADDING_TO_LIDARR": self.DRY_RUN_ADDING_TO_LIDARR,
                        "APP_NAME": self.APP_NAME,
                        "APP_REV": self.APP_REV,
                        "APP_URL": self.APP_URL,
                        "LAST_FM_API_KEY": self.LAST_FM_API_KEY,
                        "LAST_FM_API_SECRET": self.LAST_FM_API_SECRET,
                        "MODE": self.MODE,
                        "AUTO_START": self.AUTO_START,
                        "AUTO_START_DELAY": self.AUTO_START_DELAY,
                    },
                    json_file,
                    indent=4,
                )

        except Exception as e:
            self.lidify_logger.error(f"Error Saving Config: {str(e)}")

    def preview(self, raw_artist_name):
        artist_name = urllib.parse.unquote(raw_artist_name)
        if self.MODE == "LastFM":
            preview_info = {}
            try:
                biography = None
                lfm = pylast.LastFMNetwork(api_key=self.LAST_FM_API_KEY, api_secret=self.LAST_FM_API_SECRET)
                search_results = lfm.search_for_artist(artist_name)
                artists = search_results.get_next_page()
                cleaned_artist_name = unidecode(artist_name).lower()
                for artist_obj in artists:
                    match_ratio = fuzz.ratio(cleaned_artist_name, artist_obj.name.lower())
                    decoded_match_ratio = fuzz.ratio(unidecode(cleaned_artist_name), unidecode(artist_obj.name.lower()))
                    if match_ratio > 90 or decoded_match_ratio > 90:
                        biography = artist_obj.get_bio_content()
                        preview_info["artist_name"] = artist_obj.name
                        preview_info["biography"] = biography
                        break
                else:
                    preview_info = f"No Artist match for: {artist_name}"
                    self.lidify_logger.error(preview_info)

                if biography is None:
                    preview_info = f"No Biography available for: {artist_name}"
                    self.lidify_logger.error(preview_info)

            except Exception as e:
                preview_info = {"error": f"Error retrieving artist bio: {str(e)}"}
                self.lidify_logger.error(preview_info)

            finally:
                socketio.emit("lastfm_preview", preview_info, room=request.sid)


app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
socketio = SocketIO(app)
data_handler = DataHandler()


@app.route("/")
def home():
    return render_template("base.html")


@socketio.on("side_bar_opened")
def side_bar_opened():
    if data_handler.lidarr_items:
        ret = {"Status": "Success", "Data": data_handler.lidarr_items, "Running": not data_handler.stop_event.is_set()}
        socketio.emit("lidarr_sidebar_update", ret)


@socketio.on("get_lidarr_artists")
def get_lidarr_artists():
    thread = threading.Thread(target=data_handler.get_artists_from_lidarr, name="Lidarr_Thread")
    thread.daemon = True
    thread.start()


@socketio.on("finder")
def find_similar_artists(data):
    thread = threading.Thread(target=data_handler.find_similar_artists, args=(data,), name="Find_Similar_Thread")
    thread.daemon = True
    thread.start()


@socketio.on("adder")
def add_artists(data):
    thread = threading.Thread(target=data_handler.add_artists, args=(data,), name="Add_Artists_Thread")
    thread.daemon = True
    thread.start()


@socketio.on("connect")
def connection():
    data_handler.connection()


@socketio.on("disconnect")
def disconnection():
    data_handler.disconnection()


@socketio.on("load_settings")
def load_settings():
    data_handler.load_settings()


@socketio.on("update_settings")
def update_settings(data):
    data_handler.update_settings(data)
    data_handler.save_config_to_file()


@socketio.on("start_req")
def starter(data):
    data_handler.start(data)


@socketio.on("stop_req")
def stopper():
    data_handler.stop_event.set()


@socketio.on("load_more_artists")
def load_more_artists():
    thread = threading.Thread(target=data_handler.find_similar_artists, name="FindSimilar")
    thread.daemon = True
    thread.start()


@socketio.on("preview_req")
def preview(artist):
    data_handler.preview(artist)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
