import os
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from django.conf import settings

s3_client = boto3.client(
    's3',
    endpoint_url=settings.S3_ENDPOINT_URL,
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY
)


def s3_upload_folder(bucket_name, folder_path, destination_folder_name):
    try:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                sub_key = os.path.relpath(file_path, start=folder_path).replace("\\", "/")
                key = f"{destination_folder_name}/{sub_key}"
                s3_client.upload_file(file_path, bucket_name, key)
                print(f"Uploaded {file_path} as {key}")
    except FileNotFoundError as e:
        print(f"File not found: {e}")
    except NoCredentialsError:
        print("AWS credentials not found.")
    except PartialCredentialsError:
        print("Incomplete AWS credentials provided.")
