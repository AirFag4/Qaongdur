from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error


class ObjectStoreError(RuntimeError):
    pass


class ObjectStoreClient:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
    ) -> None:
        parsed = urlparse(endpoint)
        secure = parsed.scheme == "https"
        host = parsed.netloc or parsed.path
        if not host:
            raise ValueError(f"Invalid object storage endpoint: {endpoint}")
        self._client = Minio(
            host,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    def ensure_bucket(self, bucket_name: str) -> None:
        try:
            if not self._client.bucket_exists(bucket_name):
                self._client.make_bucket(bucket_name)
        except S3Error as error:
            raise ObjectStoreError(str(error)) from error

    def object_exists(self, bucket_name: str, object_key: str) -> bool:
        try:
            self._client.stat_object(bucket_name, object_key)
            return True
        except S3Error as error:
            if error.code == "NoSuchKey":
                return False
            raise ObjectStoreError(str(error)) from error

    def upload_file(
        self,
        *,
        bucket_name: str,
        object_key: str,
        file_path: str,
        content_type: str | None = None,
    ) -> None:
        guessed_content_type = content_type or mimetypes.guess_type(file_path)[0]
        try:
            self._client.fput_object(
                bucket_name,
                object_key,
                file_path,
                content_type=guessed_content_type,
            )
        except S3Error as error:
            raise ObjectStoreError(str(error)) from error

    def download_file(
        self,
        *,
        bucket_name: str,
        object_key: str,
        file_path: str,
    ) -> None:
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._client.fget_object(bucket_name, object_key, file_path)
        except S3Error as error:
            raise ObjectStoreError(str(error)) from error
