# Security Policy

## Protecting Your Credentials

This project requires a Vimeo Personal Access Token to function. It's critical that you keep this token secure and never commit it to version control.

## Best Practices

### 1. Use Environment Variables
Store your token in environment variables, not in code:

```bash
# Linux/Mac
export VIMEO_TOKEN="your_actual_token_here"

# Windows PowerShell
$env:VIMEO_TOKEN = "your_actual_token_here"
```

### 2. Use .env Files (Recommended)
The safest way to manage credentials locally:

1. Copy `.env.example` to `.env`
2. Add your actual token to `.env`
3. The `.env` file is already in `.gitignore` and won't be committed

```bash
cp .env.example .env
# Edit .env and replace the placeholder with your actual token
```

### 3. Never Commit Credentials
The repository includes a `.gitignore` file that prevents:
- `.env` files
- Files containing tokens/secrets
- Downloaded videos
- Metadata files
- Log files

### 4. Revoke Compromised Tokens
If you accidentally expose a token:

1. Immediately go to [https://developer.vimeo.com/apps](https://developer.vimeo.com/apps)
2. Revoke the compromised token
3. Generate a new token
4. Update your local `.env` file

### 5. Minimum Required Scopes
Only grant the minimum required scopes for your token:
- `public` - Access public videos
- `private` - Access private videos in your account
- `video_files` - Download video files

Never grant additional scopes unless absolutely necessary.

## What Not to Do

❌ **DON'T** hardcode tokens in Python files  
❌ **DON'T** commit `.env` files to Git  
❌ **DON'T** share tokens via email, chat, or screenshots  
❌ **DON'T** use the same token across multiple users  
❌ **DON'T** commit video files or metadata to the repository  

## Reporting Security Issues

If you discover a security vulnerability in this project, please email the maintainer directly rather than opening a public issue.

## Secure Development Checklist

- [ ] Token stored in `.env` or environment variable
- [ ] `.env` file is in `.gitignore`
- [ ] Token has minimum required scopes only
- [ ] Never passing token in command line (visible in process list)
- [ ] Not committing downloaded videos or metadata
- [ ] Regularly rotating tokens
- [ ] Using virtual environment for dependencies

## Additional Resources

- [Vimeo API Documentation](https://developer.vimeo.com/api/reference)
- [Vimeo App Management](https://developer.vimeo.com/apps)
- [OWASP Security Practices](https://owasp.org/www-project-top-ten/)
