"""Private S3-compatible object storage for assessment evidence."""

from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.core.config import Settings


class ObjectStorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: BaseClient | None = None

    @property
    def client(self) -> BaseClient:
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.s3_endpoint,
                aws_access_key_id=self.settings.s3_access_key,
                aws_secret_access_key=self.settings.s3_secret_key,
                region_name=self.settings.s3_region,
            )
        return self._client

    def put_json(self, object_key: str, payload: dict[str, Any]) -> None:
        """Store evidence privately; tests avoid external infrastructure."""
        if self.settings.app_env == "test":
            return
        try:
            self.client.head_bucket(Bucket=self.settings.s3_bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.settings.s3_bucket)
        self.client.put_object(
            Bucket=self.settings.s3_bucket,
            Key=object_key,
            Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

    def signed_get_url(self, object_key: str, *, expires_seconds: int = 300) -> str:
        """Create a short-lived URL without exposing storage credentials."""
        expires = max(60, min(900, expires_seconds))
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.s3_bucket, "Key": object_key},
            ExpiresIn=expires,
        )
