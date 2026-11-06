import asyncio
import random
import string
import re
import httpx
from playwright.async_api import async_playwright
import os

# --- KONFIGURASI ---
PROMO_CODE = "CLOUDFIRST"
BASE_URL = "https://app.hoplite.sh"

# --- FUNGSI EMAIL SEMENTARA (Mail.tm) ---
async def create_temp_email():
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.mail.tm/domains")
        domain = r.json()['hydra:member'][0]['domain']
        
        local_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
        address = f"{local_part}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        
        await client.post("https://api.mail.tm/accounts", json={"address": address, "password": password})
        r = await client.post("https://api.mail.tm/token", json={"address": address, "password": password})
        token = r.json()['token']
        
        return address, token

async def fetch_otp_or_link(token, timeout=120):
    async with httpx.AsyncClient() as client:
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            r = await client.get("https://api.mail.tm/messages", headers={"Authorization": f"Bearer {token}"})
            messages = r.json()['hydra:member']
            if messages:
                msg_id = messages[0]['id']
                msg_detail = await client.get(f"https://api.mail.tm/messages/{msg_id}", headers={"Authorization": f"Bearer {token}"})
                text_content = msg_detail.json()['text']
                
                # Cek apakah ada link verifikasi
                link_match = re.search(r'https?://[^\s]+', text_content)
                if link_match:
                    return "link", link_match.group(0)
                
                # Cek apakah ada kode OTP (6 digit)
                otp_match = re.search(r'\b(\d{6})\b', text_content)
                if otp_match:
                    return "otp", otp_match.group(1)
            await asyncio.sleep(5)
        raise TimeoutError("Verifikasi tidak ditemukan dalam batas waktu")

# --- FUNGSI UTAMA FARMING ---
async def farm_hoplite_account():
    email_address, email_token = await create_temp_email()
    print(f"[*] Memproses akun: {email_address}")
    
    async with async_playwright() as p:
        # Gunakan proxy jika ada di environment variable
        proxy_url = os.getenv("PROXY_URL")
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": proxy_url} if proxy_url else None
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # 1. Buka halaman signup
            await page.goto(f"{BASE_URL}/signup", wait_until="networkidle")
            
            # 2. Isi email (selector mungkin perlu disesuaikan)
            await page.fill('input[type="email"]', email_address)
            await page.click('button[type="submit"]')
            
            # 3. Tunggu verifikasi email
            print(f"[*] Menunggu verifikasi untuk {email_address}...")
            v_type, v_data = await fetch_otp_or_link(email_token)
            
            if v_type == "link":
                await page.goto(v_data, wait_until="networkidle")
            elif v_type == "otp":
                await page.fill('input[type="text"]', v_data)
                await page.click('button[type="submit"]')
            
            # 4. Tunggu masuk ke dashboard
            await page.wait_for_url(f"{BASE_URL}/**", timeout=30000)
            print("[+] Berhasil masuk dashboard.")
            
            # 5. Buka Settings > Billing
            await page.goto(f"{BASE_URL}/settings/billing", wait_until="networkidle")
            
            # 6. Masukkan kode promo
            try:
                # Cari input untuk kode promo
                promo_input = await page.wait_for_selector('input[placeholder*="code" i], input[name*="promo" i], input[name*="coupon" i]', timeout=10000)
                await promo_input.fill(PROMO_CODE)
                
                # Klik tombol Redeem/Apply
                await page.click('button:has-text("Redeem"), button:has-text("Apply")')
                await page.wait_for_timeout(5000) # Tunggu proses
                print("[+] Kode promo berhasil dimasukkan!")
            except Exception as e:
                print(f"[-] Gagal memasukkan kode promo: {e}")
                # Screenshot untuk diagnosa
                await page.screenshot(path=f"/tmp/hoplite_billing_{email_address}.png")
            
            return {"email": email_address, "status": "success"}
            
        except Exception as e:
            print(f"[-] Gagal memproses {email_address}: {e}")
            await page.screenshot(path=f"/tmp/hoplite_fail_{email_address}.png")
            return {"email": email_address, "status": "failed", "error": str(e)}
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(farm_hoplite_account())
