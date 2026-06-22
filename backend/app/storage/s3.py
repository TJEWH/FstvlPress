from __future__ import annotations
import asyncio
import boto3
from botocore.client import Config
from app.settings import settings
from app.storage.base import Storage, StoredObject


STATIC_CACHE_CONTROL = "public, max-age=604800"


class S3Storage(Storage):
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = settings.s3_bucket

    def _public_url(self, key: str) -> str:
        if settings.s3_public_base_url:
            return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
        # fallback: presigned GET (not ideal for public, but works)
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=3600,
        )

    async def put(
        self, *, data: bytes, key: str, content_type: str, filename: str
    ) -> StoredObject:
        await asyncio.to_thread(
            self.s3.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl=STATIC_CACHE_CONTROL,
        )
        return StoredObject(
            key=key,
            url=self._public_url(key),
            size=len(data),
            content_type=content_type,
            filename=filename,
        )

    async def delete(self, *, key: str) -> None:
        await asyncio.to_thread(self.s3.delete_object, Bucket=self.bucket, Key=key)

    async def get(self, *, key: str) -> bytes | None:
        try:
            resp = await asyncio.to_thread(
                self.s3.get_object, Bucket=self.bucket, Key=key
            )
            return resp["Body"].read()
        except Exception:
            return None
