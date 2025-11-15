import src.services.gtfs as gtfs_service


if __name__ == '__main__':

    print('Fetching and placing GTFS static data...')

    gtfs_service.fetch_and_place_gtfs_static_data(output_dir='data/gtfs_static')

    print('GTFS static data fetched and placed successfully.')