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
    briefing_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> bool:
    """Send briefing notification email via Resend.
    
    Args:
        briefing_title: Title of the briefing
        briefing_transcript: Transcript text (optional)
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
    
    # Prepare email content
    transcript_preview = ""
    if briefing_transcript:
        # Remove HOST1:/HOST2: prefixes and truncate
        import re
        cleaned = re.sub(r'HOST[12]:\s*', '', briefing_transcript, flags=re.IGNORECASE).strip()
        transcript_preview = cleaned[:500] + "..." if len(cleaned) > 500 else cleaned
    
    # Construct briefing detail page URL with auto-play if briefing_id is provided
    briefing_url = f"{frontend_url}/briefing/{briefing_id}?autoplay=true" if briefing_id else audio_url
    
    # Build email HTML with app's dark theme styling
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'DM Sans', system-ui, sans-serif; 
                line-height: 1.6; 
                color: #eeeef0; 
                background-color: #1a1a1e;
                margin: 0;
                padding: 0;
            }}
            .container {{ 
                max-width: 600px; 
                margin: 0 auto; 
                padding: 0;
                background-color: #1a1a1e;
            }}
            .header {{ 
                background: linear-gradient(135deg, rgba(232, 93, 4, 0.1) 0%, rgba(232, 93, 4, 0.05) 100%);
                border-bottom: 1px solid rgba(66, 66, 75, 0.5);
                padding: 32px 24px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0 0 8px 0;
                color: #ffffff;
                font-size: 24px;
                font-weight: 600;
            }}
            .content {{ 
                padding: 24px;
                background-color: #1a1a1e;
            }}
            .briefing-item {{
                background-color: rgba(58, 58, 65, 0.5);
                border: 1px solid rgba(66, 66, 75, 0.5);
                padding: 20px;
                border-radius: 12px;
                backdrop-filter: blur(8px);
            }}
            .briefing-item h2 {{
                margin-top: 0;
                margin-bottom: 12px;
                color: #ffffff;
                font-size: 18px;
                font-weight: 600;
            }}
            .transcript {{
                background-color: rgba(58, 58, 65, 0.3);
                padding: 15px;
                border-radius: 8px;
                margin-top: 15px;
            }}
            .transcript p {{
                color: #b8b8c1;
                font-size: 14px;
                line-height: 1.6;
                margin: 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Daily Briefing Ready</h1>
            </div>
            <div class="content">
                <div class="briefing-item">
                    <h2>{briefing_title}</h2>
                    {f'<div class="transcript"><p><strong>Preview:</strong></p><p>{transcript_preview}</p></div>' if transcript_preview else ''}
                    {f'<div style="display: flex; align-items: center; gap: 12px; margin-top: 16px;"><a href="{briefing_url}" style="display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; background-color: #e85d04; color: white; text-decoration: none; border-radius: 50%; transition: all 0.2s; box-shadow: 0 0 20px -5px rgba(232, 93, 4, 0.4);"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left: 2px;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></a></div>' if briefing_url else ''}
                </div>
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

{f'Listen to briefing: {briefing_url}' if briefing_url else ''}
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
    
    # Get frontend URL for constructing briefing detail page links
    settings = get_settings()
    frontend_url = getattr(settings, 'frontend_url', 'http://localhost:3000')
    
    briefing_sections = []
    for briefing in briefings:
        transcript_preview = ""
        if briefing.transcript:
            cleaned = re.sub(r'HOST[12]:\s*', '', briefing.transcript, flags=re.IGNORECASE).strip()
            transcript_preview = cleaned[:300] + "..." if len(cleaned) > 300 else cleaned
        
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
            'transcript_preview': transcript_preview,
            'briefing_url': briefing_url,
            'duration': duration_str,
        })
    
    # Build email HTML with app's dark theme styling
    briefing_items_html = ""
    for i, section in enumerate(briefing_sections, 1):
        briefing_items_html += f"""
        <div class="briefing-item" style="background-color: rgba(58, 58, 65, 0.5); border: 1px solid rgba(66, 66, 75, 0.5); padding: 20px; border-radius: 12px; margin-bottom: 16px; backdrop-filter: blur(8px);">
            <h3 style="margin-top: 0; margin-bottom: 12px; color: #ffffff; font-size: 18px; font-weight: 600;">{section['title']}</h3>
            {f'<p style="color: #b8b8c1; font-size: 14px; line-height: 1.6; margin-bottom: 16px;">{section["transcript_preview"]}</p>' if section['transcript_preview'] else ''}
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <a href="{section['briefing_url']}" style="display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; background-color: #e85d04; color: white; text-decoration: none; border-radius: 50%; transition: all 0.2s; box-shadow: 0 0 20px -5px rgba(232, 93, 4, 0.4);">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left: 2px;">
                        <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                </a>
                {f'<span style="color: #747484; font-size: 13px; font-family: monospace;">{section["duration"]}</span>' if section['duration'] else ''}
            </div>
        </div>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'DM Sans', system-ui, sans-serif; 
                line-height: 1.6; 
                color: #eeeef0; 
                background-color: #1a1a1e;
                margin: 0;
                padding: 0;
            }}
            .container {{ 
                max-width: 600px; 
                margin: 0 auto; 
                padding: 0;
                background-color: #1a1a1e;
            }}
            .header {{ 
                background: linear-gradient(135deg, rgba(232, 93, 4, 0.1) 0%, rgba(232, 93, 4, 0.05) 100%);
                border-bottom: 1px solid rgba(66, 66, 75, 0.5);
                padding: 32px 24px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0 0 8px 0;
                color: #ffffff;
                font-size: 24px;
                font-weight: 600;
            }}
            .header p {{
                margin: 0;
                font-size: 14px;
                color: #b8b8c1;
            }}
            .content {{ 
                padding: 24px;
                background-color: #1a1a1e;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Daily Briefings Ready</h1>
                <p>You have {len(briefings)} new briefing{'' if len(briefings) == 1 else 's'}</p>
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
{f"   Duration: {section['duration']}" if section['duration'] else ''}
   Listen: {section['briefing_url']}

"""
    
    text_content = f"""Daily Briefings Ready

You have {len(briefings)} new briefing{'' if len(briefings) == 1 else 's'}:

{briefing_items_text}
    """
    
    # Resend API endpoint
    url = "https://api.resend.com/emails"
    
    # Use onboarding@resend.dev as the from email (for testing without verified sender domain)
    # See: https://docs.novu.co/platform/integrations/email/resend#getting-started
    from_email = "onboarding@resend.dev"
    
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
