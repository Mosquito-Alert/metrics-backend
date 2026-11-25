import json
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the storage bucket for metric values (idempotent)."

    def handle(self, *args, **options):
        s3 = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(s3={'addressing_style': 'path'}),
        )
        bucket = settings.S3_BUCKET_NAME

        # wait for the storage service
        for _ in range(30):
            try:
                s3.list_buckets()
                break
            except (EndpointConnectionError, ClientError) as e:
                self.stdout.write(f"Waiting for storage... ({e.__class__.__name__})")
                time.sleep(2)
        else:
            raise SystemExit("Storage not reachable")

        try:
            s3.create_bucket(Bucket=bucket)
            self.stdout.write(f"Bucket '{bucket}' created.")
        except ClientError as e:
            if e.response['Error']['Code'] not in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
                raise
            self.stdout.write(f"Bucket '{bucket}' already exists.")

        s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})

        # public read (equivalent to: mc anonymous set download)
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/*"],
            }],
        }
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))

        self.stdout.write(self.style.SUCCESS('Storage bucket ready.'))
