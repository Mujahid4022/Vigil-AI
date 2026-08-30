"""
facebook_client.py - Facebook Graph API wrapper for Vigil AI.

This module handles all interactions with Facebook:
- Posting text + images to a page
- Posting videos
- Replying to user messages
- Liking and commenting on posts
- Fetching post insights
"""

import requests
import os
import time
import urllib.parse
import re
from config.config import FB_GRAPH_API_VERSION


# ----------------------------------------------------------------------
# Helper: Add UTM tracking parameters to a single URL
# ----------------------------------------------------------------------
def add_utm_parameters(url, source="facebook", medium="social", campaign="vigil_ai"):
    """Adds UTM tracking parameters to a URL for Google Analytics."""
    if not url:
        return url

    parsed = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed.query)

    query_params["utm_source"] = [source]
    query_params["utm_medium"] = [medium]
    query_params["utm_campaign"] = [campaign]
    query_params["utm_term"] = ["automated_post"]

    new_query = urllib.parse.urlencode(query_params, doseq=True)
    new_url = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )
    return new_url


# ----------------------------------------------------------------------
# Helper: Add UTM parameters to ALL URLs inside a text message
# ----------------------------------------------------------------------
def add_utm_to_text(text):
    """Finds all URLs in a string and adds UTM parameters to each."""
    if not text:
        return text

    # Regex to find URLs
    url_pattern = re.compile(r'https?://[^\s]+')
    urls = url_pattern.findall(text)
    for url in urls:
        # Avoid adding UTM twice if already present
        if "utm_source=" in url:
            continue
        new_url = add_utm_parameters(url)
        text = text.replace(url, new_url)
    return text


# ----------------------------------------------------------------------
# 1. Post text with an optional image to a Facebook Page
# ----------------------------------------------------------------------
def post_to_facebook(
    access_token: str, page_id: str, message: str, image_path: str = None
) -> str:
    """
    Posts a message (and optionally an image) to a Facebook Page.

    Args:
        access_token (str): Page access token.
        page_id (str): The Facebook Page ID.
        message (str): The text to post.
        image_path (str, optional): Path to an image file. If provided,
            we post as a photo; otherwise we post a simple status.

    Returns:
        str: The Facebook post ID if successful, or None on error.
    """
    # ---- AUTOMATIC UTM INJECTION ----
    message = add_utm_to_text(message)

    if image_path and os.path.exists(image_path):
        photo_url = (
            f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{page_id}/photos"
        )
        with open(image_path, "rb") as img_file:
            files = {"source": img_file}
            data = {"message": message, "access_token": access_token}
            response = requests.post(photo_url, files=files, data=data)
    else:
        url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{page_id}/feed"
        payload = {"message": message, "access_token": access_token}
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
# 2. Post a video to a Facebook Page
# ----------------------------------------------------------------------
def post_video_to_facebook(
    page_id: str,
    access_token: str,
    caption: str,
    video_path: str = None,
    video_url: str = None,
) -> str:
    """
    Posts a video to a Facebook Page.
    Provide either a local video_path or a public video_url.
    """
    # ---- AUTOMATIC UTM INJECTION ----
    caption = add_utm_to_text(caption)

    if not video_path and not video_url:
        print("❌ No video source provided.")
        return None

    data = {
        "title": caption[:100],
        "description": caption,
        "access_token": access_token,
    }

    try:
        if video_path and os.path.exists(video_path):
            fb_url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{page_id}/videos"
            with open(video_path, "rb") as video_file:
                files = {"source": video_file}
                response = requests.post(fb_url, files=files, data=data)
        elif video_url:
            fb_url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{page_id}/videos"
            data["file_url"] = video_url
            response = requests.post(fb_url, data=data)
        else:
            return None

        result = response.json()
        if "id" in result:
            print(f"✅ Video posted successfully! ID: {result['id']}")
            return result["id"]
        else:
            print(f"❌ Video FB Error: {result}")
            return None
    except Exception as e:
        print(f"❌ Video upload error: {e}")
        return None


# ----------------------------------------------------------------------
# 3. Send a reply to a user's message (for inbox responses)
# ----------------------------------------------------------------------
def send_reply(recipient_id: str, message_text: str, page_access_token: str) -> bool:
    """
    Sends a text reply to a specific user via Facebook Messenger.
    """
    # ---- AUTOMATIC UTM INJECTION ----
    message_text = add_utm_to_text(message_text)

    url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
        "access_token": page_access_token,
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print(f"✅ Reply sent to {recipient_id}")
        return True
    else:
        print(f"❌ Reply failed: {response.json()}")
        return False


# ----------------------------------------------------------------------
# 4. Like a Facebook Post
# ----------------------------------------------------------------------
def like_post(post_id: str, access_token: str) -> bool:
    """
    Likes a specific post using the page token.
    """
    try:
        url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{post_id}/likes"
        response = requests.post(url, data={"access_token": access_token})
        if response.status_code == 200:
            print(f"✅ Liked post {post_id}")
            return True
        else:
            print(f"❌ Like failed: {response.json()}")
            return False
    except Exception as e:
        print(f"❌ Like error: {e}")
        return False


# ----------------------------------------------------------------------
# 5. Comment on a Facebook Post
# ----------------------------------------------------------------------
def comment_on_post(post_id: str, message: str, access_token: str) -> str:
    """
    Comments on a specific post using the page token.
    Returns the comment ID if successful, else None.
    """
    # ---- AUTOMATIC UTM INJECTION ----
    message = add_utm_to_text(message)

    try:
        url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{post_id}/comments"
        data = {"message": message, "access_token": access_token}
        response = requests.post(url, data=data)
        result = response.json()
        if "id" in result:
            print(f"✅ Commented on post {post_id}")
            return result["id"]
        else:
            print(f"❌ Comment failed: {result}")
            return None
    except Exception as e:
        print(f"❌ Comment error: {e}")
        return None


# ----------------------------------------------------------------------
# 6. Get Post Insights (Performance Analytics)
# ----------------------------------------------------------------------
def get_post_insights(post_id: str, access_token: str) -> dict:
    """
    Fetches engagement metrics for a specific post.
    Returns a dict with impressions, reach, likes, comments, shares.
    """
    metrics = [
        "post_impressions",
        "post_engaged_users",
        "post_clicks",
        "post_like_count",
        "post_comment_count",
        "post_share_count",
    ]
    metric_string = ",".join(metrics)
    url = (
        f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{post_id}/insights"
        f"?metric={metric_string}&access_token={access_token}"
    )

    try:
        response = requests.get(url)
        data = response.json()
        if "data" in data:
            result = {}
            for item in data["data"]:
                result[item["name"]] = item["values"][0]["value"]
            return result
        else:
            print(f"⚠️ No insights data for {post_id}")
            return None
    except Exception as e:
        print(f"❌ Insights error: {e}")
        return None


# ----------------------------------------------------------------------
# 7. Get page info – for debugging
# ----------------------------------------------------------------------
def get_page_info(access_token: str, page_id: str):
    """
    Fetches basic page details (name, category, etc.) to verify the token works.
    """
    url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{page_id}"
    params = {"access_token": access_token, "fields": "name,category"}
    response = requests.get(url, params=params)
    return response.json()

# ----------------------------------------------------------------------
# 8. Post to Instagram Feed (Business Account)
# ----------------------------------------------------------------------
def post_to_instagram(
    ig_user_id: str,
    access_token: str,
    caption: str,
    image_bytes: bytes = None,
    image_path: str = None,
    image_url: str = None,
) -> str:
    """
    Posts an image to Instagram Feed.
    Supports image_url (public URL), image_bytes, or image_path.
    """
    if not image_url and not image_bytes and not image_path:
        print("❌ No image provided for Instagram.")
        return None

    try:
        # Step 1: Create media container
        container_url = f"https://graph.facebook.com/v26.0/{ig_user_id}/media"
        data = {"caption": caption[:2200], "access_token": access_token}
        files = None

        if image_url:
            # RECOMMENDED: Use a public URL
            data["image_url"] = image_url
        elif image_path and os.path.exists(image_path):
            files = {"image": open(image_path, "rb")}
        elif image_bytes:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(image_bytes)
                temp_path = tmp.name
            files = {"image": open(temp_path, "rb")}

        # Send the request
        if files:
            response = requests.post(container_url, files=files, data=data)
        else:
            response = requests.post(container_url, data=data)

        result = response.json()
        if "id" not in result:
            print(f"❌ Instagram container error: {result}")
            return None
        container_id = result["id"]

        # Clean up temp file if created
        if files and 'temp_path' in locals():
            os.remove(temp_path)

        # Step 2: Publish the container
        publish_url = f"https://graph.facebook.com/v26.0/{ig_user_id}/media_publish"
        publish_data = {
            "creation_id": container_id,
            "access_token": access_token,
        }
        publish_response = requests.post(publish_url, data=publish_data)
        publish_result = publish_response.json()

        if "id" in publish_result:
            print(f"✅ Instagram post successful! ID: {publish_result['id']}")
            return publish_result["id"]
        else:
            print(f"❌ Instagram publish error: {publish_result}")
            return None
    except Exception as e:
        print(f"❌ Instagram error: {e}")
        return None


# ----------------------------------------------------------------------
# Simple test when run directly
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("Facebook client module loaded. Use the functions with valid tokens.")