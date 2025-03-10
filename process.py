import json
from datetime import datetime
import anthropic
import os
import boto3
import hashlib
import time
from typing import List, Tuple
from core import LanguageEntry, Example


def get_examples_from_claude(query: str) -> Tuple[str, str, List[Tuple[str, str]]]:
    """Get definition, translation and examples from Claude"""
    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    system_prompt = """You are a german language assistant for a B1 student learning B2 Niveau.
    First write a dictionary form of a word and its russian translation separated by |.
    Then provide 5 different simple usage examples of German Word and their Russian Translations.
    Examples should be short enough. Answer only with a list, without any explanations, sticking to a following format: Example | Translation.
    Don't use any line numbers."""
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": query
            }
        ]
    )
    
    response = message.content[0].text
    return parse_claude_response(response)

def parse_claude_response(response: str) -> Tuple[str, str, List[Tuple[str, str]]]:
    """Parses the Claude response into definition, translation and example pairs"""
    lines = [line.strip() for line in response.split('\n') if line.strip()]
    
    definition_line = lines[0]
    definition, translation = definition_line.split('|')
    
    # Return example pairs instead of creating Example objects
    example_pairs = []
    for line in lines[1:]:
        if '|' in line:
            de, ru = line.split('|')
            example_pairs.append((de.strip(), ru.strip()))
    
    return definition.strip(), translation.strip(), example_pairs

def get_audio(text: str) -> str:
    """Gets German audio using Amazon Polly"""
    try:
        polly = boto3.client('polly')
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId='Vicki',
            LanguageCode='de-DE',
            Engine='neural'
        )
        
        if "AudioStream" in response:
            filename = hashlib.md5(text.encode('utf-8')).hexdigest() + '.mp3'
            return filename
            
    except Exception as e:
        print(f"Error generating audio for '{text}': {str(e)}")
        return None


def generate_audio_files(query: str, example_texts: List[str]) -> Tuple[str, List[str]]:
    """Generate audio files for query and examples"""
    # Get audio for the query word
    query_audio = get_audio(query)
    
    # Get audio for each example
    example_audios = []
    for text in example_texts:
        audio = get_audio(text)
        example_audios.append(audio)
        time.sleep(1)  # Avoid rate limiting
        
    return query_audio, example_audios


def create_language_entry(query: str) -> LanguageEntry:
    """Creates a new LanguageEntry for the given query"""
    # Get content from Claude
    definition, translation, example_pairs = get_examples_from_claude(query)
    
    # Create Example objects (without audio yet)
    examples = [
        Example(de=de, ru=ru)
        for de, ru in example_pairs
    ]
    
    # # Generate all audio files
    # query_audio, example_audios = generate_audio_files(
    #     query=query,
    #     example_texts=[ex.de for ex in examples]
    # )
    
    # # Attach audio files to examples
    # for example, audio in zip(examples, example_audios):
    #     example.audio_file = audio
    
    # Create and return the entry
    return LanguageEntry(
        query=query,
        definition=definition,
        translation=translation,
        examples=examples,
        # audio_file=query_audio
    )



def lambda_handler(event, context):
    """Process messages from SQS queue"""
    try:
        print("Received event:", json.dumps(event, indent=2))
        
        for record in event['Records']:
            message = json.loads(record['body'])
            
            # Split message into lines and clean them
            lines = [line.strip() for line in message['text'].split('\n') if line.strip()]
            
            for line in lines:
                try:
                    print(f"Processing line: {line}")
                    
                    # Check if entry already exists
                    existing_entry = LanguageEntry.get_by_query(line)
                    if existing_entry:
                        print(f"Entry already exists for: {line}")
                        continue
                    
                    # Create and save new entry
                    entry = create_language_entry(line)
                    entry.save()
                    
                    print(f"Successfully processed and saved: {line}")
                    
                except Exception as e:
                    print(f"Error processing line '{line}': {str(e)}")
                    continue
            
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f"Processed message from user {message.get('username')}",
                'timestamp': datetime.utcnow().isoformat()
            })
        }
            
    except Exception as e:
        print(f"Error processing messages: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        } 