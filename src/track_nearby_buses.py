import time
import threading
import numpy as np
from datetime import datetime, timezone
from src.services.gtfs import *


routes_data = load_gtfs_static_file('routes')
route_names_exceptions_data = load_gtfs_static_file('route_names_exceptions')
trips_data = load_gtfs_static_file('trips')


route_ids = {}
route_ids.update({route['route_short_name']: route['route_id'] for route in routes_data})
route_ids.update({exception['route_name']: exception['route_id'] for exception in route_names_exceptions_data})

route_names = {v: k for k, v in route_ids.items()}

trip_names = {trip['trip_id']: trip['trip_headsign'] for trip in trips_data}


class NearbyBusLog:

    class BusEntry:
        
        def __init__(self, parent, trip_id, trip_name, x, y, timestamp):
            self.parent = parent
            self.trip_id = trip_id
            self.trip_name = trip_name
            self.x = x
            self.y = y
            self.timestamp = timestamp

            self.observed = False

        def update(self, x, y, timestamp):

            just_observed = False
            # if not self.observed and distance_to_line_segment(np.array([self.parent.x, self.parent.y]), np.array([self.x, self.y]), np.array([x, y])) < self.parent.radius:
            if not self.observed and \
                'UBC' not in self.trip_name and \
                np.linalg.norm(np.array([self.parent.x, self.parent.y]) - np.array([x, y])) < self.parent.radius:
                self.observed = True
                just_observed = True

            self.x = x
            self.y = y
            self.timestamp = timestamp

            return just_observed

    def __init__(self, x, y, radius):
        self.x = x
        self.y = y
        self.radius = radius
        self.buses = {}

    def update_buses(self):

        vehicle_position_data = load_gtfs_realtime_data(GTFS_REALTIME_VEHICLE_POSITION_ENDPOINT)
        parsed_vehicle_position_data = parse_vehicle_position_data(vehicle_position_data)

        just_observed_vehicles = []

        for vehicle in parsed_vehicle_position_data:
            if vehicle['trip_id'] not in self.buses:
                self.buses[vehicle['trip_id']] = NearbyBusLog.BusEntry(
                    parent=self,
                    trip_id=vehicle['trip_id'],
                    trip_name=vehicle['trip_name'],
                    x=vehicle['x'],
                    y=vehicle['y'],
                    timestamp=vehicle['timestamp']
                )
            else:
                if self.buses[vehicle['trip_id']].x == vehicle['x'] and self.buses[vehicle['trip_id']].y == vehicle['y']:
                    continue
                just_observed = self.buses[vehicle['trip_id']].update(
                    x=vehicle['x'],
                    y=vehicle['y'],
                    timestamp=vehicle['timestamp']
                )
                if just_observed:
                    just_observed_vehicles.append(vehicle)

        return just_observed_vehicles


def parse_vehicle_position_data(vehicle_position_data: dict):

    vehicles = []

    for entity in vehicle_position_data.get("entity", []):

        vehicle = entity.get("vehicle", {})
        trip = vehicle.get("trip", {})
        route_id = trip.get("routeId", "")
        route_name = route_names.get(route_id, "Unknown")
        id = entity.get("id", "")
        trip_name = trip_names.get(id, "Unknown")
        timestamp = vehicle.get("timestamp", 0)

        vehicles.append({
            'trip_id': int(id),
            'trip_name': trip_name,
            'route_name': route_name,
            'x': vehicle.get("position", {}).get("longitude"),
            'y': vehicle.get("position", {}).get("latitude"),
            'timestamp': datetime.fromtimestamp(int(timestamp), tz=timezone.utc),
        })

    return vehicles


def distance_to_line_segment(p, v, w):
    l2 = np.sum((w - v) ** 2)
    t = max(0, min(1, np.dot(p - v, w - v) / l2))
    projection = v + t * (w - v)

    return np.linalg.norm(p - projection)


def track_nearby_buses(bus_list: list, bus_list_lock: threading.RLock):

    nearby_bus_log = NearbyBusLog(x=-123.248528, y=49.266562, radius=0.005)

    while True:
        just_observed_vehicles = nearby_bus_log.update_buses()
        with bus_list_lock:
            for vehicle in just_observed_vehicles:
                bus_list.append(vehicle)
        time.sleep(1)


if __name__ == '__main__':

    nearby_bus_log = NearbyBusLog(x=-123.248528, y=49.266562, radius=0.005)
    
    while True:
        nearby_bus_log.update_buses()
        time.sleep(1)