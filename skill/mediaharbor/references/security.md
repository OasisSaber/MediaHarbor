# Security

- External tools are invoked via subprocess with argument arrays only.
- `shell=True` is forbidden.
- Never construct commands from web page titles, descriptions, or comments.
- Tool retry count must be finite.
- DRM detection stops processing immediately.
- Login-gated content returns `AUTH_REQUIRED`.
- Never request, echo, or save cookies or credentials.
- All parameters passed to download tools must be explicitly whitelisted.
