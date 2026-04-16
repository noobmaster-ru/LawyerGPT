import os
from typing import Dict, Union

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Config(BaseModel):
    base_url: str = Field(default='')
    model: str = Field(default='')
    password: str = Field(default='')
    rag_settings: dict = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        data = cls()._load_yaml(path) if os.path.exists(path) else {}

        data['base_url'] = os.getenv('X5_API_BASE_URL', data.get('base_url', ''))
        data['model'] = os.getenv('X5_MODEL', data.get('model', ''))
        data['password'] = os.getenv('X5_API_KEY', data.get('password', ''))

        return cls(**data)

    def _load_yaml(self, path: str) -> Dict[str, Union[str, bool, int, float]]:
        try:
            with open(path, 'r', encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data is None:
                raise ValueError(f"Failed to load YAML from {path}")
            return data
        except Exception as e:
            raise ValueError(f"Failed to parse YAML: {e}")


def get_database_url() -> str:
    url = os.getenv('DATABASE_URL')
    if url:
        return url
    user = os.getenv('POSTGRES_USER', 'legal_user')
    password = os.getenv('POSTGRES_PASSWORD', 'secret_password')
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'legal_db')
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def get_qdrant_settings() -> Dict[str, Union[str, int]]:
    return {
        'host': os.getenv('QDRANT_HOST', 'localhost'),
        'port': int(os.getenv('QDRANT_PORT', '6333')),
    }
