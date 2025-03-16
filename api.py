import json
import os
import boto3
import jinja2
from core import LanguageEntry
from pathlib import Path

# Initialize Jinja2 environment
template_dir = Path(os.path.dirname(os.path.abspath(__file__))) / 'templates'
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir),
    autoescape=jinja2.select_autoescape(['html', 'xml'])
)

# Define routes
ROUTES = {
    'GET': {
        '/collection': 'get_collection',
    }
}

def get_collection():
    """Get all language entries and render them as HTML"""
    try:
        # Get all entries from DynamoDB
        entries = LanguageEntry.get_table().scan()
        items = entries.get('Items', [])
        
        # Render template
        template = jinja_env.get_template('collection.html')
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': template.render(items=items)
        }
    except Exception as e:
        print(f"Error in get_collection: {str(e)}")
        template = jinja_env.get_template('error.html')
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': template.render(error=str(e))
        }

def lambda_handler(event, context):
    """AWS Lambda handler for API Gateway"""
    try:
        # Extract path and method
        path = event.get('path', '')
        http_method = event.get('httpMethod', 'GET')
        
        # Debug logging
        print(f"API Request: {http_method} {path}")
        print(f"Event: {json.dumps(event)}")
        
        # Normalize path for routing
        if path == '/collection/':
            path = '/collection'
        
        # Find matching route
        if http_method in ROUTES and path in ROUTES[http_method]:
            # Get handler function
            handler_name = ROUTES[http_method][path]
            handler = globals()[handler_name]
            
            # Call handler
            return handler()
        # Handle proxy paths
        elif path.startswith('/collection/'):
            # Extract the ID and action from the path
            parts = path.split('/')
            if len(parts) >= 3:
                item_id = parts[2]
                action = parts[3] if len(parts) >= 4 else None
                
                if action == 'audio':
                    # Future implementation for audio playback
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'text/html'
                        },
                        'body': f'<audio controls autoplay><source src="/audio/{item_id}.mp3" type="audio/mpeg">Your browser does not support the audio element.</audio>'
                    }
        else:
            # Route not found
            template = jinja_env.get_template('not_found.html')
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'text/html'
                },
                'body': template.render(path=path, method=http_method)
            }
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f"<html><body><h1>Server Error</h1><p>{str(e)}</p></body></html>"
        } 