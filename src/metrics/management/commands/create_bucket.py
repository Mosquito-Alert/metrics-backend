import boto3
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Django command to create a storage bucket for metric values.
    """

    help = "Django command to create a storage bucket for metric values."

    def handle(self, *args, **options):
        """
        Handle the command to create the storage bucket.
        """
        self.stdout.write("Creating storage bucket for metric values...")

        s3_client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT_LOCAL_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY
        )
        bucket_name = settings.S3_BUCKET_NAME

        try:
            s3_client.create_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' created successfully.")
            s3_client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={"Status": "Enabled"}
            )
            print(f"Versioning enabled for bucket '{bucket_name}'.")
        except s3_client.exceptions.BucketAlreadyExists as e:
            print(f"Bucket already exists: {e}")
        except s3_client.exceptions.BucketAlreadyOwnedByYou:
            print(f"Bucket '{bucket_name}' already owned by you.")

        self.stdout.write(self.style.SUCCESS('Successfully created the storage bucket for metric values.'))
