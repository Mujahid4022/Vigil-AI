"""
facebook_client.py - Facebook Graph API wrapper for Vigil AI.

This module handles all interactions with Facebook:
- Posting text + images to a page
- Replying to user messages (for the deals engine)
"""

import requests
import os
from config.config import FB_GRAPH_API_VERSION

# ----------------------------------------------------------------------
# 1. Post text with an optional image to a Facebook Page
# ----------------------------------------------------------------------
def post_to_facebook(access_token: str, page_id: str, message: str, image_path: str = None) -> str:
    """
    Posts a message (and optionally an image) to a Facebook Page.
    
    Args:
        access_token (str): Page access token.
        page_id (str): The Facebook Page ID.
        message (str): The text to post.
        image_path (str, optional): Path to an image file. If provided,
            we post as a photo; otherwise we post a simple status.
    
    Returns:
        str: The Facebook post ID if successful, or an error message.
    """
    # Facebook Graph API URL
    url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{page_id}/feed"

    # Prepare the payload – always include the message
    payload = {
        "message": message,
        "access_token": access_token
    }

    # If an image is provided, we need to upload it separately.
    # The simplest way: use the 'photos' endpoint with the image as a file.
    # We'll use a different endpoint for photos.
    if image_path and os.path.exists(image_path):
        # Use the /photos endpoint for image posts
        photo_url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{page_id}/photos"
        files = {
            "source": open(image_path, "rb")
        }
        data = {
            "message": message,
            "access_token": access_token
        }
        response = requests.post(photo_url, files=files, data=data)
        # Close the file handle
        files["source"].close()
    else:
        # No image – just a text post
        response = requests.post(url, data=payload)

    if response.status_code == 200:
        result = response.json()
        post_id = result.get("id")
        print(f"✅ Post successful! ID: {post_id}")
        return post_id
    else:
        error = response.json()
        print(f"❌ Facebook error: {error}")
        return None

# ----------------------------------------------------------------------
# 2. Send a reply to a user's message (for inbox responses)
# ----------------------------------------------------------------------
def send_reply(recipient_id: str, message_text: str, page_access_token: str) -> bool:
    """
    Sends a text reply to a specific user via Facebook Messenger.
    
    Args:
        recipient_id (str): The Facebook ID of the user who sent the message.
        message_text (str): The reply text.
        page_access_token (str): The page access token (with 'pages_messaging' permission).
    
    Returns:
        bool: True if successful, False otherwise.
    """
    url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
        "access_token": page_access_token
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print(f"✅ Reply sent to {recipient_id}")
        return True
    else:
        print(f"❌ Reply failed: {response.json()}")
        return False

# ----------------------------------------------------------------------
# 3. (Optional) Get page info – for debugging
# ----------------------------------------------------------------------
def get_page_info(access_token: str, page_id: str):
    """
    Fetches basic page details (name, category, etc.) to verify the token works.
    """
    url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{page_id}"
    params = {
        "access_token": access_token,
        "fields": "name,category"
    }
    response = requests.get(url, params=params)
    return response.json()

# ----------------------------------------------------------------------
# Simple test when run directly
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # This is just for testing – you would need real tokens
    print("Facebook client module loaded. Use the functions with valid tokens.")