from dataclasses import dataclass
from typing import List, Dict, Optional, Any, ClassVar
import boto3
from boto3.dynamodb.conditions import Key
import json
import uuid
from datetime import datetime
import os
from enum import Enum, auto

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
    def get_by_query(cls, query: str) -> Optional['LanguageEntry']:
        """Retrieve an entry by its query word"""
        table = cls.get_table()
        response = table.query(
            IndexName='query-index',
            KeyConditionExpression=Key('query').eq(query)
        )
        items = response.get('Items', [])
        return cls.from_dict(items[0]) if items else None

class LanguageLevel(Enum):
    """Enum for language proficiency levels according to CEFR"""
    A1 = "A1"  # Beginner
    A2 = "A2"  # Elementary
    B1 = "B1"  # Intermediate
    B2 = "B2"  # Upper Intermediate
    C1 = "C1"  # Advanced
    C2 = "C2"  # Proficiency
    
    @classmethod
    def from_string(cls, level_str: str) -> 'LanguageLevel':
        """Convert string to enum value, with validation"""
        try:
            return cls(level_str.upper())
        except ValueError:
            valid_levels = [level.value for level in cls]
            raise ValueError(f"Invalid level: {level_str}. Must be one of {', '.join(valid_levels)}")
    
    @classmethod
    def get_all_values(cls) -> List[str]:
        """Get all valid level values as strings"""
        return [level.value for level in cls]

@dataclass
class User:
    """User model for AnkiBot"""
    user_id: str
    level: LanguageLevel = LanguageLevel.A1
    context: str = ""
    admin: bool = False
    created_at: str = None
    
    DEFAULT_LEVEL: ClassVar[LanguageLevel] = LanguageLevel.A1
    DEFAULT_ADMIN: ClassVar[bool] = False
    
    def __post_init__(self):
        """Initialize default values if not provided"""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        # Convert string to enum if needed
        if isinstance(self.level, str):
            try:
                self.level = LanguageLevel(self.level)
            except ValueError:
                self.level = self.DEFAULT_LEVEL
    
    def to_dict(self) -> dict:
        """Convert to dictionary for DynamoDB"""
        return {
            'user_id': self.user_id,
            'level': self.level.value,  # Store enum value as string in DynamoDB
            'context': self.context,
            'admin': self.admin,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Create User instance from dictionary"""
        # Get level as string from DynamoDB and convert to enum
        level_str = data.get('level', cls.DEFAULT_LEVEL.value)
        try:
            level = LanguageLevel(level_str)
        except ValueError:
            level = cls.DEFAULT_LEVEL
        
        return cls(
            user_id=data['user_id'],
            level=level,
            context=data.get('context', ''),
            admin=data.get('admin', cls.DEFAULT_ADMIN),
            created_at=data.get('created_at')
        )
    
    @staticmethod
    def get_table():
        """Get the DynamoDB table for users"""
        return boto3.resource('dynamodb').Table('users')
    
    def save(self) -> None:
        """Save the user to DynamoDB"""
        table = self.get_table()
        table.put_item(Item=self.to_dict())
    
    @classmethod
    def get_user(cls, user_id):
        """Get a user by ID, or create if not exists"""
        table = cls.get_table()
        response = table.get_item(Key={'user_id': str(user_id)})
        
        if 'Item' in response:
            return cls.from_dict(response['Item'])
        else:
            # Create new user with default values
            new_user = cls(user_id=str(user_id))
            new_user.save()
            return new_user 