import os
from contextlib import asynccontextmanager
from aiobotocore.session import get_session

class S3AsyncClient:
    def __init__(self, access_key: str, secret_key: str, endpoint_url_base: str, bucket_name: str, public_endpoint: str = None):
        self.bucket_name = bucket_name
        self.endpoint_url = f"https://{endpoint_url_base}"  # S3 API endpoint
        self.public_endpoint = public_endpoint  # Публичный endpoint (UUID контейнера)
        self.config = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "endpoint_url": self.endpoint_url,
            "verify": False,
        }
        self.session = get_session()

    @asynccontextmanager
    async def get_client(self):
        async with self.session.create_client("s3", **self.config) as client:
            yield client

    async def upload_file(self, file_path: str, object_name: str) -> str:
        async with self.get_client() as client:
            try:
                with open(file_path, "rb") as f:
                    await client.put_object(Bucket=self.bucket_name, Key=object_name, Body=f, ACL='public-read', ContentType='application/xml')
                # Используем публичный endpoint для ссылки, если он задан
                if self.public_endpoint:
                    public_url = f"{self.public_endpoint}/{object_name}"
                else:
                    public_url = f"{self.endpoint_url}/{self.bucket_name}/{object_name}"
                print(f"Файл '{object_name}' успешно загружен в S3. Ссылка: {public_url}")
                return public_url
            except Exception as e:
                print(f"Ошибка при загрузке файла в S3: {e}")
                return "" 