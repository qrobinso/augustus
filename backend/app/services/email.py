"""Email service for sending notifications via Resend."""

import httpx
import re
import socket
from datetime import datetime
from typing import Optional, List
from app.config import get_settings
from app.models.briefing import Briefing


def get_network_ip() -> Optional[str]:
    """Get the machine's network IP address for external access.
    
    Returns:
        Network IP address (e.g., '192.168.1.100') or None if not found
    """
    try:
        # Connect to a remote address to determine the local network IP
        # This doesn't actually send data, just determines which interface would be used
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Connect to a public DNS server (doesn't actually connect)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            return ip
        finally:
            s.close()
    except Exception:
        # Fallback: try to get IP from hostname
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            # Filter out localhost
            if ip and ip != '127.0.0.1':
                return ip
        except Exception:
            pass
    return None


def get_external_frontend_url(frontend_url: str) -> str:
    """Convert localhost frontend URL to network-accessible URL.
    
    Args:
        frontend_url: The configured frontend URL (may be localhost)
    
    Returns:
        Network-accessible URL (replaces localhost with network IP)
    """
    # If already using an external URL (not localhost), return as-is
    if 'localhost' not in frontend_url and '127.0.0.1' not in frontend_url:
        return frontend_url
    
    # Extract port from URL using more robust method
    port_match = re.search(r':(\d+)(?:/|$)', frontend_url)
    port = port_match.group(1) if port_match else '3000'
    
    # Determine protocol
    protocol = 'https://' if frontend_url.startswith('https://') else 'http://'
    
    # Get network IP
    network_ip = get_network_ip()
    if network_ip:
        # Replace localhost/127.0.0.1 with network IP
        return f"{protocol}{network_ip}:{port}"
    
    # If we can't detect network IP, return original (will log warning)
    return frontend_url


async def send_briefing_email(
    briefing_title: str,
    briefing_summary: Optional[str],
    audio_url: Optional[str],
    recipients: List[str],
    briefing_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> bool:
    """Send briefing notification email via Resend.
    
    Args:
        briefing_title: Title of the briefing
        briefing_summary: Summary of the briefing content (optional)
        audio_url: URL to the audio file (optional)
        recipients: List of email addresses to send to
        briefing_id: Briefing ID for constructing detail page link (optional)
        api_key: Resend API key (uses global setting if not provided)
    
    Returns:
        True if email was sent successfully, False otherwise
    """
    if not recipients:
        print("[Email] No recipients provided, skipping email")
        return False
    
    # Get API key
    if not api_key:
        settings = get_settings()
        api_key = getattr(settings, 'resend_api_key', None)
    
    if not api_key:
        print("[Email] No Resend API key configured, skipping email")
        return False
    
    # Get frontend URL for constructing briefing detail page links
    settings = get_settings()
    frontend_url = getattr(settings, 'frontend_url', 'http://localhost:3000')
    
    # Convert localhost to network-accessible URL for email links
    external_url = get_external_frontend_url(frontend_url)
    if external_url != frontend_url:
        print(f"[Email] Using network-accessible URL: {external_url} (instead of {frontend_url})")
    elif 'localhost' in frontend_url or '127.0.0.1' in frontend_url:
        print(f"[Email] WARNING: Frontend URL is localhost ({frontend_url}). Email links may not work on external devices.")
        print(f"[Email] WARNING: Set FRONTEND_URL to your network IP or domain (e.g., http://192.168.1.100:3000)")
    
    frontend_url = external_url
    
    # Prepare email content - use summary directly (already clean text)
    summary_text = ""
    if briefing_summary:
        summary_text = briefing_summary[:500] + "..." if len(briefing_summary) > 500 else briefing_summary
    
    # Construct briefing detail page URL with auto-play if briefing_id is provided
    briefing_url = f"{frontend_url}/briefing/{briefing_id}?autoplay=true" if briefing_id else audio_url
    
    # Build email HTML optimized for Gmail compatibility
    # Use table-based layout with inline styles (Gmail strips style tags)
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: Arial, Helvetica, sans-serif;">
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f5f5f5;">
            <tr>
                <td align="center" style="padding: 20px 0;">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background-color: #e85d04; padding: 32px 24px; text-align: center;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600; font-family: Arial, Helvetica, sans-serif;">Augustus Today</h1>
                            </td>
                        </tr>
                        <!-- Content -->
                        <tr>
                            <td style="padding: 24px; background-color: #ffffff;">
                                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                    <tr>
                                        <td style="background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 20px;">
                                            <h2 style="margin: 0 0 16px 0; color: #333333; font-size: 20px; font-weight: 600; font-family: Arial, Helvetica, sans-serif;">{briefing_title}</h2>
                                            {f'<p style="margin: 0 0 20px 0; color: #666666; font-size: 14px; line-height: 1.6; font-family: Arial, Helvetica, sans-serif;">{summary_text}</p>' if summary_text else ''}
                                            {f'<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td><a href="{briefing_url}" style="display: inline-block; padding: 12px 24px; background-color: #e85d04; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; font-family: Arial, Helvetica, sans-serif;">▶ Play Now</a></td></tr></table>' if briefing_url else ''}
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 24px; background-color: #f8f9fa; border-top: 1px solid #e0e0e0;">
                                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                    <tr>
                                        <td style="text-align: center; padding-bottom: 12px;">
                                            <p style="margin: 0; color: #666666; font-size: 12px; font-family: Arial, Helvetica, sans-serif;">
                                                You're receiving this email because you've set up scheduled briefings.
                                            </p>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="text-align: center; padding-bottom: 8px;">
                                            <a href="{frontend_url}/dashboard" style="color: #e85d04; text-decoration: none; font-size: 12px; font-family: Arial, Helvetica, sans-serif;">Manage Briefings</a>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="text-align: center; padding-top: 12px; border-top: 1px solid #e0e0e0;">
                                            <p style="margin: 0; color: #999999; font-size: 11px; font-family: Arial, Helvetica, sans-serif; line-height: 1.5;">
                                                © {datetime.now().year} Augustus. All rights reserved.<br>
                                                This is an automated briefing notification.
                                            </p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    # Plain text version
    text_content = f"""
Augustus Today

{briefing_title}

{summary_text if summary_text else ''}

{f'Play Now: {briefing_url}' if briefing_url else ''}

---
You're receiving this email because you've set up scheduled briefings.
Manage Briefings: {frontend_url}/dashboard

© {datetime.now().year} Augustus. All rights reserved.
This is an automated briefing notification.
    """
    
    # Resend API endpoint
    url = "https://api.resend.com/emails"
    
    # Use onboarding@resend.dev as the from email (for testing without verified sender domain)
    # See: https://docs.novu.co/platform/integrations/email/resend#getting-started
    from_email = "onboarding@resend.dev"
    
    # Build email payload for Resend API
    payload = {
        "from": f"Augustus Briefings <{from_email}>",
        "to": recipients,
        "subject": f"Augustus Today: {briefing_title}",
        "html": html_content,
        "text": text_content,
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            print(f"[Email] Successfully sent briefing email to {len(recipients)} recipients")
            return True
    except httpx.HTTPStatusError as e:
        print(f"[Email] Resend API error: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        print(f"[Email] Failed to send email: {e}")
        return False


async def send_batched_briefings_email(
    briefings: List[Briefing],
    recipients: List[str],
    api_key: Optional[str] = None,
) -> bool:
    """Send a single email notification with multiple briefings.
    
    Args:
        briefings: List of Briefing objects to include in the email
        recipients: List of email addresses to send to
        api_key: Resend API key (uses global setting if not provided)
    
    Returns:
        True if email was sent successfully, False otherwise
    """
    if not recipients:
        print("[Email] No recipients provided, skipping email")
        return False
    
    if not briefings:
        print("[Email] No briefings provided, skipping email")
        return False
    
    # Get API key
    if not api_key:
        settings = get_settings()
        api_key = getattr(settings, 'resend_api_key', None)
    
    if not api_key:
        print("[Email] No Resend API key configured, skipping email")
        return False
    
    # Prepare content for all briefings
    import re
    
    # Get frontend URL for constructing briefing detail page links
    settings = get_settings()
    frontend_url = getattr(settings, 'frontend_url', 'http://localhost:3000')
    
    # Convert localhost to network-accessible URL for email links
    external_url = get_external_frontend_url(frontend_url)
    if external_url != frontend_url:
        print(f"[Email] Using network-accessible URL: {external_url} (instead of {frontend_url})")
    elif 'localhost' in frontend_url or '127.0.0.1' in frontend_url:
        print(f"[Email] WARNING: Frontend URL is localhost ({frontend_url}). Email links may not work on external devices.")
        print(f"[Email] WARNING: Set FRONTEND_URL to your network IP or domain (e.g., http://192.168.1.100:3000)")
    
    frontend_url = external_url
    
    briefing_sections = []
    for briefing in briefings:
        # Get summary from extra_data (story_analysis) or fall back to empty
        summary = ""
        if hasattr(briefing, 'extra_data') and briefing.extra_data:
            summary = briefing.extra_data.get('story_analysis', '') or ''
        if summary:
            summary = summary[:300] + "..." if len(summary) > 300 else summary
        
        # Construct briefing detail page URL with auto-play
        briefing_url = f"{frontend_url}/briefing/{briefing.id}?autoplay=true"
        
        # Format duration
        duration_str = ""
        if briefing.duration_seconds:
            mins = int(briefing.duration_seconds // 60)
            secs = int(briefing.duration_seconds % 60)
            duration_str = f"{mins}:{secs:02d}"
        
        briefing_sections.append({
            'title': briefing.title,
            'summary': summary,
            'briefing_url': briefing_url,
            'duration': duration_str,
        })
    
    # Build email HTML optimized for Gmail compatibility
    # Use table-based layout with inline styles (Gmail strips style tags)
    briefing_items_html = ""
    for i, section in enumerate(briefing_sections, 1):
        briefing_items_html += f"""
                            <tr>
                                <td style="padding-bottom: 16px;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 20px;">
                                        <tr>
                                            <td>
                                                <h3 style="margin: 0 0 12px 0; color: #333333; font-size: 18px; font-weight: 600; font-family: Arial, Helvetica, sans-serif;">{section['title']}</h3>
                                                {f'<p style="margin: 0 0 16px 0; color: #666666; font-size: 14px; line-height: 1.6; font-family: Arial, Helvetica, sans-serif;">{section["summary"]}</p>' if section['summary'] else ''}
                                                <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                                    <tr>
                                                        <td>
                                                            <a href="{section['briefing_url']}" style="display: inline-block; padding: 10px 20px; background-color: #e85d04; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 13px; font-family: Arial, Helvetica, sans-serif;">▶ Play Now</a>
                                                            {f'<span style="color: #999999; font-size: 13px; font-family: monospace; margin-left: 12px;">{section["duration"]}</span>' if section['duration'] else ''}
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: Arial, Helvetica, sans-serif;">
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f5f5f5;">
            <tr>
                <td align="center" style="padding: 20px 0;">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background-color: #e85d04; padding: 32px 24px; text-align: center;">
                                <h1 style="margin: 0 0 8px 0; color: #ffffff; font-size: 24px; font-weight: 600; font-family: Arial, Helvetica, sans-serif;">Augustus Today</h1>
                                <p style="margin: 0; color: #ffffff; font-size: 14px; font-family: Arial, Helvetica, sans-serif;">You have {len(briefings)} new briefing{'' if len(briefings) == 1 else 's'}</p>
                            </td>
                        </tr>
                        <!-- Content -->
                        <tr>
                            <td style="padding: 24px; background-color: #ffffff;">
                                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                    {briefing_items_html}
                                </table>
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 24px; background-color: #f8f9fa; border-top: 1px solid #e0e0e0;">
                                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                    <tr>
                                        <td style="text-align: center; padding-bottom: 12px;">
                                            <p style="margin: 0; color: #666666; font-size: 12px; font-family: Arial, Helvetica, sans-serif;">
                                                You're receiving this email because you've set up scheduled briefings.
                                            </p>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="text-align: center; padding-bottom: 8px;">
                                            <a href="{frontend_url}/dashboard" style="color: #e85d04; text-decoration: none; font-size: 12px; font-family: Arial, Helvetica, sans-serif;">Manage Briefings</a>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="text-align: center; padding-top: 12px; border-top: 1px solid #e0e0e0;">
                                            <p style="margin: 0; color: #999999; font-size: 11px; font-family: Arial, Helvetica, sans-serif; line-height: 1.5;">
                                                © {datetime.now().year} Augustus. All rights reserved.<br>
                                                This is an automated briefing notification.
                                            </p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    # Plain text version
    briefing_items_text = ""
    for i, section in enumerate(briefing_sections, 1):
        briefing_items_text += f"""
{i}. {section['title']}
{f"   {section['summary']}" if section['summary'] else ''}
{f"   Duration: {section['duration']}" if section['duration'] else ''}
   Play Now: {section['briefing_url']}

"""
    
    text_content = f"""Augustus Today

You have {len(briefings)} new briefing{'' if len(briefings) == 1 else 's'}:

{briefing_items_text}
---
You're receiving this email because you've set up scheduled briefings.
Manage Briefings: {frontend_url}/dashboard

© {datetime.now().year} Augustus. All rights reserved.
This is an automated briefing notification.
    """
    
    # Resend API endpoint
    url = "https://api.resend.com/emails"
    
    # Use onboarding@resend.dev as the from email (for testing without verified sender domain)
    # See: https://docs.novu.co/platform/integrations/email/resend#getting-started
    from_email = "onboarding@resend.dev"
    
    # Build email payload for Resend API
    subject = f"Augustus Today ({len(briefings)} briefing{'' if len(briefings) == 1 else 's'})"
    
    payload = {
        "from": f"Augustus Briefings <{from_email}>",
        "to": recipients,
        "subject": subject,
        "html": html_content,
        "text": text_content,
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            print(f"[Email] Successfully sent batched email with {len(briefings)} briefings to {len(recipients)} recipients")
            return True
    except httpx.HTTPStatusError as e:
        print(f"[Email] Resend API error: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        print(f"[Email] Failed to send batched email: {e}")
        return False
