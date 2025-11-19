import os
import io
import zipfile
import requests
import csv
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict
from src.services.api_keys import GTFS_API_KEY
from src.utils.resource_path import *


GTFS_REALTIME_BASE_URL = "https://gtfsapi.translink.ca/v3/"
GTFS_STATIC_URL = "https://gtfs-static.translink.ca/gtfs/google_transit.zip"

GTFS_REALTIME_VEHICLE_POSITION_ENDPOINT = "gtfsposition"


def fetch_and_place_gtfs_static_data(output_dir: str):

    response = requests.get(f'{GTFS_STATIC_URL}?apikey={GTFS_API_KEY}')
    response.raise_for_status()
    
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        z.extractall(output_dir)


def load_gtfs_static_file(file_name: str):

    with open(resource_path(os.path.join('data', 'gtfs_static', f'{file_name}.txt')), 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return [row for row in reader]
    

def load_gtfs_realtime_data(endpoint: str):
    try:
        feed = gtfs_realtime_pb2.FeedMessage()
        response = requests.get(f'{GTFS_REALTIME_BASE_URL}{endpoint}?apikey={GTFS_API_KEY}')
        response.raise_for_status()
        feed.ParseFromString(response.content)
        return MessageToDict(feed)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching GTFS realtime data: {e}")
        return None
    except Exception as e:
        print(f"Error parsing GTFS realtime data: {e}")
        return None