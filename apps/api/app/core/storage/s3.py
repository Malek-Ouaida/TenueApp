from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import quote, unquote, urlparse

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]


@dataclass(frozen=True)
class PresignedUpload:
    method: str
    url: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class PresignedDownload:
    url: str
    expires_at: datetime


@dataclass(frozen=True)
class StorageObject:
    bucket: str
    key: str
    content_length: int
    content_type: str | None


class ObjectStorageClient(Protocol):
    def generate_presigned_upload(
        self,
        *,
        bucket: str,
        key: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> PresignedUpload: ...

    def generate_presigned_download(
        self,
        *,
        bucket: str,
        key: str,
        expires_in_seconds: int,
    ) -> PresignedDownload: ...

    def head_object(self, *, bucket: str, key: str) -> StorageObject | None: ...

    def get_object_bytes(self, *, bucket: str, key: str) -> bytes: ...

    def put_object_bytes(
        self,
        *,
        bucket: str,
        key: str,
        content: bytes,
        content_type: str,
    ) -> None: ...

    def copy_object(
        self,
        *,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
        content_type: str | None = None,
    ) -> None: ...

    def delete_object(self, *, bucket: str, key: str) -> None: ...


class S3StorageClient:
    def __init__(
        self,
        *,
        endpoint_url: str,
        region_name: str,
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def generate_presigned_upload(
        self,
        *,
        bucket: str,
        key: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> PresignedUpload:
        url = self._client.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in_seconds,
            HttpMethod="PUT",
        )
        return PresignedUpload(
            method="PUT",
            url=url,
            headers={"Content-Type": content_type},
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )

    def generate_presigned_download(
        self,
        *,
        bucket: str,
        key: str,
        expires_in_seconds: int,
    ) -> PresignedDownload:
        url = self._client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
            HttpMethod="GET",
        )
        return PresignedDownload(
            url=url,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )

    def head_object(self, *, bucket: str, key: str) -> StorageObject | None:
        try:
            result = self._client.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if _is_missing_object(exc):
                return None
            raise

        return StorageObject(
            bucket=bucket,
            key=key,
            content_length=int(result["ContentLength"]),
            content_type=result.get("ContentType"),
        )

    def get_object_bytes(self, *, bucket: str, key: str) -> bytes:
        try:
            result = self._client.get_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if _is_missing_object(exc):
                raise FileNotFoundError(f"Object {bucket}/{key} was not found.") from exc
            raise

        body = result["Body"]
        return bytes(body.read())

    def put_object_bytes(
        self,
        *,
        bucket: str,
        key: str,
        content: bytes,
        content_type: str,
    ) -> None:
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )

    def copy_object(
        self,
        *,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
        content_type: str | None = None,
    ) -> None:
        params: dict[str, object] = {
            "Bucket": destination_bucket,
            "Key": destination_key,
            "CopySource": {"Bucket": source_bucket, "Key": source_key},
        }
        if content_type is not None:
            params["ContentType"] = content_type
            params["MetadataDirective"] = "REPLACE"

        try:
            self._client.copy_object(**params)
        except ClientError as exc:
            if _is_missing_object(exc):
                raise FileNotFoundError(
                    f"Object {source_bucket}/{source_key} was not found."
                ) from exc
            raise

    def delete_object(self, *, bucket: str, key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=key)


def _is_missing_object(exc: ClientError) -> bool:
    error_code = exc.response.get("Error", {}).get("Code")
    status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return error_code in {"404", "NoSuchKey", "NotFound"} or status_code == 404


class InMemoryStorageClient:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], tuple[bytes, str | None]] = {}

    def generate_presigned_upload(
        self,
        *,
        bucket: str,
        key: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> PresignedUpload:
        encoded_key = quote(key, safe="")
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
        return PresignedUpload(
            method="PUT",
            url=f"https://fake-storage.local/upload/{bucket}/{encoded_key}",
            headers={"Content-Type": content_type},
            expires_at=expires_at,
        )

    def generate_presigned_download(
        self,
        *,
        bucket: str,
        key: str,
        expires_in_seconds: int,
    ) -> PresignedDownload:
        encoded_key = quote(key, safe="")
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
        return PresignedDownload(
            url=f"https://fake-storage.local/download/{bucket}/{encoded_key}",
            expires_at=expires_at,
        )

    def put_via_presigned_upload(
        self,
        *,
        url: str,
        headers: dict[str, str],
        content: bytes,
    ) -> None:
        parsed = urlparse(url)
        parts = parsed.path.lstrip("/").split("/", 2)
        if len(parts) != 3 or parts[0] != "upload":
            raise ValueError("Unexpected presigned upload URL.")
        _, bucket, encoded_key = parts
        self._objects[(bucket, unquote(encoded_key))] = (content, headers.get("Content-Type"))

    def head_object(self, *, bucket: str, key: str) -> StorageObject | None:
        payload = self._objects.get((bucket, key))
        if payload is None:
            return None
        content, content_type = payload
        return StorageObject(
            bucket=bucket,
            key=key,
            content_length=len(content),
            content_type=content_type,
        )

    def get_object_bytes(self, *, bucket: str, key: str) -> bytes:
        payload = self._objects.get((bucket, key))
        if payload is None:
            raise FileNotFoundError(f"Object {bucket}/{key} was not found.")
        return payload[0]

    def put_object_bytes(
        self,
        *,
        bucket: str,
        key: str,
        content: bytes,
        content_type: str,
    ) -> None:
        self._objects[(bucket, key)] = (content, content_type)

    def copy_object(
        self,
        *,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
        content_type: str | None = None,
    ) -> None:
        payload = self._objects.get((source_bucket, source_key))
        if payload is None:
            raise FileNotFoundError(f"Object {source_bucket}/{source_key} was not found.")

        content, existing_content_type = payload
        self._objects[(destination_bucket, destination_key)] = (
            content,
            content_type or existing_content_type,
        )

    def delete_object(self, *, bucket: str, key: str) -> None:
        self._objects.pop((bucket, key), None)
