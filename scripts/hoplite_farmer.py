import asyncio
import random
import string
import re
import httpx
import os
from playwright.async_api import async_playwright

# --- KONFIGURASI ---
PROMO_CODE = os.getenv("HOPLITE_PROMO", "CLOUDFIRST")
BASE_URL = "https://app.hoplite.sh"

async def create_temp_email():
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.mail.tm/domains")
        domain = r.json()['hydra:member'][0]['domain']
        local_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        address = f"{local_part}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        
        await client.post("https://api.mail.tm/accounts", json={"address": address, "password": password})
        r = await client.post("https://api.mail.tm/token", json={"address": address, "password": password})
        return address, r.json()['token']

async def fetch_verification(token, timeout=120):
    async with httpx.AsyncClient() as client:
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                r = await client.get("https://api.mail.tm/messages", headers={"Authorization": f"Bearer {token}"})
                messages = r.json()['hydra:member']
                if messages:
                    msg_id = messages[0]['id']
                    msg_detail = await client.get(f"https://api.mail.tm/messages/{msg_id}", headers={"Authorization": f"Bearer {token}"})
                    html_content = " ".join(msg_detail.json().get('html', []))
                    text_content = msg_detail.json().get('text', '')
                    
                    # Cari Link Verifikasi
                    link_match = re.search(r'https?://[^\s"\'<>]+', html_content + text_content)
                    if link_match:
                        return link_match.group(0)
            except Exception:
                pass
            await asyncio.sleep(4)
        raise TimeoutError("Email verifikasi tidak kunjung datang.")

async def farm_hoplite():
    email_address, email_token = await create_temp_email()
    print(f"[*] Memproses akun: {email_address}")
    
    async with async_playwright() as p:
        proxy_url = os.getenv("PROXY_URL")
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": proxy_url} if proxy_url else None,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # 1. Buka Signup
            await page.goto(f"{BASE_URL}/signup", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            
            # 2. Isi Email
            await page.fill('input[type="email"]', email_address)
            # Klik Continue/Sign up
            await page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("Sign up")').first.click()
            
            print(f"[*] Menunggu link verifikasi di email...")
            verify_url = await fetch_verification(email_token)
            
            # 3. Buka Link Verifikasi
            await page.goto(verify_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
            print("[+] Email berhasil diverifikasi.")
            
            # 4. Masuk ke Billing
            await page.goto(f"{BASE_URL}/settings/billing", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            
            # 5. Input Promo Code
            print(f"[*] Mencoba memasukkan kode promo: {PROMO_CODE}")
            promo_input = page.locator('input[placeholder*="code" i], input[placeholder*="promo" i], input[name*="coupon" i], input[name*="promo" i]').first
            await promo_input.fill(PROMO_CODE)
            await page.wait_for_timeout(1000)
            
            # Klik Redeem/Apply
            await page.locator('button:has-text("Redeem"), button:has-text("Apply"), button:has-text("Submit")').first.click()
            await page.wait_for_timeout(5000)
            
            print(f"[+] Sukses! Cek dashboard untuk status plan.")
            return {"email": email_address, "status": "success"}
            
        except Exception as e:
            await page.screenshot(path=f"/tmp/hoplite_fail_{email_address}.png")
            print(f"[-] Gagal: {e}")
            return {"email": email_address, "status": "failed", "error": str(e)}
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(farm_hoplite())
