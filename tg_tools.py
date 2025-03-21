"""
Telegram Mini App utilities for authentication and validation
"""
import os
import json
import hmac
import hashlib
from urllib.parse import unquote
from aws_lambda_powertools import Logger
from aws_lambda_powertools.middleware_factory import lambda_handler_decorator
from typing import Callable, Dict, Any
from aws_lambda_powertools.utilities.typing import LambdaContext


# Initialize logger
logger = Logger()

# Get environment variables
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

def validate_tg_init_data(init_data_str):
    """
    Validate Telegram initData according to the official documentation:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    
    Args:
        init_data_str (str): The raw initData string from Telegram
        
    Returns:
        tuple: (is_valid, user_data) - Boolean indicating if data is valid and user data if available
    """
    try:
        # Check if we have a token to validate with
        if not TELEGRAM_TOKEN:
            logger.warning("TELEGRAM_TOKEN not set, skipping validation")
            return False, None
            
        # Parse the query string
        parsed_data = {}
        for param in init_data_str.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                parsed_data[key] = unquote(value)
        
        # Extract the hash
        received_hash = parsed_data.get('hash')
        if not received_hash:
            logger.warning("No hash found in initData")
            return False, None
            
        # Remove hash from the data
        data_without_hash = parsed_data.copy()
        data_without_hash.pop('hash', None)
        
        # Sort in alphabetical order
        data_check_array = []
        for key in sorted(data_without_hash.keys()):
            data_check_array.append(f"{key}={data_without_hash[key]}")
        
        # Create the data check string
        data_check_string = '\n'.join(data_check_array)
        
        # Create the secret key by HMAC-SHA256 of "WebAppData" with the bot token
        secret_key = hmac.new(
            key="WebAppData".encode(),
            msg=TELEGRAM_TOKEN.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        # Calculate the HMAC-SHA256 of the data check string with the secret
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Compare the hashes
        is_valid = calculated_hash == received_hash
        
        # Extract user data if available
        user_data = None
        if is_valid and 'user' in parsed_data:
            try:
                user_data = json.loads(parsed_data['user'])
                logger.info(f"Validated Telegram user: {user_data.get('id')}")
            except json.JSONDecodeError:
                logger.error("Failed to parse user JSON data")
        
        return is_valid, user_data
    except Exception as e:
        logger.error(f"Error validating Telegram initData: {str(e)}")
        return False, None


@lambda_handler_decorator
def session_middleware(
    handler: Callable[[Dict[str, Any], LambdaContext], Dict[str, Any]],
    event: Dict[str, Any],
    context: LambdaContext,
) -> Dict[str, Any]:
    """
    Middleware to validate Telegram initData and store user information in the request context
    
    Args:
        handler: The Lambda handler function
        event: The Lambda event
        context: The Lambda context
        
    Returns:
        The result of the handler function
    """
    # Get Authorization header
    headers = event.get('headers', {}) or {}
    auth_header = headers.get('Authorization') or headers.get('authorization', '')
    logger.debug(f"Authorization header: {auth_header[:20]}..." if auth_header else "No Authorization header")
    
    # Extract initData from Authorization header
    init_data = None
    if auth_header.startswith('Telegram '):
        init_data = auth_header[9:]  # Remove 'Telegram ' prefix
        logger.debug(f"Found initData in Authorization header: {init_data[:20]}...")

    if init_data:
        logger.warning("No initData found in query parameters")
    
    is_valid = False
    user_data = None
    user_id = None
    
    if init_data:
        is_valid, user_data = validate_tg_init_data(init_data)
        if is_valid and user_data:
            user_id = str(user_data.get('id'))
            logger.info(f"Valid Telegram initData received for user: {user_id}")
        else:
            logger.warning("Invalid Telegram initData received")
            if user_data:
                logger.debug(f"User data present but validation failed: {user_data}")
    
    # Store authentication results in the event context
    if 'requestContext' not in event:
        event['requestContext'] = {}
        logger.debug("Created requestContext in event")
        
    if 'authorizer' not in event['requestContext']:
        event['requestContext']['authorizer'] = {}
        logger.debug("Created authorizer in requestContext")
        
    event['requestContext']['authorizer']['is_authenticated'] = is_valid
    event['requestContext']['authorizer']['user_data'] = user_data
    event['requestContext']['authorizer']['user_id'] = user_id
    logger.debug(f"Updated authorizer with is_authenticated={is_valid}, user_id={user_id}")
    
    # Call the handler with the modified event
    logger.debug("Calling handler with modified event")
    return handler(event, context) 