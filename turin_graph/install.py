import argparse
from pathlib import Path
import boto3


def download_bucket(
    bucket: str,
    destination: Path,
    access_key: str,
    secret_access_key: str,
    prefix: str = "",
) -> None:
    s3 = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_access_key,
    )

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            # Skip S3 "directory" markers
            if key.endswith("/"):
                continue

            output_path = destination / key
            output_path.parent.mkdir(parents=True, exist_ok=True)

            print(f"Downloading: s3://{bucket}/{key}")
            s3.download_file(bucket, key, str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download all files from an S3 bucket."
    )

    parser.add_argument(
        "bucket",
        help="S3 bucket name",
    )

    parser.add_argument(
        "destination",
        type=Path,
        help="Local directory to download the bucket into",
    )

    parser.add_argument(
        "--access-key",
        required=True,
        help="AWS access key ID",
    )

    parser.add_argument(
        "--secret-access-key",
        required=True,
        help="AWS secret access key",
    )

    parser.add_argument(
        "--prefix",
        default="",
        help="Only download objects whose keys start with this prefix",
    )

    args = parser.parse_args()

    args.destination.mkdir(parents=True, exist_ok=True)

    download_bucket(
        bucket=args.bucket,
        destination=args.destination,
        access_key=args.access_key,
        secret_access_key=args.secret_access_key,
        prefix=args.prefix,
    )


if __name__ == "__main__":
    main()
