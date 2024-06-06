import json
import time
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from google.transit import gtfs_realtime_pb2

# URL to fetch the data
DATA_URL = "https://mapa.idsbk.sk/navigation/vehicles/nearby?lat=48.14862961464581&lng=17.122590613001403&radius=1000.4029061281587465&cityID=-1"

def fetch_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def create_gtfs_realtime_feed(data):
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
            trip_update.trip.trip_id = str(vehicle["timeTableTrip"]["tripID"])
            trip_update.trip.route_id = str(vehicle["timeTableTrip"]["timeTableLine"]["lineID"])
            trip_update.trip.direction_id = 1 if vehicle["timeTableTrip"]["ezTripDirection"] == "there" else 0
            trip_update.trip.start_date = time.strftime("%Y%m%d")
            stop_time_update = trip_update.stop_time_update.add()
            stop_time_update.stop_sequence = vehicle["lastStopOrder"]
            stop_time_update.departure.delay = vehicle["delayMinutes"] * 60
            # stop_time_update.stop_id could be added if stop IDs were available

    return feed.SerializeToString()

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/gtfs-realtime":
            self.send_response(200)
            self.send_header("Content-type", "application/octet-stream")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            data = fetch_data(DATA_URL)
            gtfs_feed = create_gtfs_realtime_feed(data)
            self.wfile.write(gtfs_feed)
        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_HEAD(self):
        if self.path == "/gtfs-realtime":
            self.send_response(200)
            self.send_header("Content-type", "application/octet-stream")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

def run(server_class=HTTPServer, handler_class=RequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting HTTP server on port {port}...')
    print(f'Open url: http://localhost:{port}/gtfs-realtime')
    httpd.serve_forever()

if __name__ == "__main__":
    run()
