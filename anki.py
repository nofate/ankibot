import genanki
import io
import random
import boto3
import os
from dotenv import load_dotenv

load_dotenv()
# Constants
AUDIO_BUCKET = os.environ.get('AUDIO_BUCKET')

# Define note model
MODEL = genanki.Model(
    1607392319,
    'German Word',
    fields=[
        {'name': 'Word'},
        {'name': 'Definition'},
        {'name': 'Translation'},
        {'name': 'Examples'},
        {'name': 'Audio'}
    ],
    templates=[{
        'name': 'Card 1',
        'qfmt': '{{Word}}<br>{{Audio}}',
        'afmt': '''
            {{FrontSide}}
            <hr id="answer">
            <b>{{Definition}}</b><br>
            <i>{{Translation}}</i><br>
            <br>
            {{Examples}}
        '''
    }]
)

def create_anki_deck(entries):
    """Create an Anki deck from language entries"""
    try:
        print(f"Starting deck creation with {len(entries)} entries")
        print(f"Using audio bucket: {AUDIO_BUCKET}")
        
        # Create temp directory for media files
        import tempfile
        import shutil
        temp_dir = tempfile.mkdtemp()
        print(f"Created temp directory: {temp_dir}")
        
        try:
            # Create Anki deck
            deck_id = random.randrange(1 << 30, 1 << 31)
            print(f"Generated deck_id: {deck_id}")
            
            deck = genanki.Deck(
                deck_id=deck_id,
                name='German Vocabulary'
            )
            
            # Add notes to deck
            media_files = []  # Track media files here
            s3 = boto3.client('s3')
            
            for i, entry in enumerate(entries):
                print(f"\nProcessing entry {i+1}/{len(entries)}:")
                print(f"Entry data: {entry}")
                
                # Download main audio if exists
                if entry.get('audio_file'):
                    print(f"Downloading main audio: {entry['audio_file']}")
                    audio_path = os.path.join(temp_dir, entry['audio_file'])
                    with open(audio_path, 'wb') as f:
                        s3.download_fileobj(
                            AUDIO_BUCKET,
                            f"audio/{entry['audio_file']}",
                            f
                        )
                    media_files.append(audio_path)
                
                # Format examples and download their audio
                examples_html = '<ul>'
                for j, ex in enumerate(entry.get('examples', [])):
                    print(f"Processing example {j+1}: {ex}")
                    examples_html += f'<li>{ex.get("de", "")}<br>{ex.get("ru", "")}</li>'
                    
                    if ex.get('audio_file'):
                        print(f"Downloading example audio: {ex['audio_file']}")
                        audio_path = os.path.join(temp_dir, ex['audio_file'])
                        with open(audio_path, 'wb') as f:
                            s3.download_fileobj(
                                AUDIO_BUCKET,
                                f"audio/{ex['audio_file']}",
                                f
                            )
                        media_files.append(audio_path)
                        examples_html += f'<br>[sound:{ex["audio_file"]}]'
                examples_html += '</ul>'
                
                # Create note
                fields = [
                    entry.get('query', ''),
                    entry.get('definition', ''),
                    entry.get('translation', ''),
                    examples_html,
                    f'[sound:{entry["audio_file"]}]' if entry.get('audio_file') else ''
                ]
                print(f"Note fields: {fields}")
                
                note = genanki.Note(
                    model=MODEL,
                    fields=fields
                )
                deck.add_note(note)
            
            print("\nCreating package...")
            package = genanki.Package(deck)
            
            print(f"\nWriting package with {len(media_files)} media files...")
            # Create a temporary file for the package
            with tempfile.NamedTemporaryFile(suffix='.apkg', delete=False) as temp_file:
                package.media_files = media_files
                package.write_to_file(temp_file.name)
                
                # Read the generated file into memory
                with open(temp_file.name, 'rb') as f:
                    package_data = f.read()
                    
            # Clean up temp files
            os.unlink(temp_file.name)
            
            # Return the package data as a BytesIO object
            package_buf = io.BytesIO(package_data)
            
            print("Deck creation completed successfully")
            return package_buf
            
        finally:
            # Clean up temp directory
            print(f"Cleaning up temp directory: {temp_dir}")
            shutil.rmtree(temp_dir)
        
    except Exception as e:
        print(f"Error in create_anki_deck: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    from core import LanguageEntry
    
    # Load environment variables

    
    # Verify environment
    if not AUDIO_BUCKET:
        print("Error: AUDIO_BUCKET environment variable is not set")
        exit(1)
        
    try:
        print(f"Using audio bucket: {AUDIO_BUCKET}")
        
        # Get all entries from DynamoDB
        entries = LanguageEntry.get_table().scan().get('Items', [])
        
        if not entries:
            print("No entries found in DynamoDB")
            exit(1)
            
        print(f"Found {len(entries)} entries in DynamoDB")
        
        # Create deck
        deck_buf = create_anki_deck(entries)
        
        # Save to file
        with open('test_deck.apkg', 'wb') as f:
            f.write(deck_buf.getvalue())
            
        print("\nTest deck saved as 'test_deck.apkg'")
        
    except Exception as e:
        print(f"Test failed: {str(e)}") 