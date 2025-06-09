import os
from django.contrib.gis.utils import LayerMapping
import geopandas as gpd
from django.core.management.base import BaseCommand

from anomaly_detection.regions.models import (AutonomousCommunity, Country,
                                              Municipality, Province)


class Command(BaseCommand):
    """
    Django command to prepare the original GADM data into for loading to the database.
    """

    help = """Load geographical data into the database."""

    DATA_DIR = os.path.join(os.path.join(os.path.dirname(__file__), 'data'))

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            default='data/gadm_410.gpkg',
            help='Path to the input GPKG file'
        )

    def get_clean_data(self, df_world):
        """
        Clean the GADM data for Spain.
        This function filters the data for Spain and selects the relevant columns.
        """
        # Filter the data for Spain
        df_esp = df_world[df_world['GID_0'] == 'ESP']

        # Filter columns
        columns_to_keep = [
            'UID', 'CONTINENT', 'GID_0', 'NAME_0', 'VARNAME_0',
            'GID_1', 'NAME_1', 'VARNAME_1', 'NL_NAME_1', 'TYPE_1', 'ENGTYPE_1',
            'GID_2', 'NAME_2', 'VARNAME_2', 'NL_NAME_2', 'TYPE_2', 'ENGTYPE_2',
            'GID_3', 'NAME_3', 'VARNAME_3', 'NL_NAME_3', 'TYPE_3', 'ENGTYPE_3',
            'GID_4', 'NAME_4', 'VARNAME_4', 'TYPE_4', 'ENGTYPE_4',
            'GID_5', 'NAME_5', 'TYPE_5', 'ENGTYPE_5',
            'geometry'
        ]
        df_esp_clean = df_esp[columns_to_keep].reset_index(drop=True)
        df_esp_clean.columns = df_esp_clean.columns.str.lower()
        return df_esp_clean

    def group_data(self, df_esp):
        """
        Group the data by autonomous communities, provinces, and municipalities.
        """

        df_autonomous_communities = df_esp[['gid_1', 'name_1', 'varname_1', 'gid_0', 'geometry']].dissolve(
            by="gid_1",
        ).reset_index().rename(
            columns={
                "gid_1": "gadm_id",
                "name_1": "name",
                "varname_1": "alt_name",
                'gid_0': 'gadm_id_country'
            }
        )

        df_autonomous_communities = df_autonomous_communities.set_crs(epsg=4326)

        df_provinces = df_esp[['gid_2', 'name_2', 'varname_2', 'gid_1', 'geometry']].dissolve(
            by="gid_2",
        ).reset_index().rename(
            columns={
                'gid_2': 'gadm_id',
                'name_2': 'name',
                'varname_2': 'alt_name',
                'gid_1': 'gadm_id_autonomous_community'
            }
        )
        df_provinces = df_provinces.set_crs(epsg=4326)

        df_municipalities = df_esp[['gid_4', 'name_4', 'varname_4', 'gid_2', 'geometry']].rename(
            columns={
                'gid_4': 'gadm_id',
                'name_4': 'name',
                'varname_4': 'alt_name',
                'gid_2': 'gadm_id_province'
            }
        )
        df_municipalities = df_municipalities.set_crs(epsg=4326)

        return df_municipalities, df_provinces, df_autonomous_communities

    def save_data_in_files(self, df_municipalities, df_provinces, df_autonomous_communities):
        """
        Save the dataframes to files.
        """
        municipalities_path = os.path.join(self.DATA_DIR, "municipalities.gpkg")
        df_municipalities.to_file(
            municipalities_path,
            driver="GPKG",
            layer="municipalities",
            index=False,
        )

        provinces_path = os.path.join(self.DATA_DIR, "provinces.gpkg")
        df_provinces.to_file(
            provinces_path,
            driver="GPKG",
            layer="provinces",
            index=False,
        )

        autonomous_communities_path = os.path.join(self.DATA_DIR, "autonomous_communities.gpkg")
        df_autonomous_communities.to_file(
            autonomous_communities_path,
            driver="GPKG",
            layer="autonomous_communities",
            index=False,
        )

        return municipalities_path, provinces_path, autonomous_communities_path

    def insert_data(self, municipalities_path, provinces_path, autonomous_communities_path):
        """
        Insert the data into the database.
        """
        self.stdout.write('Creating or updating the countries...')
        Country.objects.update_or_create(
            code='ESP',
            defaults={
                'name': 'Spain',
                'alt_name': 'España',
                'continent': 'Europe'
            }
        )
        self.stdout.write('Successfully created or updated the country.')

        self.stdout.write('Creating the autonomous communities...')
        lm_autonomous_communities = LayerMapping(
            AutonomousCommunity,
            autonomous_communities_path,
            {
                'code': 'gadm_id',
                'name': 'name',
                'alt_name': 'alt_name',
                'geometry': 'MULTIPOLYGON',
                'country': {
                    'code': 'gadm_id_country',
                },
            },
            transform=False,
            encoding='utf-8'
        )
        lm_autonomous_communities.save(strict=True, verbose=False)
        self.stdout.write('Successfully created or updated the autonomous communities.')

        self.stdout.write('Creating the provinces...')
        lm_provinces = LayerMapping(
            Province,
            provinces_path,
            {
                'code': 'gadm_id',
                'name': 'name',
                'alt_name': 'alt_name',
                'geometry': 'MULTIPOLYGON',
                'autonomous_community': {
                        'code': 'gadm_id_autonomous_community',
                },
            },
            transform=False,
            encoding='utf-8'
        )
        lm_provinces.save(strict=True, verbose=False)
        self.stdout.write('Successfully created or updated the provinces.')

        self.stdout.write('Creating the municipalities...')
        lm_municipalities = LayerMapping(
            Municipality,
            municipalities_path,
            {
                'code': 'gadm_id',
                'name': 'name',
                'alt_name': 'alt_name',
                'geometry': 'MULTIPOLYGON',
                'province': {
                    'code': 'gadm_id_province',
                },
            },
            transform=False,
            encoding='utf-8'
        )
        lm_municipalities.save(strict=True, verbose=False, progress=True)
        self.stdout.write('Successfully created or updated the municipalities.')

    def handle(self, *args, **options):
        """Entrypoint for command."""
        # Get the input file. If the input file is not provided, use the default one.
        input_file = options['input']
        if not input_file or not os.path.exists(input_file):
            input_file = os.path.join(self.DATA_DIR, 'gadm_410.gpkg')

        # Load the world GPKG file
        df_world = gpd.read_file(input_file)
        print("\nLoaded world GPKG file")
        print(df_world.head(3))

        # Filter and clean the data for Spain
        df_esp = self.get_clean_data(df_world)
        df_esp = df_esp.set_crs(epsg=4326)
        print("\nFiltered and cleaned data for Spain")
        print(df_esp.head(3))

        # Group the data by autonomous communities, provinces, and municipalities
        df_municipalities, df_provinces, df_autonomous_communities = self.group_data(df_esp)
        print("\nGrouped data by autonomous communities, provinces, and municipalities")
        print(df_municipalities.head(3))
        print(df_provinces.head(3))
        print(df_autonomous_communities.head(3))

        # Save the grouped data to files
        municipalities_path, provinces_path, autonomous_communities_path = self.save_data_in_files(
            df_municipalities, df_provinces, df_autonomous_communities
        )
        print("\nSaved grouped data to files")

        # Insert the data into the database
        municipalities_path = os.path.join(self.DATA_DIR, "municipalities.gpkg")
        provinces_path = os.path.join(self.DATA_DIR, "provinces.gpkg")
        autonomous_communities_path = os.path.join(self.DATA_DIR, "autonomous_communities.gpkg")
        try:
            self.insert_data(municipalities_path, provinces_path, autonomous_communities_path)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error inserting data: {e}"))
            return
        print("\nInserted data into the database")

        # Clean up the temporary files
        os.remove(municipalities_path)
        os.remove(provinces_path)
        os.remove(autonomous_communities_path)
        self.stdout.write(self.style.SUCCESS('Successfully loaded geographical data into the database.'))
