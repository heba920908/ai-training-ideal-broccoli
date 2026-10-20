"""
Configuration constants for AI service integrations.

This module centralizes all API endpoints, API keys, models, and default configuration
values used across different AI service providers (OpenAI, Anthropic, Gemini).

All API keys are loaded from environment variables for security.
"""

import os

# Default system prompt used across all AI services
DEFAULT_SYSTEM_PROMPT = "You are an assistant who answers concisely and informatively."

# OpenAI / EPAM DIAL API configuration (loaded from OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_API_KEY)
OPENAI_HOST = os.getenv("OPENAI_BASE_URL", "https://ai-proxy.lab.epam.com").rstrip("/")
OPENAI_CHAT_COMPLETIONS_ENDPOINT = f"{OPENAI_HOST}/chat/completions"
OPENAI_RESPONSES_ENDPOINT = f"{OPENAI_HOST}/responses"
OPENAI_EMBEDDINGS_ENDPOINT = f"{OPENAI_HOST}/embeddings"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")
OPENAI_TERRA_MODEL = OPENAI_MODEL
OPENAI_LUNA_MODEL = OPENAI_MODEL
OPENAI_EMBEDDINGS_MODEL = OPENAI_MODEL

# Anthropic API configuration
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Claude Sonnet 5 rejects non-default `temperature`/`top_p`/`top_k` and `budget_tokens` thinking, and runs adaptive
# thinking by default (responses can start with a `thinking` block). Claude Haiku 4.5 still supports them
ANTHROPIC_SONNET_MODEL = "claude-sonnet-5"
ANTHROPIC_HAIKU_MODEL = "claude-haiku-4-5"

# Google Gemini API configuration
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_FLASH_MODEL = "gemini-3-flash-preview"

# User Service API configuration
USER_SERVICE_ENDPOINT = "http://localhost:8041"