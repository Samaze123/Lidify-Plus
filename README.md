![Build Status](https://github.com/TheWicklowWolf/Lidify/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/lidify.svg)


<p>
  <img src="/src/static/lidify.png" alt="image">
</p>

Music discovery tool that provides recommendations based on selected Lidarr artists.  

#### Note:
As of November 2024 changes to the Spotify API prevent its use in this application, see https://github.com/TheWicklowWolf/Lidify/issues/24 for details.  
This application now exclusively supports Last.fm. To integrate it, log in to your Last.fm account and create an API account at [this page](https://www.last.fm/api/account/create). Then, copy the provided API key and secret into the Docker Compose configuration.  


## Run using docker-compose

```yaml
services:
  lidify:
    image: thewicklowwolf/lidify:latest
    container_name: lidify
    volumes:
      - ./config:/lidify/config
      - /etc/localtime:/etc/localtime:ro
    ports:
      - 5000:5000
    restart: unless-stopped
    environment:
      LAST_FM_API_KEY: <insert>
      LAST_FM_API_SECRET: <insert>

```
If you put both Lidarr and Lidify in the same network, you can use the Lidarr container name as the address:
```yaml
services:
  lidify:
    environment:
      LIDARR_ADDRESS: http://lidarr:8686
    networks:
      lidarr_network:
  lidarr:
    ...: ...
    networks:
      lidarr_network:
networks:
  lidarr_network:
```

## Configuration via environment variables

Certain values can be set via environment variables:

* __PUID__: The user ID to run the app with. Defaults to `1000`. 
* __PGID__: The group ID to run the app with. Defaults to `1000`.
* __LIDARR_ADDRESS__: The URL for Lidarr. Defaults to `http://192.168.1.2:8686`. Can be configured from the application as well.
* __LIDARR_API_KEY__: The API key for Lidarr. Defaults to ``. Can be configured from the application as well.
* __ROOT_FOLDER_PATH__: The root folder path for music. Defaults to `/data/media/music/`. Can be configured from the application as well.
* __FALLBACK_TO_TOP_RESULT__: Whether to use the top result if no match is found. Defaults to `False`.
* __LIDARR_API_TIMEOUT__: Timeout duration for Lidarr API calls. Defaults to `120`.
* __QUALITY_PROFILE_ID__: Quality profile ID in Lidarr. Defaults to `1`.
* __METADATA_PROFILE_ID__: Metadata profile ID in Lidarr. Defaults to `1`
* __SEARCH_FOR_MISSING_ALBUMS__: Whether to start searching for albums when adding artists. Defaults to `False`
* __DRY_RUN_ADDING_TO_LIDARR__: Whether to run without adding artists in Lidarr. Defaults to `False`
* __APP_NAME__: Name of the application. Defaults to `Lidify`.
* __APP_REV__: Application revision. Defaults to `0.01`.
* __APP_URL__: URL of the application. Defaults to `Random URL`.
* __LAST_FM_API_KEY__: The API key for LastFM. Defaults to ``.
* __LAST_FM_API_SECRET__: The API secret for LastFM. Defaults to ``.
* __MODE__: Mode for discovery (Right now, only LastFM). Defaults to `LastFM`.
* __AUTO_START__: Whether to run automatically at startup. Defaults to `False`.
* __AUTO_START_DELAY__: Delay duration for Auto Start in Seconds (if enabled). Defaults to `60`.

---

<p>
  <img src="/src/static/light.png" alt="image">
</p>

<p>
  <img src="/src/static/dark.png" alt="image">
</p>

---

https://hub.docker.com/r/thewicklowwolf/lidify
