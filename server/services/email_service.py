import logging
from email.message import EmailMessage
import aiosmtplib

from server.config import settings

logger = logging.getLogger(__name__)


async def send_verification_email_async(to_email: str, code: str) -> None:
    
    sender_email = getattr(settings, "smtp_from", None) or getattr(settings, "smtp_user", "")

    message = EmailMessage()
    message["From"] = sender_email
    message["To"] = to_email
    message["Subject"] = "کد تأیید حساب کاربری"

    plain_text = f"کد تایید شما: {code}\nاین کد تا چند دقیقه دیگر معتبر است."
    message.set_content(plain_text)

    html_content = f"""
    <html dir="rtl" lang="fa">
      <body style="font-family: Tahoma, Arial, sans-serif; background-color: #f4f6f9; padding: 30px;">
        <div style="max-width: 480px; margin: 0 auto; background: #ffffff; padding: 25px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); text-align: center;">
          <h2 style="color: #2c3e50; margin-bottom: 20px;">تأیید حساب کاربری</h2>
          <p style="color: #555555; font-size: 14px; line-height: 1.6;">
            از ثبت‌نام شما سپاسگزاریم. لطفاً از کد زیر برای فعال‌سازی حساب خود استفاده کنید:
          </p>
          <div style="margin: 30px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #1a73e8; background: #e8f0fe; padding: 10px 24px; border-radius: 6px; display: inline-block;">
              {code}
            </span>
          </div>
          <p style="color: #888888; font-size: 12px; margin-top: 25px;">
            اگر شما درخواست ساخت حساب نداده‌اید، این پیام را نادیده بگیرید.
          </p>
        </div>
      </body>
    </html>
    """
    message.add_alternative(html_content, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=(settings.smtp_port == 587),
            use_tls=(settings.smtp_port == 465),
            timeout=20,
        )
        logger.info(f"Verification email sent successfully to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send verification email to {to_email}: {e}")


send_verification_email = send_verification_email_async
