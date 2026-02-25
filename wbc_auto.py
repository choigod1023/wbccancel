from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import sys
import ctypes

try:
    from plyer import notification
except ImportError:
    notification = None

try:
    import requests
except ImportError:
    requests = None

# Discord 웹훅 — wbc_auto 전용 (모니터는 DISCORD_WEBHOOK_URL 사용)
WBC_AUTO_DISCORD_WEBHOOK_URL = os.environ.get("WBC_AUTO_DISCORD_WEBHOOK_URL", "").strip()


def notify_windows(title, message, timeout=10):
    """Windows 토스트 알림 표시. plyer 미설치 시 무시."""
    if notification is None:
        return
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="WBC Auto",
            timeout=timeout,
        )
    except Exception:
        pass


def notify_discord(title, message, is_error=False):
    """Discord 웹훅으로 @everyone 멘션과 함께 알림 전송."""
    if not WBC_AUTO_DISCORD_WEBHOOK_URL or requests is None:
        return
    try:
        # 임베드 description 최대 4096자 제한 — 초과 시 잘라서 전송
        max_len = 4096
        if len(message) > max_len:
            message = message[: max_len - 20] + "\n...[잘림]"
        payload = {
            "content": "@everyone",
            "allowed_mentions": {"parse": ["everyone"]},
            "embeds": [{
                "title": title,
                "description": message,
                "color": 0xE74C3C if is_error else 0x00AA00,
            }],
        }
        r = requests.post(WBC_AUTO_DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code not in (200, 204):
            print(f"[Discord] 전송 실패: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[Discord] 오류: {e}")


def bring_chrome_to_front(driver):
    """
    Windows API로 현재 Chrome 창을 맨 앞으로 가져옴.
    한자(取引完了) 없이 클릭해서 결제로 넘어갔을 때 호출.
    """
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        title = (driver.title or "").strip()
        if not title:
            title = "Chrome"
        hwnd = None

        def enum_cb(hwnd_param, _):
            nonlocal hwnd
            if user32.IsWindowVisible(hwnd_param):
                length = user32.GetWindowTextLengthW(hwnd_param) + 1
                buf = ctypes.create_unicode_buffer(length)
                user32.GetWindowTextW(hwnd_param, buf, length)
                if title in buf.value or "Chrome" in buf.value:
                    hwnd = hwnd_param
                    return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(enum_cb), None)
        if hwnd:
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def login(driver, username, password):
    """Login to the system"""
    try:
        # Wait for login page to load and find login elements
        # You'll need to adjust the following selectors to match the actual page
        driver.get("https://tradead.tixplus.jp/wbc2026/login")
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, 'id'))  # Adjust selector
        )
        password_field = driver.find_element(By.NAME, 'password')  # Adjust selector
        
        # Enter credentials
        username_field.clear()
        username_field.send_keys(username)
        password_field.clear()
        password_field.send_keys(password)
        
        # Submit login form
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")  # Adjust selector
        login_button.click()
        
        # Wait for login to complete
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "user-profile"))  # Adjust selector
        )
        
        print("Login successful!")
        
    except Exception as e:
        print(f"Login failed: {e}")

def click_available_tickets(driver):
    """Click on available ticket (div[2] 블록만 대상). 取引完了면 새로고침 후 재시도."""
    i = 2
    while True:
        try:
            try:
                xpath = f'//*[@id="app"]/div/div/div[3]/div/div[{i}]/div/div[1]/div/div[1]/div/h6'
                h6_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )

                # h6 요소의 텍스트 확인
                text = h6_element.text

                # "取引完了"가 포함된 경우: 제목·가격 정보와 함께 출력 후 새로고침
                if "取引完了" in text:
                    title_str = ""
                    price_str = ""
                    try:
                        title_el = driver.find_element(By.XPATH, f'//*[@id="app"]/div/div/div[3]/div/div[{i}]/div/div[1]/div/div[1]/h6')
                        title_str = (title_el.text or "").strip()
                    except Exception:
                        pass
                    try:
                        price_block = driver.find_element(By.XPATH, f'//*[@id="app"]/div/div/div[3]/div/div[{i}]/div/div[2]/div')
                        price_str = (price_block.text or "").strip()
                    except Exception:
                        pass
                    if title_str or price_str:
                        print(f"取引完了 — 제목: {title_str} | {price_str} — 페이지 새로고침 후 재시도")
                    else:
                        print("取引完了 — 페이지 새로고침 후 재시도")
                    driver.refresh()
                    time.sleep(0.3)
                    continue

                # 그 외에는 클릭 (딜레이 최소화)
                h6_element.click()
                print(f"클릭됨: {i} 번째 요소")
                time.sleep(0.3)
                break

            except Exception as e:
                # h6가 없어도 .../div[{i}]/div/div[1]/div/div[1] 까지는 존재함 → 그 부모의 부모 클릭
                try:
                    base_xpath = f'//*[@id="app"]/div/div/div[3]/div/div[{i}]/div/div[1]/div/div[1]'
                    base_el = driver.find_element(By.XPATH, base_xpath)
                    parent_parent = base_el.find_element(By.XPATH, "..").find_element(By.XPATH, "..")
                    parent_parent.click()
                    print(f"클릭됨 (부모의 부모): {i} 번째 블록")
                    time.sleep(0.3)
                    break
                except Exception as e2:
                    print(f"{i} 번째 요소 없음 또는 오류: {e2}")
                    driver.refresh()
                    time.sleep(0.3)
                    continue

        except Exception as e:
            print(f"Ticket clicking failed: {e}")
            break


def complete_purchase_flow(driver, wait_sec=10):
    """
    티켓 클릭 후 다음 페이지부터 결제 완료까지 진행.
    각 단계마다 요소가 보일 때까지 대기 후 클릭.
    """
    bring_chrome_to_front(driver)
    wait = WebDriverWait(driver, wait_sec)
    click = lambda xpath: wait.until(EC.element_to_be_clickable((By.XPATH, xpath))).click()

    try:
        # --- 1단계: 티켓 클릭 후 나온 페이지에서 '다음' 링크 클릭 ---
        click("//*[@id=\"app\"]/div/div/div[3]/div[2]/div/a")
        time.sleep(1)

        # --- 2단계: 첫 번째 체크박스 동의 ---
        click("//*[@id=\"app\"]/div/div/form/div[3]/div/label/span[1]/input")
        time.sleep(0.5)

        # --- 3단계: 두 번째 체크박스(visible) 동의 ---
        click("//*[@id=\"app\"]/div/div/form/div[3]/div[3]/label/span[1]/input")
        time.sleep(0.5)

        # --- 4단계: 폼 제출 → 다음 페이지 ---
        click("//*[@id=\"app\"]/div/div/form/div[3]/div[3]/button[1]")
        time.sleep(1)

        # --- 5단계: 라디오 버튼 선택 ---
        click("//*[@id=\"app\"]/div/div/form/div[2]/div[1]/div/div/div/label/span[1]/input")
        time.sleep(0.5)

        # --- 6단계: 제출 버튼 클릭 → 다음 페이지 ---
        click("//*[@id=\"app\"]/div/div/form/div[2]/div[2]/div/button")
        time.sleep(1)

        # --- 7단계: 두 번째 라디오 버튼 선택 ---
        click("//*[@id=\"app\"]/div/div/form/div[2]/div[1]/div/div/div/div/div/label/span[1]/input")
        time.sleep(0.5)

        # --- 8단계: 제출 버튼 클릭 → 다음 페이지 ---
        click("//*[@id=\"app\"]/div/div/form/div[2]/div[2]/div/button")
        time.sleep(1)

        # --- 9단계: 최종 완료 버튼 클릭 ---
        click("//*[@id=\"app\"]/div/div/form/div[2]/div[4]/div/button[2]")
        print("결제 플로우 완료.")
        notify_windows("WBC Auto", "결제 플로우 완료.", timeout=10)
        notify_discord("WBC Auto — 결제 플로우 완료", "결제 단계가 정상적으로 완료되었습니다.", is_error=False)
    except Exception as e:
        # 요청대로: 에러 메시지만 알림으로 전송
        msg = f"결제 플로우 중 오류: {e}"
        print(msg)
        notify_windows("WBC Auto 오류", msg, timeout=15)
        notify_discord("WBC Auto — 결제 플로우 오류", msg, is_error=True)
        raise


# Main execution
if __name__ == "__main__":
    # listings/{id} 의 id 입력: 인자로 주거나 실행 후 입력
    if len(sys.argv) >= 2:
        listing_id = sys.argv[1].strip()
    else:
        listing_id = input("listings ID 입력 (예: 1519): ").strip()
    if not listing_id:
        print("listings ID가 비어 있습니다. 종료합니다.")
        sys.exit(1)
    listings_url = f"https://tradead.tixplus.jp/wbc2026/buy/bidding/listings/{listing_id}"

    # Chrome 드라이버 설정
    options = Options()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome()
    
    try:
        # 웹사이트 열기 후 로그인 (한 번만)
        driver.get(listings_url)
        login(driver, "choigod10234@gmail.com", "jjang486")

        # 로그인 이후만 반복: 리스팅 이동 → 티켓 클릭 → 결제 플로우 (에러 나면 여기서만 재시도)
        while True:
            try:
                driver.get(listings_url)
                click_available_tickets(driver)
                complete_purchase_flow(driver)
                break
            except Exception as e:
                # 요청대로: 에러 메시지만 알려주고, 로그인 이후 단계만 재시도
                err_msg = f"Execution failed: {e}. 로그인 이후 단계부터 재시도합니다."
                print(err_msg)
                notify_windows("WBC Auto 오류", err_msg, timeout=10)
                notify_discord("WBC Auto — 실행 오류", err_msg, is_error=True)
                time.sleep(0.8)
    except Exception as e:
        print(f"Execution failed: {e}")
    finally:
        # 에러가 나도 Python이 바로 종료되면 크롬(자식 프로세스)이 같이 꺼짐 → 대기시켜 프로세스 유지
        print("동작 종료. 브라우저는 열린 상태로 유지됩니다.")
        print("이 콘솔 창을 닫지 마세요. 닫으면 크롬도 함께 종료됩니다.")
        print("스크립트만 끝내려면 여기서 Ctrl+C 를 누르세요 (그때는 크롬도 꺼질 수 있음).")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("종료합니다.")