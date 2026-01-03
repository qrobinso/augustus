"""Email service for sending notifications via Resend."""

import httpx
import re
import socket
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models.briefing import Briefing
from app.models.topic import Topic
from app.database import async_session_maker


def _is_docker_or_virtual_ip(ip: str) -> bool:
    """Check if an IP address belongs to a Docker or virtual network interface.
    
    Args:
        ip: IP address to check
        
    Returns:
        True if the IP is from a Docker/virtual network, False otherwise
    """
    if not ip:
        return True
    
    # Docker default bridge network uses 172.17.0.0/16
    # Docker custom networks use 172.18.0.0/16 - 172.31.0.0/16
    # Also filter out other common virtual/container network ranges
    parts = ip.split('.')
    if len(parts) != 4:
        return True
    
    try:
        first_octet = int(parts[0])
        second_octet = int(parts[1])
        
        # Docker bridge networks: 172.17.x.x - 172.31.x.x
        if first_octet == 172 and 17 <= second_octet <= 31:
            return True
        
        # Localhost
        if first_octet == 127:
            return True
            
        # Link-local addresses: 169.254.x.x
        if first_octet == 169 and second_octet == 254:
            return True
            
    except ValueError:
        return True
    
    return False


def _get_linux_network_ip() -> Optional[str]:
    """Get network IP on Linux by parsing ip addr output.
    
    Returns:
        Network IP address or None if not found
    """
    import subprocess
    try:
        # Run 'ip addr' to get all network interfaces
        result = subprocess.run(['ip', 'addr'], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return None
        
        # Parse output to find IPv4 addresses
        # Look for lines like: "inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0"
        import re
        
        # Find all inet addresses with their interface info
        # Format: inet <ip>/<mask> ... scope <scope> <interface>
        pattern = r'inet\s+(\d+\.\d+\.\d+\.\d+)/\d+.*?scope\s+(\w+)\s+(\w+)'
        matches = re.findall(pattern, result.stdout)
        
        # Filter and prioritize addresses
        # Priority: 192.168.x.x > 10.x.x.x > other private ranges
        priority_192 = []  # 192.168.x.x addresses (highest priority)
        priority_10 = []   # 10.x.x.x addresses
        priority_other = []  # Other valid addresses
        
        for ip, scope, interface in matches:
            # Skip loopback and docker/virtual interfaces
            if interface.startswith('lo'):
                continue
            if interface.startswith('docker') or interface.startswith('br-') or interface.startswith('veth'):
                continue
            if _is_docker_or_virtual_ip(ip):
                continue
            
            # Only consider 'global' scope addresses (routable)
            if scope != 'global':
                continue
            
            # Categorize by network range
            if ip.startswith('192.168.'):
                # Prioritize physical interface names within 192.168 range
                if interface.startswith(('eth', 'en', 'wlan', 'wl')):
                    priority_192.insert(0, ip)
                else:
                    priority_192.append(ip)
            elif ip.startswith('10.'):
                if interface.startswith(('eth', 'en', 'wlan', 'wl')):
                    priority_10.insert(0, ip)
                else:
                    priority_10.append(ip)
            else:
                if interface.startswith(('eth', 'en', 'wlan', 'wl')):
                    priority_other.insert(0, ip)
                else:
                    priority_other.append(ip)
        
        # Combine in priority order: 192.168.x.x first, then 10.x.x.x, then others
        candidates = priority_192 + priority_10 + priority_other
        
        if candidates:
            return candidates[0]
            
    except Exception:
        pass
    
    return None


def get_network_ip() -> Optional[str]:
    """Get the machine's network IP address for external access.
    
    Returns:
        Network IP address (e.g., '192.168.1.100') or None if not found
    """
    # First try the socket method - fastest and usually correct
    socket_ip = None
    try:
        # Connect to a remote address to determine the local network IP
        # This doesn't actually send data, just determines which interface would be used
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Connect to a public DNS server (doesn't actually connect)
            s.connect(('8.8.8.8', 80))
            socket_ip = s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        pass
    
    # Check if the socket IP is a Docker/virtual IP
    if socket_ip and not _is_docker_or_virtual_ip(socket_ip):
        return socket_ip
    
    # Socket returned a Docker IP or failed - try Linux-specific method
    import platform
    if platform.system() == 'Linux':
        linux_ip = _get_linux_network_ip()
        if linux_ip:
            print(f"[Email] Detected Docker/virtual IP ({socket_ip}), using real network IP: {linux_ip}")
            return linux_ip
    
    # Fallback: try to get IP from hostname
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        # Filter out localhost and Docker IPs
        if ip and not _is_docker_or_virtual_ip(ip):
            return ip
    except Exception:
        pass
    
    # Last resort: return socket_ip even if it's Docker (better than nothing)
    if socket_ip:
        print(f"[Email] WARNING: Could not detect non-Docker IP, using {socket_ip}")
        return socket_ip
    
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
                                            {f'<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td><a href="{briefing_url}" style="display: inline-block; padding: 12px 24px; background-color: #e85d04; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; font-family: Arial, Helvetica, sans-serif;">Play Now</a></td></tr></table>' if briefing_url else ''}
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
To manage your scheduled briefings, visit your dashboard.
    """
    
    # Resend API endpoint
    url = "https://api.resend.com/emails"
    
    # Get from email from settings, defaulting to onboarding@resend.dev if not configured
    settings = get_settings()
    from_email = settings.resend_from_email or "onboarding@resend.dev"
    
    # Sanitize subject line to avoid spam triggers
    # Remove any potentially problematic characters and ensure it's not too long
    safe_title = briefing_title[:50] + "..." if len(briefing_title) > 50 else briefing_title
    subject = f"Augustus Today: {safe_title}"
    
    # Build email payload for Resend API with deliverability best practices
    payload = {
        "from": f"Augustus Briefings <{from_email}>",
        "to": recipients,
        "subject": subject,
        "html": html_content,
        "text": text_content,
        "reply_to": from_email,  # Set reply-to for better deliverability
        "headers": {
            "List-Unsubscribe": f"<{frontend_url}/dashboard>",  # RFC 2369 compliance
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",  # One-click unsubscribe support
            "X-Mailer": "Augustus Briefing System",  # Identify the sending system
            "Precedence": "bulk",  # Indicate this is automated/bulk email
        },
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
    db: Optional[AsyncSession] = None,
) -> bool:
    """Send a single email notification with multiple briefings.
    
    Args:
        briefings: List of Briefing objects to include in the email
        recipients: List of email addresses to send to
        api_key: Resend API key (uses global setting if not provided)
        db: Optional database session for querying topics
    
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
    
    # Get topics for all briefings if database session is available
    topics_map = {}  # Map topic_id -> topic_name
    if db:
        try:
            # Collect all topic IDs from all briefings
            all_topic_ids = set()
            for briefing in briefings:
                if hasattr(briefing, 'extra_data') and briefing.extra_data:
                    topic_ids = briefing.extra_data.get('topic_ids', []) or []
                    all_topic_ids.update(topic_ids)
            
            # Query all topics at once
            if all_topic_ids:
                result = await db.execute(
                    select(Topic).where(Topic.id.in_(all_topic_ids))
                )
                topics = result.scalars().all()
                topics_map = {topic.id: topic.name for topic in topics}
        except Exception as e:
            print(f"[Email] Error fetching topics: {e}")
    
    briefing_sections = []
    for briefing in briefings:
        # Get summary from extra_data (story_analysis) or fall back to empty
        summary = ""
        if hasattr(briefing, 'extra_data') and briefing.extra_data:
            summary = briefing.extra_data.get('story_analysis', '') or ''
        if summary:
            summary = summary[:300] + "..." if len(summary) > 300 else summary
        
        # Get topic names for this briefing
        topic_names = []
        if hasattr(briefing, 'extra_data') and briefing.extra_data:
            topic_ids = briefing.extra_data.get('topic_ids', []) or []
            topic_names = [topics_map.get(tid) for tid in topic_ids if topics_map.get(tid)]
        
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
            'topics': topic_names,
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
                                                <h3 style="margin: 0 0 8px 0; color: #333333; font-size: 18px; font-weight: 600; font-family: Arial, Helvetica, sans-serif;">{section['title']}</h3>
                                                {f'<p style="margin: 0 0 16px 0; color: #999999; font-size: 13px; font-family: Arial, Helvetica, sans-serif;">{", ".join(section["topics"])}</p>' if section.get('topics') else ''}
                                                {f'<p style="margin: 0 0 16px 0; color: #666666; font-size: 14px; line-height: 1.6; font-family: Arial, Helvetica, sans-serif;">{section["summary"]}</p>' if section['summary'] else ''}
                                                <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                                    <tr>
                                                        <td>
                                                            <a href="{section['briefing_url']}" style="display: inline-block; padding: 10px 20px; background-color: #e85d04; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 13px; font-family: Arial, Helvetica, sans-serif;">Play Now</a>
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
{f"   Topics: {', '.join(section['topics'])}" if section.get('topics') else ''}
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
To manage your scheduled briefings, visit your dashboard.
    """
    
    # Resend API endpoint
    url = "https://api.resend.com/emails"
    
    # Get from email from settings, defaulting to onboarding@resend.dev if not configured
    settings = get_settings()
    from_email = settings.resend_from_email or "onboarding@resend.dev"
    
    # Build email payload for Resend API with deliverability best practices
    subject = f"Augustus Today ({len(briefings)} briefing{'' if len(briefings) == 1 else 's'})"
    
    payload = {
        "from": f"Augustus Briefings <{from_email}>",
        "to": recipients,
        "subject": subject,
        "html": html_content,
        "text": text_content,
        "reply_to": from_email,  # Set reply-to for better deliverability
        "headers": {
            "List-Unsubscribe": f"<{frontend_url}/dashboard>",  # RFC 2369 compliance
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",  # One-click unsubscribe support
            "X-Mailer": "Augustus Briefing System",  # Identify the sending system
            "Precedence": "bulk",  # Indicate this is automated/bulk email
        },
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
