#!/bin/bash
# Test and Push Script
# This script runs tests and then pushes to GitHub if tests pass

set -e  # Exit immediately if a command exits with a non-zero status

# Colors for terminal output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting test and push script...${NC}"

# Get the project root directory (where this script is run from)
PROJECT_ROOT=$(pwd)

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Check for pytest
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}pytest could not be found. Please install it with: pip install pytest${NC}"
    exit 1
fi

# Run tests with proper Python path
echo -e "${YELLOW}Running tests...${NC}"
if PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH" pytest tests/ -v; then
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo -e "${RED}Tests failed. Fix the issues before pushing to GitHub.${NC}"
    exit 1
fi

# If no commit message is provided, use a default one
COMMIT_MSG=${1:-"Update Twitter media extraction with improved API support"}

# Git operations
echo -e "${YELLOW}Staging changes...${NC}"
git add .

echo -e "${YELLOW}Committing changes with message: '${COMMIT_MSG}'${NC}"
git commit -m "$COMMIT_MSG"

echo -e "${YELLOW}Pushing to GitHub...${NC}"
git push

echo -e "${GREEN}Successfully tested and pushed changes to GitHub!${NC}"

# Deactivate virtual environment if it was activated
if [ -d "venv" ]; then
    deactivate 2>/dev/null || true
fi 