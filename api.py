import os
import jinja2
from core import LanguageEntry
from pathlib import Path
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler import content_types
from aws_lambda_powertools.event_handler.api_gateway import Response
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
    NotFoundError,
    ServiceError,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent


# Initialize Jinja2 environment
template_dir = Path(os.path.dirname(os.path.abspath(__file__))) / 'templates'
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir),
    autoescape=jinja2.select_autoescape(['html', 'xml'])
)

# Initialize logger and API resolver
logger = Logger()
app = APIGatewayRestResolver()
# Initialize global context dictionary
context_dict = {'stage_name': ''}

# HTML response helper
def html_response(body, status_code=200):
    """Return a Response object with HTML content type"""
    return Response(
        status_code=status_code,
        content_type=content_types.TEXT_HTML,
        body=body,
    )

# Error handler
def error_handler(e, status_code=500):
    """Handle exceptions and return appropriate HTML response"""
    logger.exception("Error occurred")
    template = jinja_env.get_template('error.html')
    stage_name = context_dict.get('stage_name', '')
    
    # Render the error template
    error_html = template.render(error=str(e), stage_name=stage_name)
    
    # Raise the appropriate exception based on status code
    if status_code == 400:
        raise BadRequestError(error_html)
    elif status_code == 404:
        raise NotFoundError(error_html)
    else:
        raise InternalServerError(error_html)

# Route handlers
@app.get("/collection")
def get_collection():
    """Get all language entries and render them as HTML"""
    try:
        # Get all entries from DynamoDB
        entries = LanguageEntry.get_table().scan()
        items = entries.get('Items', [])
        
        # Get stage name from the global context
        stage_name = context_dict.get('stage_name', '')
        
        # Render template
        template = jinja_env.get_template('collection.html')
        return html_response(template.render(
            items=items,
            stage_name=stage_name
        ))
    except Exception as e:
        error_handler(e)  # This will raise an InternalServerError

@app.delete("/collection/<item_id>")
def delete_entry(item_id):
    """Delete a language entry"""
    try:
        # Delete the entry from DynamoDB
        LanguageEntry.get_table().delete_item(
            Key={
                'id': item_id
            }
        )
        
        # Return an empty response (HTMX will remove the element)
        return html_response("")
    except Exception as e:
        logger.exception(f"Error deleting entry {item_id}")
        raise ServiceError(f'<div class="error">Error deleting entry: {str(e)}</div>')

@app.get("/collection/<item_id>/audio")
def get_audio(item_id):
    """Get audio for a language entry"""
    try:
        # Future implementation for audio playback
        return html_response(f'<audio controls autoplay><source src="/audio/{item_id}.mp3" type="audio/mpeg">Your browser does not support the audio element.</audio>')
    except Exception as e:
        error_handler(e)  # This will raise an InternalServerError

# Not found handler
@app.not_found
def not_found_handler(path, method):
    template = jinja_env.get_template('not_found.html')
    stage_name = context_dict.get('stage_name', '')
    error_html = template.render(path=path, method=method, stage_name=stage_name)
    raise NotFoundError(error_html)

# Exception handler for API Gateway
@app.exception_handler(BadRequestError)
def handle_bad_request_error(ex: BadRequestError):
    """Handle BadRequestError exceptions"""
    return html_response(str(ex), 400)

@app.exception_handler(NotFoundError)
def handle_not_found_error(ex: NotFoundError):
    """Handle NotFoundError exceptions"""
    return html_response(str(ex), 404)

@app.exception_handler(InternalServerError)
def handle_internal_server_error(ex: InternalServerError):
    """Handle InternalServerError exceptions"""
    return html_response(str(ex), 500)

@app.exception_handler(ServiceError)
def handle_service_error(ex: ServiceError):
    """Handle ServiceError exceptions"""
    return html_response(str(ex), 500)

@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event, context: LambdaContext):
    """AWS Lambda handler for API Gateway"""
    try:
        # Debug logging
        logger.info("API Request", extra={
            "path": event.get('path', ''),
            "method": event.get('httpMethod', 'GET')
        })
        
        # Extract stage name from the event
        request_context = event.get('requestContext', {})
        stage = request_context.get('stage', '')
        stage_name = f"/{stage}" if stage else ""
        
        # Update global context
        global context_dict
        context_dict = {'stage_name': stage_name}
        
        # Handle the request with the resolver
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Unhandled error in lambda_handler")
        # Create a basic HTML error page for truly unexpected errors
        error_html = f"<html><body><h1>Server Error</h1><p>{str(e)}</p></body></html>"
        return html_response(error_html, 500) 