#!/bin/bash
# Push to GitHub Script
# This script commits and pushes changes to GitHub

set -e  # Exit immediately if a command exits with a non-zero status

# Colors for terminal output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting GitHub push script...${NC}"

# If no commit message is provided, use a default one
COMMIT_MSG=${1:-"Update Twitter media extraction with improved API support"}

# Git operations
echo -e "${YELLOW}Staging changes...${NC}"
git add .

echo -e "${YELLOW}Committing changes with message: '${COMMIT_MSG}'${NC}"
git commit -m "$COMMIT_MSG"

echo -e "${YELLOW}Pushing to GitHub...${NC}"
git push

echo -e "${GREEN}Successfully pushed changes to GitHub!${NC}" 