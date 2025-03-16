import json
from datetime import datetime
import anthropic
import os
import boto3
import hashlib
import time
from typing import List, Tuple, Optional
from core import LanguageEntry, Example, User, LanguageLevel
import asyncio
from concurrent.futures import ThreadPoolExecutor


def get_examples_from_claude(query: str, user_level: str = "B1", user_context: str = "") -> Tuple[str, str, List[Tuple[str, str]]]:
    """Get definition, translation and examples from Claude"""
    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    system_prompt = f"""You are a german language assistant for a {user_level} level student.
    First write a dictionary form of a word and its russian translation separated by |.
    If user input is a phrase with multiple words ­— dictionary form for phrases  should be if  possible infinitive with corresponding word order (verb last) and correc t government (case and prepositions).
    Dictionary form for single nouns should have singular and plural forms with definite article divided by commas.
    Dictionary form for single  verbs should have infinitive, present 3rd person singular, präteritum and partizip 2nd form with helper verb, divided by commas.
    Then provide 5 different simple usage examples of German Word and their Russian Translations. 
    Examples should be short enough. Try to use perfekt and present tenses. Answer only with a list, without any explanations, sticking to a following format: Example | Translation.
    Don't use any line numbers."""
    
    # Add user context if available
    if user_context:
        system_prompt += f"\n\nExamples should be related to the following context: {user_context}"
    
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

async def get_audio(text: str) -> Optional[str]:
    """Gets German audio using Amazon Polly and stores in S3 (async)"""
    try:
        filename = hashlib.md5(text.encode('utf-8')).hexdigest() + '.mp3'
        s3_key = f"audio/{filename}"
        
        # Check if file already exists in S3
        s3 = boto3.client('s3')
        try:
            s3.head_object(Bucket=os.environ['AUDIO_BUCKET'], Key=s3_key)
            print(f"Audio file already exists: {s3_key}")
            return filename
        except:
            print(f"Generating new audio for: {text}")
        
        # Start synthesis task
        polly = boto3.client('polly')
        response = polly.start_speech_synthesis_task(
            Text=text,
            OutputFormat='mp3',
            VoiceId='Vicki',
            LanguageCode='de-DE',
            Engine='neural',
            OutputS3BucketName=os.environ['AUDIO_BUCKET'],
            OutputS3KeyPrefix='audio/'
        )
        
        # Poll for completion asynchronously
        task_id = response['SynthesisTask']['TaskId']
        while True:
            status = polly.get_speech_synthesis_task(TaskId=task_id)
            task_status = status['SynthesisTask']['TaskStatus']
            
            if task_status == 'completed':
                # Get Polly's output file path
                polly_uri = status['SynthesisTask']['OutputUri']
                polly_key = polly_uri.split(os.environ['AUDIO_BUCKET'] + '/')[1]
                
                # Copy to our desired filename
                s3.copy_object(
                    Bucket=os.environ['AUDIO_BUCKET'],
                    CopySource=f"{os.environ['AUDIO_BUCKET']}/{polly_key}",
                    Key=s3_key
                )
                
                # Delete original Polly file
                s3.delete_object(
                    Bucket=os.environ['AUDIO_BUCKET'],
                    Key=polly_key
                )
                
                print(f"Generated and renamed audio to: {s3_key}")
                return filename
            elif task_status == 'failed':
                print(f"Failed to generate audio: {status['SynthesisTask']['TaskStatusReason']}")
                return None
                
            await asyncio.sleep(0.5)
            
    except Exception as e:
        print(f"Error generating/storing audio for '{text}': {str(e)}")
        return None

async def generate_audio_files(query: str, example_texts: List[str]) -> Tuple[str, List[str]]:
    """Generate audio files for query and examples in parallel"""
    # Create tasks for all audio generations
    tasks = [
        get_audio(query),  # Query audio
        *[get_audio(text) for text in example_texts]  # Example audios
    ]
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)
    
    # First result is query audio, rest are example audios
    return results[0], results[1:]

def create_language_entry(query: str, user_level: str = "B1", user_context: str = "") -> LanguageEntry:
    """Creates a new LanguageEntry for the given query"""
    # Get content from Claude
    definition, translation, example_pairs = get_examples_from_claude(query, user_level, user_context)
    
    # Create Example objects (without audio yet)
    examples = [
        Example(de=de, ru=ru)
        for de, ru in example_pairs
    ]
    
    # Generate all audio files in parallel
    loop = asyncio.get_event_loop()
    query_audio, example_audios = loop.run_until_complete(
        generate_audio_files(
            query=query,
            example_texts=[ex.de for ex in examples]
        )
    )
    
    # Attach audio files to examples
    for example, audio in zip(examples, example_audios):
        example.audio_file = audio
    
    # Create and return the entry
    return LanguageEntry(
        query=query,
        definition=definition,
        translation=translation,
        examples=examples,
        audio_file=query_audio
    )

def lambda_handler(event, context):
    """Process messages from SQS queue"""
    try:
        print("Received event:", json.dumps(event, indent=2))
        
        for record in event['Records']:
            message = json.loads(record['body'])
            
            # Get user data if user_id is available
            user_level = "B1"  # Default level
            user_context = ""  # Default empty context
            
            if 'user_id' in message:
                user = User.get_user(message['user_id'])
                user_level = user.level.value
                user_context = user.context
            
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
                    entry = create_language_entry(line, user_level, user_context)
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