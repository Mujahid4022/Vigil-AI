"""
engine_1_urdu_poetry.py - Engine 1: Urdu Poetry Generator and Poster.

This module:
- Generates a new Urdu poem using Gemini
- Renders it onto an image with the Jameel Noori Nastaliq font
- Posts it to the Urdu Poetry Facebook page
- Records the post in the database to avoid repeats
"""

import os
from datetime import datetime
from config.config import FB_PAGE_ID_URDU, get_page_token
from src.core.facebook_client import post_to_facebook
from src.models.database import add_post, post_exists
from src.utils.text_processor import generate_urdu_poetry, reshape_urdu_text
from src.utils.image_renderer import render_poetry_to_image

# ----------------------------------------------------------------------
# Main function: run the entire engine
# ----------------------------------------------------------------------
def run_engine_1():
    """
    Orchestrates poetry generation, rendering, posting, and tracking.
    """
    print(f"🔄 [Engine 1] Starting at {datetime.now()}")

    # --- Get the token dynamically from config.json ---
    token = get_page_token(FB_PAGE_ID_URDU)
    if not token:
        print("❌ Urdu Page Token not found in config.json. Aborting.")
        return

    # 1. Generate poem
    poem = generate_urdu_poetry()
    if not poem:
        print("❌ No poem generated. Aborting.")
        return

    # 2. Check if this poem was already posted (using hash)
    if post_exists(poem):
        print("⚠️ This poem already exists in the database. Skipping.")
        return

    # 3. Render the poem to an image
    image_path = os.path.join("data", f"urdu_poem_{int(datetime.now().timestamp())}.png")
    render_poetry_to_image(poem, image_path)

    # 4. Post to Facebook
    caption = poem + "\n\n#UrduPoetry #VigilAI"
    post_id = post_to_facebook(token, FB_PAGE_ID_URDU, caption, image_path)

    if post_id:
        # 5. Record in database
        add_post("urdu", poem, post_id)
        print(f"✅ [Engine 1] Successfully posted. Post ID: {post_id}")
    else:
        print("❌ [Engine 1] Failed to post to Facebook.")

    print(f"🔄 [Engine 1] Finished at {datetime.now()}")

# ----------------------------------------------------------------------
# Allow running this module directly for testing
# ----------------------------------------------------------------------
if __name__ == "__main__":
    run_engine_1()