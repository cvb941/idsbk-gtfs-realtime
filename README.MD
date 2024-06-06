# GTFS Realtime HTTP Server for Bratislava Public Transit

This project provides an HTTP server that serves GTFS-realtime data for public transportation vehicles in Bratislava. The data is fetched from the [Mapa IDS BK](https://mapa.idsbk.sk/mhd-ids-bk) website and transformed into the GTFS-realtime format, allowing applications to consume real-time transit information.

### Installation

Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt
```

## Usage

### Running the Server

To start the server, run the following command:

```bash
python main.py
```

The server will start on port 8000 by default. You can access the GTFS-realtime feed at `http://localhost:8000/gtfs-realtime`.

### Server Endpoints

- **GET /gtfs-realtime**: Fetches the real-time vehicle data, converts it to the GTFS-realtime format, and returns it.
