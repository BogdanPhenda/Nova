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

    async def upload_file(self, file_or_content: str, object_name: str) -> str:
        """
        Загружает файл или содержимое в S3.
        :param file_or_content: Путь к файлу или содержимое для загрузки
        :param object_name: Имя объекта в S3
        :return: Публичный URL загруженного файла
        """
        async with self.get_client() as client:
            try:
                if os.path.exists(file_or_content):  # Если это путь к файлу
                    with open(file_or_content, "rb") as f:
                        await client.put_object(
                            Bucket=self.bucket_name,
                            Key=object_name,
                            Body=f,
                            ACL='public-read',
                            ContentType='application/xml'
                        )
                else:  # Если это содержимое
                    await client.put_object(
                        Bucket=self.bucket_name,
                        Key=object_name,
                        Body=file_or_content.encode('utf-8'),
                        ACL='public-read',
                        ContentType='application/xml'
                    )

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

    async def delete_file(self, object_name: str) -> bool:
        """Удаляет файл из S3."""
        async with self.get_client() as client:
            try:
                await client.delete_object(
                    Bucket=self.bucket_name,
                    Key=object_name
                )
                print(f"Файл '{object_name}' успешно удален из S3")
                return True
            except Exception as e:
                print(f"Ошибка при удалении файла из S3: {e}")
                return False 