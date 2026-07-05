# LLM Providers

Daily Stock Analysis supports multiple model providers through direct provider settings and LiteLLM-compatible routing.

## Configuration Paths

- Simple provider variables in `.env`, such as `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `DEEPSEEK_API_KEY`.
- Advanced routing with `LITELLM_CONFIG` and LiteLLM Router-compatible YAML.
- Web settings channel management for supported runtime configuration.

## Model Selection

Use `LITELLM_MODEL` for regular analysis and `AGENT_LITELLM_MODEL` when agent-specific routing is needed. Fallback models should be explicit and should not repeat the primary model.

## Safety Rules

- Do not commit API keys or provider-specific credentials.
- Keep provider prefixes and route aliases consistent with configured channels.
- Validate model availability before relying on a channel in scheduled jobs.
- Record diagnostics for authentication, quota, model-not-found, timeout, network, and format errors.

## Testing

Use the settings page connection test for basic calls and optional capability tests for JSON output, tool calling, streaming, and vision input.