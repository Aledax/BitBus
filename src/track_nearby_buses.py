import time
import threading
import numpy as np
from datetime import datetime, timezone, timedelta
from src.services.gtfs import *


POLL_INTERVAL_S = 1
ORIGIN_POSITION_LONG_LAT = (-123.248528, 49.266562)
SEARCH_RADIUS_LONG_LAT = 0.005
TRIGGER_TRAVEL_DISTANCE_LONG_LAT = 0.001


def load_static_data():

    routes_data = load_gtfs_static_file('routes')
    route_names_exceptions_data = load_gtfs_static_file('route_names_exceptions')
    trips_data = load_gtfs_static_file('trips')
    stop_times_data = load_gtfs_static_file('stop_times')

    route_ids = {}
    route_ids.update({route['route_short_name']: route['route_id'] for route in routes_data})
    route_ids.update({exception['route_name']: exception['route_id'] for exception in route_names_exceptions_data})

    route_names = {v: k for k, v in route_ids.items()}

    trip_names = {trip['trip_id']: trip['trip_headsign'] for trip in trips_data}

    departure_times = {}
    for stop_time in stop_times_data:
        if stop_time['trip_id'] not in departure_times:
            departure_times[stop_time['trip_id']] = stop_time['departure_time']

    return route_ids, route_names, trip_names, departure_times


class NearbyBusLog:

    class BusEntry:
        
        def __init__(self, parent, trip_id, trip_name, x, y, timestamp, departure_time):
            self.parent = parent
            self.trip_id = trip_id
            self.trip_name = trip_name
            self.previous_positions = [(x, y)]
            self.timestamp = timestamp
            self.departure_time = departure_time

            self.triggered = False

        @property
        def distance_traveled(self):

            if len(self.previous_positions) < 2: return 0
            return sum([np.linalg.norm(np.subtract(np.array(self.previous_positions[i]), np.array(self.previous_positions[i + 1]))) for i in range(len(self.previous_positions) - 1)])

        def update_and_trigger(self, x, y, timestamp):

            just_triggered = False
            if not self.triggered and \
                'UBC' not in self.trip_name and \
                self.distance_traveled > TRIGGER_TRAVEL_DISTANCE_LONG_LAT and \
                np.linalg.norm(np.array([self.parent.x, self.parent.y]) - np.array([x, y])) < self.parent.radius:
                self.triggered = True
                just_triggered = True

            self.previous_positions.append((x, y))
            self.timestamp = timestamp

            return just_triggered
        

    def __init__(self, origin, radius, static_route_ids, static_route_names, static_trip_names, static_departure_times):
        self.x = origin[0]
        self.y = origin[1]
        self.radius = radius
        self.buses = {}

        self.static_route_ids = static_route_ids
        self.static_route_names = static_route_names
        self.static_trip_names = static_trip_names
        self.static_departure_times = static_departure_times

    def create_bus_entry(self, vehicle_data):

        self.buses[vehicle_data['trip_id']] = NearbyBusLog.BusEntry(
            parent=self,
            trip_id=vehicle_data['trip_id'],
            trip_name=vehicle_data['trip_name'],
            x=vehicle_data['x'],
            y=vehicle_data['y'],
            timestamp=vehicle_data['timestamp'],
            departure_time=vehicle_data['departure_time']
        )

    def update_bus_entry(self, vehicle_data):

        return self.buses[vehicle_data['trip_id']].update_and_trigger(
            x=vehicle_data['x'],
            y=vehicle_data['y'],
            timestamp=vehicle_data['timestamp']
        )

    def update_and_trigger_buses(self):

        raw_vehicle_position_data = load_gtfs_realtime_data(GTFS_REALTIME_VEHICLE_POSITION_ENDPOINT)
        if raw_vehicle_position_data == None:
            return []

        parsed_vehicle_position_data = self.parse_vehicle_position_data(raw_vehicle_position_data)

        triggered_vehicles = []

        for vehicle_data in parsed_vehicle_position_data:
            if vehicle_data['trip_id'] not in self.buses:
                self.create_bus_entry(vehicle_data)
            else:
                triggered = self.update_bus_entry(vehicle_data)
                if triggered:
                    triggered_vehicles.append(vehicle_data)

        return triggered_vehicles


    def parse_vehicle_position_data(self, vehicle_position_data: dict):

        vehicles = []

        for entity in vehicle_position_data.get("entity", []):

            vehicle = entity.get("vehicle", {})
            trip = vehicle.get("trip", {})
            route_id = trip.get("routeId", "")
            route_name = self.static_route_names.get(route_id, "Unknown")
            id = entity.get("id", "")
            trip_name = self.static_trip_names.get(id, "Unknown")
            timestamp = vehicle.get("timestamp", 0)
            departure_time = self.static_departure_times.get(id, "Unknown")

            vehicles.append({
                'trip_id': int(id),
                'trip_name': trip_name,
                'route_name': route_name,
                'x': vehicle.get("position", {}).get("longitude"),
                'y': vehicle.get("position", {}).get("latitude"),
                'timestamp': datetime.fromtimestamp(int(timestamp), tz=timezone.utc).astimezone(timezone(timedelta(hours=-8))).strftime('%H:%M:%S'),
                'departure_time': departure_time
            })

        return vehicles


def track_nearby_buses(triggered_bus_list: list, triggered_bus_list_lock: threading.RLock):

    nearby_bus_log = NearbyBusLog(ORIGIN_POSITION_LONG_LAT, SEARCH_RADIUS_LONG_LAT, *load_static_data())

    while True:
        triggered_buses = nearby_bus_log.update_and_trigger_buses()
        with triggered_bus_list_lock:
            for vehicle in triggered_buses:
                triggered_bus_list.append(vehicle)
        time.sleep(POLL_INTERVAL_S)