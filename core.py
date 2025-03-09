from dataclasses import dataclass
from typing import List, Dict, Optional
import boto3
from boto3.dynamodb.conditions import Key
import json
import uuid
from datetime import datetime

@dataclass
class Example:
    de: str
    ru: str
    audio_file: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'de': self.de,
            'ru': self.ru,
            'audio_file': self.audio_file
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Example':
        return cls(
            de=data['de'],
            ru=data['ru'],
            audio_file=data.get('audio_file')
        )

@dataclass
class LanguageEntry:
    query: str
    definition: str
    translation: str
    examples: List[Example]
    audio_file: Optional[str] = None
    id: str = None
    created_at: str = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'query': self.query,
            'definition': self.definition,
            'translation': self.translation,
            'examples': [ex.to_dict() for ex in self.examples],
            'audio_file': self.audio_file,
            'created_at': self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'LanguageEntry':
        return cls(
            id=data['id'],
            query=data['query'],
            definition=data['definition'],
            translation=data['translation'],
            examples=[Example.from_dict(ex) for ex in data['examples']],
            audio_file=data.get('audio_file'),
            created_at=data['created_at']
        )

    @staticmethod
    def get_table():
        dynamodb = boto3.resource('dynamodb')
        return dynamodb.Table('language_entries')

    def save(self) -> None:
        """Save the entry to DynamoDB"""
        table = self.get_table()
        table.put_item(Item=self.to_dict())

    @classmethod
    def get_by_id(cls, id: str) -> Optional['LanguageEntry']:
        """Retrieve an entry by its ID"""
        table = cls.get_table()
        response = table.get_item(Key={'id': id})
        item = response.get('Item')
        return cls.from_dict(item) if item else None

    @classmethod
    def get_by_query(cls, query: str) -> Optional['LanguageEntry']:
        """Retrieve an entry by its query word"""
        table = cls.get_table()
        response = table.query(
            IndexName='query-index',
            KeyConditionExpression=Key('query').eq(query)
        )
        items = response.get('Items', [])
        return cls.from_dict(items[0]) if items else None

    @classmethod
    def list_entries(cls, limit: int = 100) -> List['LanguageEntry']:
        """List all entries"""
        table = cls.get_table()
        response = table.scan(Limit=limit)
        return [cls.from_dict(item) for item in response.get('Items', [])] 