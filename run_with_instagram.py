#!/usr/bin/env python3
import os
import subprocess
import sys

def main():
    # Set Instagram credentials
    os.environ['INSTAGRAM_CLIENT_ID'] = "your_instagram_app_id"
    os.environ['INSTAGRAM_CLIENT_SECRET'] = "your_instagram_app_secret"

    # Print masked credentials for verification
    client_id = os.environ['INSTAGRAM_CLIENT_ID']
    client_secret = os.environ['INSTAGRAM_CLIENT_SECRET']

    masked_id = client_id[:4] + '*' * (len(client_id) - 8) + client_id[-4:] if len(client_id) > 8 else '****'
    masked_secret = client_secret[:4] + '*' * (len(client_secret) - 8) + client_secret[-4:] if len(client_secret) > 8 else '****'

ai_video_bp = Blue# # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # print('ai_video', __name__, url_prefix='/ai-video')

    # Run the app
    try:
        subprocess.run([sys.executable, "app.py"], check=True)
    except KeyboardInterrupt:
ai_video_bp = Blue# # # # print('ai_video', __name__, url_prefix='/ai-video')
    except subprocess.CalledProcessError as e:
ai_video_bp = Blue# # # # print('ai_video', __name__, url_prefix='/ai-video')

if __name__ == "__main__":
