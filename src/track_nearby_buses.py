import time
import threading
import json
import numpy as np
from datetime import datetime, timezone, timedelta
from src.services.gtfs import *
from src.utils.special_text import *


POLL_INTERVAL_S = 1
ORIGIN_POSITION_LONG_LAT = (-123.248528, 49.266562)
SEARCH_RADIUS_LONG_LAT = 0.005
TRIGGER_TRAVEL_DISTANCE_LONG_LAT = 0.002


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
        
        def __init__(self, parent, trip_id, trip_name, route_name, x, y, timestamp, departure_time):
            self.parent = parent
            self.entry_id = None
            self.trip_id = trip_id
            self.trip_name = trip_name
            self.route_name = route_name
            self.reports = {}
            self.scheduled_departure_time = departure_time

            self.triggered = False
            self.in_range = False
            self.update_and_trigger(x, y, timestamp)

        @property
        def text_color(self):
            return 0 if self.entry_id is None else self.entry_id % 7

        @property
        def distance_traveled(self):

            if len(self.reports) < 2: return 0
            positions = list(self.reports.values())
            return sum([np.linalg.norm(np.subtract(np.array(positions[i]), np.array(positions[i + 1]))) for i in range(len(positions) - 1)])
        
        def name(self):

            return f'{self.route_name}/{self.scheduled_departure_time}'
        
        def print_reports(self):
            
            formatted_reports = {timestamp: hyperlink(f'{pos[0], pos[1]}', f'https://www.google.com/maps?q={pos[1]},{pos[0]}') for timestamp, pos in self.reports.items()}
            for report in formatted_reports.items():
                print(f'    {report[0]} - {report[1]}')

        def update_and_trigger(self, x, y, timestamp):

            self.reports[timestamp] = (x, y)
            current_time = datetime.strftime(datetime.now(tz=timezone(timedelta(hours=-8))), '%H:%M:%S')
            
            if not self.in_range and \
                'UBC' not in self.trip_name:
                for timestamp, position in self.reports.items():
                    if np.linalg.norm(np.array(position) - np.array(ORIGIN_POSITION_LONG_LAT)) < SEARCH_RADIUS_LONG_LAT:
                        self.in_range = True
                        self.entry_id = self.parent.generate_entry_id()
                        print(f'\n[{current_time}] {color_text(self.name(), self.text_color)} DETECTED')
                        self.print_reports()
                        break

            just_triggered = False
            if not self.triggered and \
                'UBC' not in self.trip_name and \
                self.distance_traveled > TRIGGER_TRAVEL_DISTANCE_LONG_LAT and \
                np.linalg.norm(np.array(ORIGIN_POSITION_LONG_LAT) - np.array([x, y])) < SEARCH_RADIUS_LONG_LAT:
                self.triggered = True
                just_triggered = True
                print(f'\n[{current_time}] {color_text(self.name(), self.text_color)} TRIGGERED')
                self.print_reports()

            return just_triggered
        

    def __init__(self, origin, radius, static_route_ids, static_route_names, static_trip_names, static_departure_times):
        self.x = origin[0]
        self.y = origin[1]
        self.radius = radius
        self.buses = {}
        self.entry_id_counter = 0

        self.static_route_ids = static_route_ids
        self.static_route_names = static_route_names
        self.static_trip_names = static_trip_names
        self.static_departure_times = static_departure_times

    def generate_entry_id(self):
        self.entry_id_counter += 1
        return self.entry_id_counter - 1

    def create_bus_entry(self, vehicle_data):

        self.buses[vehicle_data['trip_id']] = NearbyBusLog.BusEntry(
            parent=self,
            trip_id=vehicle_data['trip_id'],
            trip_name=vehicle_data['trip_name'],
            route_name=vehicle_data['route_name'],
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
            departure_time = self.static_departure_times.get(id, "Unknown").strip()

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