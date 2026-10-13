import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_verification_email_html(otp_code: str, user_name: str = "Citizen") -> str:
    """Generate high-fidelity monochrome & glass HTML email matching the Voice2Gov UI."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Voice2Gov Verification Code</title>
</head>
<body style="margin: 0; padding: 0; background-color: #08080A; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; color: #FAFAFA;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #08080A; padding: 40px 16px;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 520px; background: #101014; border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 20px; overflow: hidden; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);">
          
          <!-- Header Bar -->
          <tr>
            <td style="padding: 36px 36px 20px 36px; text-align: center; border-bottom: 1px solid rgba(255, 255, 255, 0.06); background: radial-gradient(circle at 50% 0%, rgba(200, 214, 255, 0.08), transparent 70%);">
              <div style="display: inline-block; padding: 4px 12px; border-radius: 999px; background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 12px;">
                <span style="font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #A0A0AA;">Citizen Security</span>
              </div>
              <h1 style="margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; color: #FFFFFF;">Voice2Gov</h1>
              <p style="margin: 4px 0 0 0; font-size: 13px; color: #8E8E93;">AI-Powered Civic Grievance Platform</p>
            </td>
          </tr>

          <!-- Body Content -->
          <tr>
            <td style="padding: 32px 36px;">
              <h2 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 600; color: #FFFFFF;">Verify your account</h2>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 22px; color: #A0A0AA;">
                Hello <strong style="color: #FFFFFF;">{user_name}</strong>,<br>
                Thank you for joining Voice2Gov. Use the 6-digit one-time password (OTP) below to activate your account and access civic services:
              </p>

              <!-- OTP Glass Highlight Box -->
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 20px 0;">
                <tr>
                  <td align="center" style="background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.16); border-radius: 14px; padding: 24px 16px;">
                    <div style="font-size: 38px; font-weight: 800; letter-spacing: 12px; color: #FFFFFF; font-family: 'SF Pro Display', -apple-system, monospace;">
                      {otp_code}
                    </div>
                    <div style="margin-top: 10px; font-size: 12px; font-weight: 500; color: #8E8E93;">
                      ⏱ Valid for 1 minute (60 seconds)
                    </div>
                  </td>
                </tr>
              </table>

              <p style="margin: 24px 0 0 0; font-size: 13px; line-height: 20px; color: #71717A;">
                Security notice: Never disclose this code to anyone. Voice2Gov officials will never request your OTP. If you did not create an account, you can safely ignore this email.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 36px 28px 36px; text-align: center; border-top: 1px solid rgba(255, 255, 255, 0.06); background: rgba(0, 0, 0, 0.2);">
              <p style="margin: 0; font-size: 11px; color: #52525B;">
                © 2026 Voice2Gov · Empowering citizens with real-time civic transparency.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


class EmailService:
    """Free Google SMTP email service with HTML UI matching the Voice2Gov design system."""

    @staticmethod
    async def send_verification_otp(to_email: str, otp_code: str, user_name: str = "Citizen") -> bool:
        """Send 6-digit OTP code to citizen email via Google SMTP in a background thread."""

        def _send_sync() -> bool:
            smtp_host = settings.smtp_host or "smtp.gmail.com"
            smtp_port = settings.smtp_port or 587
            smtp_user = settings.smtp_user.strip()
            smtp_pass = settings.smtp_password.strip()
            from_email = settings.smtp_from_email.strip() or smtp_user or "noreply@voice2gov.org"
            from_name = settings.smtp_from_name or "Voice2Gov Verification"

            # Fallback for dev / unconfigured credentials
            if not smtp_user or not smtp_pass:
                logger.warning(
                    "[EMAIL SERVICE] Google SMTP credentials not configured (SMTP_USER/SMTP_PASSWORD). "
                    "Verification OTP for %s is: %s",
                    to_email,
                    otp_code,
                )
                return True

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"{otp_code} is your Voice2Gov verification code"
            msg["From"] = f"{from_name} <{from_email}>"
            msg["To"] = to_email

            plain_text = (
                f"Hello {user_name},\n\n"
                f"Your Voice2Gov verification code is: {otp_code}\n"
                f"This code will expire in 10 minutes.\n\n"
                f"If you did not request this, please ignore this email.\n"
                f"© Voice2Gov Civic Platform"
            )
            html_text = generate_verification_email_html(otp_code, user_name)

            msg.attach(MIMEText(plain_text, "plain"))
            msg.attach(MIMEText(html_text, "html"))

            try:
                if smtp_port == 465:
                    server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12)
                else:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=12)
                    server.ehlo()
                    if settings.smtp_use_tls:
                        server.starttls()
                        server.ehlo()

                server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, [to_email], msg.as_string())
                server.quit()
                logger.info("[EMAIL SERVICE] Verification email sent successfully to %s", to_email)
                return True
            except Exception as e:
                logger.error("[EMAIL SERVICE] Failed to send email via Google SMTP to %s: %s", to_email, e)
                # Keep service operational even if external SMTP is temporarily unreachable
                return False

        return await asyncio.to_thread(_send_sync)

