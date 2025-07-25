from datetime import datetime
from typing import Dict, List, Optional
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class FileMetadata:
    """Класс для хранения метаданных файла."""
    def __init__(
        self,
        file_id: str,
        original_name: str,
        user_id: str,
        upload_date: datetime,
        object_type: str,
        status: str = "new",
        last_update: Optional[datetime] = None,
        description: str = "",
    ):
        self.file_id = file_id
        self.original_name = original_name
        self.user_id = user_id
        self.upload_date = upload_date
        self.object_type = object_type
        self.status = status  # new, processing, processed, error
        self.last_update = last_update or upload_date
        self.description = description

    def to_dict(self) -> Dict:
        """Преобразует объект в словарь для сериализации."""
        return {
            "file_id": self.file_id,
            "original_name": self.original_name,
            "user_id": self.user_id,
            "upload_date": self.upload_date.isoformat(),
            "object_type": self.object_type,
            "status": self.status,
            "last_update": self.last_update.isoformat(),
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'FileMetadata':
        """Создает объект из словаря."""
        return cls(
            file_id=data["file_id"],
            original_name=data["original_name"],
            user_id=data["user_id"],
            upload_date=datetime.fromisoformat(data["upload_date"]),
            object_type=data["object_type"],
            status=data["status"],
            last_update=datetime.fromisoformat(data["last_update"]),
            description=data["description"]
        )

class FileManager:
    """Менеджер для работы с файлами и их метаданными."""
    
    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = base_dir
        self.metadata_file = os.path.join(base_dir, "metadata.json")
        self.metadata: Dict[str, FileMetadata] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Загружает метаданные из файла."""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.metadata = {
                        k: FileMetadata.from_dict(v) for k, v in data.items()
                    }
        except Exception as e:
            logger.error(f"Ошибка при загрузке метаданных: {e}")
            self.metadata = {}

    def _save_metadata(self) -> None:
        """Сохраняет метаданные в файл."""
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(
                    {k: v.to_dict() for k, v in self.metadata.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            logger.error(f"Ошибка при сохранении метаданных: {e}")

    def add_file(
        self,
        file_id: str,
        original_name: str,
        user_id: str,
        object_type: str,
        description: str = ""
    ) -> FileMetadata:
        """Добавляет новый файл в систему."""
        metadata = FileMetadata(
            file_id=file_id,
            original_name=original_name,
            user_id=user_id,
            upload_date=datetime.now(),
            object_type=object_type,
            description=description
        )
        self.metadata[file_id] = metadata
        self._save_metadata()
        return metadata

    def update_file_status(
        self,
        file_id: str,
        status: str,
        description: str = None
    ) -> Optional[FileMetadata]:
        """Обновляет статус файла."""
        if file_id in self.metadata:
            metadata = self.metadata[file_id]
            metadata.status = status
            metadata.last_update = datetime.now()
            if description is not None:
                metadata.description = description
            self._save_metadata()
            return metadata
        return None

    def get_user_files(self, user_id: str) -> List[FileMetadata]:
        """Получает все файлы пользователя."""
        return [
            metadata for metadata in self.metadata.values()
            if metadata.user_id == user_id
        ]

    def get_file_metadata(self, file_id: str) -> Optional[FileMetadata]:
        """Получает метаданные файла по его ID."""
        return self.metadata.get(file_id)

    def get_files_by_type(self, user_id: str, object_type: str) -> List[FileMetadata]:
        """Получает все файлы пользователя определенного типа."""
        return [
            metadata for metadata in self.metadata.values()
            if metadata.user_id == user_id and metadata.object_type == object_type
        ]

    def delete_file(self, file_id: str) -> bool:
        """Удаляет файл и его метаданные."""
        if file_id in self.metadata:
            try:
                # Удаляем физический файл
                file_path = os.path.join(self.base_dir, file_id)
                if os.path.exists(file_path):
                    os.remove(file_path)
                # Удаляем метаданные
                del self.metadata[file_id]
                self._save_metadata()
                return True
            except Exception as e:
                logger.error(f"Ошибка при удалении файла {file_id}: {e}")
        return False

    def cleanup_old_files(self, days: int = 30) -> int:
        """Удаляет старые файлы."""
        now = datetime.now()
        files_to_delete = [
            file_id for file_id, metadata in self.metadata.items()
            if (now - metadata.last_update).days > days
        ]
        
        deleted_count = 0
        for file_id in files_to_delete:
            if self.delete_file(file_id):
                deleted_count += 1
        
        return deleted_count 