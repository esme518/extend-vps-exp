import asyncio
import base64
import binascii
import hashlib
import hmac
import os
import sys
import logging
import aiohttp
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from playwright_captcha import CaptchaType, ClickSolver, FrameworkType
from playwright_captcha.utils.camoufox_add_init_script.add_init_script import get_addon_path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def generate_totp(secret: str, interval: int = 30, digits: int = 6) -> str:
    normalized = ''.join(secret.split()).upper()
    padding = '=' * ((8 - len(normalized) % 8) % 8)
    try:
        key = base64.b32decode(normalized + padding, casefold=True)
    except binascii.Error as exc:
        raise ValueError('AUTH_LOGIN_OTP is not a valid base32 TOTP secret.') from exc

    counter = int(time.time() // interval)
    counter_bytes = counter.to_bytes(8, 'big')
    digest = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = int.from_bytes(digest[offset:offset + 4], 'big') & 0x7FFFFFFF
    return str(code_int % (10 ** digits)).zfill(digits)


def parse_japanese_date(raw: str) -> date:
    normalized = raw.strip().replace('年', '-').replace('月', '-').replace('日', '')
    return datetime.strptime(normalized, '%Y-%m-%d').date()


def format_server_info_message(prefix: str, info: dict, today_jst: date, should_renew: bool | None = None) -> str:
    lines = [prefix]

    if info.get('server_name'):
        lines.append(f"server: {info['server_name']}")
    if info.get('service_code'):
        lines.append(f"service_code: {info['service_code']}")
    if info.get('uuid'):
        lines.append(f"uuid: {info['uuid']}")
    if info.get('expiry_date_raw'):
        lines.append(f"expiry: {info['expiry_date_raw']}")
    if info.get('update_date_raw'):
        lines.append(f"last_update: {info['update_date_raw']}")

    lines.append(f"today_jst: {today_jst.isoformat()}")
    if should_renew is not None:
        lines.append(f"should_renew: {should_renew}")

    return '\n'.join(lines)


async def send_tg_notice(token: str, user_id: str, message: str):
    if not token or not user_id:
        return

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': user_id,
        'text': message,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logging.warning(f'Telegram notice failed: {resp.status} {body}')
    except Exception as exc:
        logging.warning(f'Telegram notice raised an exception: {exc}')


async def extract_server_info(page) -> dict:
    return await page.eval_on_selector_all(
        'table.table tr',
        """
        rows => {
            const result = {};
            for (const row of rows) {
                const th = row.querySelector('th');
                const td = row.querySelector('td');
                if (!th || !td) continue;
                const key = th.textContent.trim();
                const value = td.innerText.trim().replace(/\\s+/g, ' ');
                result[key] = value;
            }
            return result;
        }
        """
    )


async def complete_optional_otp(page, otp_secret: str):
    otp_path = '/xapanel/myaccount/twostepauth/index'

    for _ in range(60):
        current_url = page.url
        if '/xapanel/xvps/' in current_url:
            return
        if otp_path in current_url:
            logging.info('Two-step authentication detected. Submitting TOTP code...')
            if not otp_secret:
                raise RuntimeError('Two-step authentication page detected but AUTH_LOGIN_OTP is not set.')

            await page.wait_for_selector('input[name="auth_code"]', timeout=10000)
            otp_code = generate_totp(otp_secret)
            await page.locator('input[name="auth_code"]').fill(otp_code)
            await page.locator('input[type="submit"][value="ログイン"]').click(no_wait_after=True)
            return
        await asyncio.sleep(0.5)

    raise TimeoutError('Timed out waiting for either the XServer dashboard or the two-step authentication page.')


async def is_effectively_enabled(locator) -> bool:
    try:
        disabled = await locator.is_disabled()
        if disabled:
            return False
    except Exception:
        pass

    try:
        aria_disabled = await locator.get_attribute('aria-disabled')
        if aria_disabled and aria_disabled.lower() == 'true':
            return False
    except Exception:
        pass

    try:
        button_class = await locator.get_attribute('class') or ''
        if 'disabled' in button_class.lower():
            return False
    except Exception:
        pass

    return True


async def wait_for_effectively_enabled(locator, timeout_ms: int = 20000, poll_ms: int = 500) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if await is_effectively_enabled(locator):
            return True
        await asyncio.sleep(poll_ms / 1000)
    return await is_effectively_enabled(locator)

async def main():
    email = os.getenv('EMAIL', '')
    password = os.getenv('PASSWORD', '')
    auth_login_otp = os.getenv('AUTH_LOGIN_OTP', '')
    notice_tg_token = os.getenv('NOTICE_TG_TOKEN', '')
    notice_tg_userid = os.getenv('NOTICE_TG_USERID', '')
    proxy_server = os.getenv('PROXY_SERVER')
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'

    options = {
        'headless': False,
        'humanize': True,
        'geoip': True,
        'os': 'macos',
        'screen': Screen(max_width=1280, max_height=720),
        'window': (1280, 720),
        'locale': 'ja-JP',
        'disable_coop': True,
        'i_know_what_im_doing': True,
        'config': {'forceScopeAccess': True},
        'main_world_eval': True,
        'addons': [os.path.abspath(get_addon_path())]
    }
    
    if proxy_server:
        parsed = urlparse(proxy_server)
        proxy_config = {
            'server': f"{parsed.scheme}://{parsed.hostname}{f':{parsed.port}' if parsed.port else ''}"
        }
        if parsed.username:
            proxy_config['username'] = parsed.username
        if parsed.password:
            proxy_config['password'] = parsed.password
        options['proxy'] = proxy_config
    
    logging.info('Launching Camoufox in Python...')
    async with AsyncCamoufox(**options) as browser:
        context = await browser.new_context()
        page = await context.new_page()
        framework = FrameworkType.CAMOUFOX

        try:
            logging.info('Navigating to login...')
            # Use domcontentloaded to avoid getting stuck on tracking pixels
            await page.goto('https://secure.xserver.ne.jp/xapanel/login/xvps/', wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_selector('#memberid', timeout=30000)
            
            await page.locator('#memberid').fill(email)
            await page.locator('#user_password').fill(password)
            
            logging.info('Logging in...')
            await page.locator('text="ログインする"').click(no_wait_after=True)

            logging.info('Waiting for dashboard or two-step authentication...')
            await complete_optional_otp(page, auth_login_otp)

            logging.info('Waiting for dashboard to load...')
            await page.wait_for_selector('a[href^="/xapanel/xvps/server/detail?id="]', timeout=30000)

            logging.info('Navigating server details...')
            await page.locator('a[href^="/xapanel/xvps/server/detail?id="]').first.click(no_wait_after=True)
            
            logging.info('Waiting for server detail page...')
            await page.wait_for_selector('text="更新する"', timeout=30000)

            server_info_raw = await extract_server_info(page)
            server_info = {
                'uuid': server_info_raw.get('UUID', ''),
                'server_name': server_info_raw.get('サーバー名', ''),
                'expiry_date_raw': server_info_raw.get('利用期限', '').split('更新する')[0].strip(),
                'update_date_raw': server_info_raw.get('更新', ''),
                'service_code': server_info_raw.get('サービスコード', ''),
            }

            if not server_info['expiry_date_raw']:
                raise RuntimeError('Could not find 利用期限 on the server detail page.')

            expiry_date = parse_japanese_date(server_info['expiry_date_raw'])
            today_jst = datetime.now(ZoneInfo('Asia/Tokyo')).date()
            should_renew = today_jst == (expiry_date - timedelta(days=1))

            logging.info(
                'Server detail: service_code=%s expiry=%s last_update=%s today_jst=%s should_renew=%s',
                server_info['service_code'] or '-',
                server_info['expiry_date_raw'],
                server_info['update_date_raw'] or '-',
                today_jst.isoformat(),
                should_renew,
            )

            if not should_renew:
                logging.info('SKIP: Today is not the day before expiry, so renewal will not be attempted.')
                await send_tg_notice(
                    notice_tg_token,
                    notice_tg_userid,
                    format_server_info_message('XServer VPS renewal skipped.', server_info, today_jst, should_renew=False),
                )
                await page.screenshot(path='skip_renewal.png', full_page=True)
                return

            await page.locator('text="更新する"').click()

            logging.info('Proceeding to renewal selection...')
            await page.locator('text="引き続き無料VPSの利用を継続する"').click(no_wait_after=True)
            
            logging.info('Waiting for renewal page or status...')
            
            # Wait for either the captcha image OR the suspension notice section
            # This will raise TimeoutError if neither appears within 30s (correct behavior)
            await page.wait_for_selector('img[src^="data:"], .newApp__suspended', timeout=30000)
            
            # If the suspension notice is visible, skip renewal gracefully
            if await page.locator('.newApp__suspended').is_visible():
                logging.info('SKIP: Renewal is not yet available (detected .newApp__suspended).')
                logging.info('XServer: "利用期限の1日前から更新手続きが可能です。"')
                await send_tg_notice(
                    notice_tg_token,
                    notice_tg_userid,
                    format_server_info_message('XServer VPS renewal skipped: not yet available.', server_info, today_jst, should_renew=True),
                )
                await page.screenshot(path='skip_renewal.png', full_page=True)
                return

            logging.info('Retrieving captcha...')
            body = await page.eval_on_selector('img[src^="data:"]', 'img => img.src')
            
            # Solve custom image captcha
            async with aiohttp.ClientSession() as session:
                async with session.post('https://captcha-120546510085.asia-northeast1.run.app', data=body) as resp:
                    code = await resp.text()
            
            logging.info(f'Resolved captcha code: {code}')
            
            input_loc = page.locator('[placeholder="上の画像の数字を入力"]')
            await input_loc.focus()
            await input_loc.press_sequentially(code, delay=100)
            
            try:
                # Use playwright-captcha library to handle the Turnstile challenge
                async with ClickSolver(framework=framework, page=page) as solver:
                    await solver.solve_captcha(captcha_container=page, captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE)
                logging.info('Turnstile interaction finished.')
            except Exception as e:
                # Some solvers might throw errors even if the click was successful.
                # We catch and log them as warnings to allow the script to proceed.
                logging.warning(f'Turnstile solve loop exited: {e}')

            await page.wait_for_selector('text="無料VPSの利用を継続する"', timeout=60000)
            await page.screenshot(path='before_click.png', full_page=True)
            
            button = page.locator('text="無料VPSの利用を継続する"')
            logging.info('Waiting for final renewal button to become enabled...')
            is_enabled = await wait_for_effectively_enabled(button, timeout_ms=60000, poll_ms=500)

            if not is_enabled:
                err_msg = 'Final button is DISABLED! Renewal failed or Turnstile verification was unsuccessful.'
                logging.error(err_msg)
                if not debug_mode:
                    raise Exception(err_msg)
            else:
                if debug_mode:
                    logging.info('DEBUG MODE: Final button is ENABLED and ready to click. Skipping click to preserve daily limit.')
                    await button.click(timeout=30000, no_wait_after=True)
                    logging.info('Final renewal submitted successfully!')
                    await send_tg_notice(
                        notice_tg_token,
                        notice_tg_userid,
                        format_server_info_message('XServer VPS renewal ready in debug mode.', server_info, today_jst, should_renew=True),
                    )
                else:
                    logging.info('Executing final renewal submission...')
                    await button.click(timeout=30000, no_wait_after=True)
                    logging.info('Final renewal submitted successfully!')
                    await send_tg_notice(
                        notice_tg_token,
                        notice_tg_userid,
                        format_server_info_message('XServer VPS renewal submitted successfully.', server_info, today_jst, should_renew=True),
                    )
                    await asyncio.sleep(10)
            
            logging.info('Done!')
            if debug_mode:
                logging.info('DEBUG MODE: Keeping browser open for 60 seconds for inspection...')
                await asyncio.sleep(60)
        
        except Exception as e:
            logging.error(f'Script Error: {e}')
            try:
                today_jst = datetime.now(ZoneInfo('Asia/Tokyo')).date()
                await send_tg_notice(
                    notice_tg_token,
                    notice_tg_userid,
                    f'XServer VPS renewal failed.\nerror: {e}\ntoday_jst: {today_jst.isoformat()}',
                )
            except Exception:
                pass
            sys.exit(1)
        finally:
            await asyncio.sleep(2)
            await context.close()

async def test_tg():
    email = os.getenv('EMAIL', '')
    password = os.getenv('PASSWORD', '')
    auth_login_otp = os.getenv('AUTH_LOGIN_OTP', '')
    notice_tg_token = os.getenv('NOTICE_TG_TOKEN', '')
    notice_tg_userid = os.getenv('NOTICE_TG_USERID', '')
    proxy_server = os.getenv('PROXY_SERVER')
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
    await send_tg_notice(
                    notice_tg_token,
                    notice_tg_userid,
                    'XServer VPS tg test',
                )
if __name__ == '__main__':
    asyncio.run(main())
    # asyncio.run(test_tg())
