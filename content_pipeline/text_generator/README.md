# AI Model Integration for Content Repurposing Pipeline

This module provides integration with various AI models for text generation in the Content Repurposing Pipeline, including:

- OpenAI (GPT-3.5/4)
- DeepSeek
- Google Gemini

## Installation

To use these AI models, you need to install the required packages:

```bash
# For OpenAI integration
pip install openai>=0.28.0,<1.0.0 tiktoken>=0.4.0,<0.6.0

# For DeepSeek integration
pip install git+https://github.com/rabilrbl/deepseek-api.git

# For Google Gemini integration
pip install google-generativeai>=0.3.0
```

You can also install all dependencies at once using the requirements.txt file:

```bash
pip install -r requirements.txt
```

## Setup

To use these AI models, you need to set up API keys in your environment variables:

```bash
# OpenAI
export OPENAI_API_KEY=your_openai_api_key

# DeepSeek
export DEEPSEEK_API_KEY=your_deepseek_api_key
export DEEPSEEK_EMAIL=your_deepseek_email@example.com
export DEEPSEEK_PASSWORD=your_deepseek_password

# Google Gemini
export GOOGLE_API_KEY=your_google_api_key
```

You can also set these in your `.env` file.

## Configuration

You can configure which AI provider to use by setting the `AI_PROVIDER` environment variable:

```bash
export AI_PROVIDER=openai  # Options: openai, deepseek, gemini
```

To use the unified text generator (recommended), set:

```bash
export USE_UNIFIED_TEXT_GENERATOR=true
```

## Usage

The text generator can be used to generate captions and hashtags for video clips:

```python
from content_pipeline.text_generator import process_clip

# Process a clip with the default AI provider
result = process_clip(
    clip_path="path/to/video.mp4",
    num_caption_variations=3,
    num_hashtags=10
)

# Process a clip with a specific AI provider
result = process_clip(
    clip_path="path/to/video.mp4",
    num_caption_variations=3,
    num_hashtags=10,
    ai_provider="gemini"  # Use Google Gemini
)

# Access the generated captions and hashtags
captions = result["captions"]
hashtags = result["hashtags"]
```

## Web Interface

The web interface allows users to select which AI model to use for text generation. The available models are determined by the API keys set in the environment variables and the installed packages.

## Fallback Mechanism

If the specified AI provider is not available (e.g., API key not set or package not installed), the system will attempt to fall back to other available providers in this order:

1. OpenAI
2. Google Gemini
3. DeepSeek

If no providers are available, the system will use fallback values for captions and hashtags.

## Troubleshooting

If you encounter errors related to missing modules, make sure you have installed the required packages:

- For OpenAI: `pip install openai tiktoken`
- For DeepSeek: `pip install deepseek-chat`
- For Google Gemini: `pip install google-generativeai`

If you encounter API key errors, make sure you have set the appropriate environment variables or included them in your `.env` file.