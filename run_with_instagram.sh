#!/bin/bash

# Set Instagram credentials
export INSTAGRAM_CLIENT_ID="your_instagram_app_id"
export INSTAGRAM_CLIENT_SECRET="your_instagram_app_secret"

# Print masked credentials for verification
echo "Instagram Client ID: ${INSTAGRAM_CLIENT_ID:0:4}****${INSTAGRAM_CLIENT_ID: -4}"
echo "Instagram Client Secret: ${INSTAGRAM_CLIENT_SECRET:0:4}****${INSTAGRAM_CLIENT_SECRET: -4}"

# Run the app
python app.py 