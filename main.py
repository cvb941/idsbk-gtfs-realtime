import json
import time
import requests
import zipfile
import os
from io import BytesIO
from http.server import BaseHTTPRequestHandler, HTTPServer
from google.transit import gtfs_realtime_pb2
import csv

# URL to fetch the data
DATA_URL = "https://mapa.idsbk.sk/navigation/vehicles/nearby?lat=48.14862961464581&lng=17.122590613001403&radius=2.4029061281587465&cityID=-1"
STATIC_GTFS_URL = "https://www.arcgis.com/sharing/rest/content/items/aba12fd2cbac4843bc7406151bc66106/data"


# Download and extract the static GTFS feed
def download_static_gtfs(url):
    response = requests.get(url)
    with zipfile.ZipFile(BytesIO(response.content)) as z:
        z.extractall("gtfs")


# Parse GTFS files into dictionaries
def parse_gtfs_files():
    gtfs_data = {}

    # Parse stops.txt
    with open('gtfs/stops.txt', mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        gtfs_data['stops'] = {row['stop_id']: row for row in reader}

    # Parse trips.txt
    with open('gtfs/trips.txt', mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        gtfs_data['trips'] = {row['trip_id']: row for row in reader}

    # Parse routes.txt
    with open('gtfs/routes.txt', mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        gtfs_data['routes'] = {row['route_id']: row for row in reader}

    # Parse stop_times.txt
    gtfs_data['stop_times'] = []
    with open('gtfs/stop_times.txt', mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        for row in reader:
            gtfs_data['stop_times'].append(row)

    return gtfs_data


def fetch_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None


def create_gtfs_realtime_feed(data, gtfs_data):
    # Create GTFS-realtime FeedMessage
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = int(time.time())

    if data and "vehicles" in data:
        for vehicle in data["vehicles"]:
            entity = feed.entity.add()
            entity.id = str(vehicle["vehicleID"])

            # Add vehicle position
            vehicle_position = entity.vehicle
            vehicle_position.vehicle.id = str(vehicle["vehicleID"])
            vehicle_position.position.latitude = vehicle["latitude"]
            vehicle_position.position.longitude = vehicle["longitude"]
            vehicle_position.current_status = (
                gtfs_realtime_pb2.VehiclePosition.STOPPED_AT if vehicle["isOnStop"]
                else gtfs_realtime_pb2.VehiclePosition.IN_TRANSIT_TO
            )
            vehicle_position.stop_id = str(vehicle["lastStopOrder"])
            vehicle_position.timestamp = int(time.time())
            # Vehicle label (if available)
            if vehicle["licenseNumber"]:
                vehicle_position.vehicle.label = vehicle["licenseNumber"]

            # Add trip update
            trip_update = entity.trip_update
            trip_id = str(vehicle["timeTableTrip"]["tripID"])
            trip_update.trip.trip_id = trip_id

            # Augment with static GTFS data
            if trip_id in gtfs_data['trips']:
                trip_info = gtfs_data['trips'][trip_id]
                route_id = trip_info['route_id']
                trip_update.trip.route_id = route_id
                if route_id in gtfs_data['routes']:
                    route_info = gtfs_data['routes'][route_id]
                    trip_update.trip.route_short_name = route_info['route_short_name']
                    trip_update.trip.route_long_name = route_info['route_long_name']

            trip_update.trip.direction_id = 1 if vehicle["timeTableTrip"]["ezTripDirection"] == "there" else 0
            trip_update.trip.start_date = time.strftime("%Y%m%d")

            # Add delay information
            delay_seconds = vehicle["delayMinutes"] * 60  # Convert minutes to seconds
            trip_update.delay = delay_seconds

            # Augment with stop times from static GTFS data
            for stop_time in gtfs_data['stop_times']:
                if stop_time['trip_id'] == trip_id:
                    stop_time_update = trip_update.stop_time_update.add()
                    stop_time_update.stop_sequence = int(stop_time['stop_sequence'])
                    stop_time_update.stop_id = stop_time['stop_id']
                    
                    # Calculate arrival and departure times with delay
                    if 'arrival_time' in stop_time:
                        arrival = stop_time_update.arrival
                        hours, minutes, seconds = map(int, stop_time['arrival_time'].split(':'))
                        arrival.time = hours * 3600 + minutes * 60 + seconds + delay_seconds
                    
                    if 'departure_time' in stop_time:
                        departure = stop_time_update.departure
                        hours, minutes, seconds = map(int, stop_time['departure_time'].split(':'))
                        departure.time = hours * 3600 + minutes * 60 + seconds + delay_seconds
                    
                    # Set delay for this stop
                    stop_time_update.departure.delay = delay_seconds

    return feed.SerializeToString()


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/gtfs-realtime":
            self.send_response(200)
            self.send_header("Content-type", "application/octet-stream")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.end_headers()
            data = fetch_data(DATA_URL)
            gtfs_feed = create_gtfs_realtime_feed(data, gtfs_data)
            self.wfile.write(gtfs_feed)
        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_HEAD(self):
        if self.path == "/gtfs-realtime":
            self.send_response(200)
            self.send_header("Content-type", "application/octet-stream")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()


def run(server_class=HTTPServer, handler_class=RequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting HTTP server on port {port}...')
    print(f'Open url: http://localhost:{port}/gtfs-realtime')
    httpd.serve_forever()


if __name__ == "__main__":
    download_static_gtfs(STATIC_GTFS_URL)
    gtfs_data = parse_gtfs_files()
    run()
