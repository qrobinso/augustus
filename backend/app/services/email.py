"""Email service for sending notifications via Resend."""

import httpx
from typing import Optional, List
from app.config import get_settings
from app.models.briefing import Briefing


async def send_briefing_email(
    briefing_title: str,
    briefing_transcript: Optional[str],
    audio_url: Optional[str],
    recipients: List[str],
    api_key: Optional[str] = None,
) -> bool:
    """Send briefing notification email via Resend.
    
    Args:
        briefing_title: Title of the briefing
        briefing_transcript: Transcript text (optional)
        audio_url: URL to the audio file (optional)
        recipients: List of email addresses to send to
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
    
    # Prepare email content
    transcript_preview = ""
    if briefing_transcript:
        # Remove HOST1:/HOST2: prefixes and truncate
        import re
        cleaned = re.sub(r'HOST[12]:\s*', '', briefing_transcript, flags=re.IGNORECASE).strip()
        transcript_preview = cleaned[:500] + "..." if len(cleaned) > 500 else cleaned
    
    # Build email HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9fafb; }}
            .button {{ display: inline-block; padding: 12px 24px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px; margin-top: 10px; }}
            .transcript {{ background-color: white; padding: 15px; border-radius: 5px; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Daily Briefing Ready</h1>
            </div>
            <div class="content">
                <h2>{briefing_title}</h2>
                {f'<div class="transcript"><p><strong>Preview:</strong></p><p>{transcript_preview}</p></div>' if transcript_preview else ''}
                {f'<a href="{audio_url}" class="button">Listen to Briefing</a>' if audio_url else ''}
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version
    text_content = f"""
Daily Briefing Ready

{briefing_title}

{transcript_preview if transcript_preview else ''}

{f'Listen to briefing: {audio_url}' if audio_url else ''}
    """
    
    # Resend API endpoint
    url = "https://api.resend.com/emails"
    
    # Get from email (use first recipient - Resend requires verified sender domain)
    from_email = recipients[0]
    # Note: Resend requires the "from" email domain to be verified in your Resend account
    # You can add a RESEND_FROM_EMAIL setting if needed
    
    # Build email payload for Resend API
    payload = {
        "from": f"Augustus Briefings <{from_email}>",
        "to": recipients,
        "subject": f"Daily Briefing: {briefing_title}",
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
    
    briefing_sections = []
    for briefing in briefings:
        transcript_preview = ""
        if briefing.transcript:
            cleaned = re.sub(r'HOST[12]:\s*', '', briefing.transcript, flags=re.IGNORECASE).strip()
            transcript_preview = cleaned[:300] + "..." if len(cleaned) > 300 else cleaned
        
        audio_url = briefing.audio_url if briefing.audio_url else None
        
        briefing_sections.append({
            'title': briefing.title,
            'transcript_preview': transcript_preview,
            'audio_url': audio_url,
            'duration': briefing.duration_seconds,
        })
    
    # Build email HTML
    briefing_items_html = ""
    for i, section in enumerate(briefing_sections, 1):
        briefing_items_html += f"""
        <div class="briefing-item" style="background-color: white; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
            <h3 style="margin-top: 0; color: #4F46E5;">{section['title']}</h3>
            {f'<p style="color: #666; font-size: 14px;">{section["transcript_preview"]}</p>' if section['transcript_preview'] else ''}
            {f'<a href="{section["audio_url"]}" class="button" style="display: inline-block; padding: 8px 16px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px; margin-top: 10px;">Listen to Briefing</a>' if section['audio_url'] else ''}
        </div>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9fafb; }}
            .button {{ display: inline-block; padding: 12px 24px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Daily Briefings Ready</h1>
                <p style="margin: 0; font-size: 14px;">You have {len(briefings)} new briefing{'' if len(briefings) == 1 else 's'}</p>
            </div>
            <div class="content">
                {briefing_items_html}
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version
    briefing_items_text = ""
    for i, section in enumerate(briefing_sections, 1):
        briefing_items_text += f"""
{i}. {section['title']}
{f"   Preview: {section['transcript_preview']}" if section['transcript_preview'] else ''}
{f"   Listen: {section['audio_url']}" if section['audio_url'] else ''}

"""
    
    text_content = f"""Daily Briefings Ready

You have {len(briefings)} new briefing{'' if len(briefings) == 1 else 's'}:

{briefing_items_text}
    """
    
    # Resend API endpoint
    url = "https://api.resend.com/emails"
    
    # Get from email (use first recipient - Resend requires verified sender domain)
    from_email = recipients[0]
    
    # Build email payload for Resend API
    subject = f"Daily Briefings Ready ({len(briefings)} briefing{'' if len(briefings) == 1 else 's'})"
    
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
