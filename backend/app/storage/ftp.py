from __future__ import annotations
import aioftp
from app.settings import settings
from app.storage.base import Storage, StoredObject


class FTPStorage(Storage):
    def _public_url(self, key: str) -> str:
        return f"{settings.ftp_public_base_url.rstrip('/')}/{key}"

    async def put(
        self, *, data: bytes, key: str, content_type: str, filename: str
    ) -> StoredObject:
        async with aioftp.Client.context(
            settings.ftp_host,
            settings.ftp_port,
            settings.ftp_user,
            settings.ftp_password,
        ) as client:
            target = f"{settings.ftp_base_dir.rstrip('/')}/{key}"
            # ensure dirs exist
            parts = target.split("/")
            path = ""
            for p in parts[:-1]:
                if not p:
                    continue
                path += "/" + p
                try:
                    await client.make_directory(path)
                except Exception:
                    pass
            await client.upload_stream(data, target)
        return StoredObject(
            key=key,
            url=self._public_url(key),
            size=len(data),
            content_type=content_type,
            filename=filename,
        )

    async def delete(self, *, key: str) -> None:
        async with aioftp.Client.context(
            settings.ftp_host,
            settings.ftp_port,
            settings.ftp_user,
            settings.ftp_password,
        ) as client:
            target = f"{settings.ftp_base_dir.rstrip('/')}/{key}"
            try:
                await client.remove_file(target)
            except Exception:
                pass

    async def get(self, *, key: str) -> bytes | None:
        try:
            async with aioftp.Client.context(
                settings.ftp_host,
                settings.ftp_port,
                settings.ftp_user,
                settings.ftp_password,
            ) as client:
                target = f"{settings.ftp_base_dir.rstrip('/')}/{key}"
                data = bytearray()
                async with client.download_stream(target) as stream:
                    async for block in stream.iter_by_block():
                        data.extend(block)
                return bytes(data)
        except Exception:
            return None
