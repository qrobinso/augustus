# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security vulnerability, please follow these steps:

1. **Do not** open a public GitHub issue
2. Report via GitHub Security Advisories: Go to the repository's Security tab and click "Report a vulnerability"
   - Or email security concerns to the repository maintainers
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond to security reports within 48 hours and work with you to address the issue before making it public.

## Security Best Practices

When using Augustus:

- **Change the default API_KEY**: Always change `API_KEY` from `change-me-in-production` to a secure random string
- **Keep API keys secure**: Never commit API keys to version control
- **Use environment variables**: Store sensitive configuration in `.env` files (which are gitignored)
- **Regular updates**: Keep dependencies up to date
- **Network security**: Use HTTPS in production and consider using a reverse proxy
- **Database security**: For production, consider using PostgreSQL with proper authentication instead of SQLite

## Known Security Considerations

- Augustus is designed for self-hosted use with a single user model
- API authentication is handled via the `API_KEY` environment variable
- All API keys are stored in environment variables, not in code
- Database files should not be committed to version control (already in `.gitignore`)

