import os
import json
import time
import glob
import csv
from urllib.parse import quote
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- 環境変数 ---
USER_ID = os.environ["USER_ID"]
PASSWORD = os.environ["USER_PASS"]
json_creds = json.loads(os.environ["GCP_JSON"])

# --- 設定 ---
TARGET_URL = "https://asp1.six-pack.xyz/admin/log/click/list"
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
SHEET_NAME = "今月_mcv_raw"

def update_google_sheet(csv_path):
    """CSVの中身を読み込んでスプレッドシートに張り付ける関数"""
    print(f"スプレッドシートへの転記を開始: {SHEET_NAME}")
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(json_creds, scopes=scopes)
    service = build('sheets', 'v4', credentials=creds)

    # 1. CSVデータの読み込み (文字コード判定付き)
    csv_data = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            csv_data = list(reader)
    except UnicodeDecodeError:
        print("UTF-8での読み込みに失敗しました。Shift_JIS(CP932)で再試行します。")
        try:
            with open(csv_path, 'r', encoding='cp932') as f:
                reader = csv.reader(f)
                csv_data = list(reader)
        except Exception as e:
            print(f"CSV読み込みエラー: {e}")
            return

    if not csv_data:
        print("CSVデータが空のため転記をスキップします。")
        return

    # 2. シートのクリア
    try:
        service.spreadsheets().values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_NAME
        ).execute()
        print("既存データをクリアしました。")
    except Exception as e:
        print(f"シートクリアエラー: {e}")

    # 3. データの書き込み
    body = {'values': csv_data}
    try:
        result = service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        print(f"スプレッドシート更新完了: {result.get('updatedCells')} セル更新")
    except Exception as e:
        print(f"書き込みエラー: {e}")

def main():
    print("=== MCV取得処理開始 ===")

    download_dir = os.path.join(os.getcwd(), "downloads_mcv")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    # 以前のCSV削除
    for f in glob.glob(os.path.join(download_dir, "*")):
        os.remove(f)

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 20)

    try:
        # --- 1. ログイン ---
        safe_user = quote(USER_ID, safe='')
        safe_pass = quote(PASSWORD, safe='')
        url_body = TARGET_URL.replace("https://", "").replace("http://", "")
        auth_url = f"https://{safe_user}:{safe_pass}@{url_body}"

        print(f"アクセス中: {TARGET_URL}")
        driver.get(auth_url)
        time.sleep(3)

        print("画面を再読み込みします...")
        driver.get(auth_url)
        time.sleep(5)

        # --- 2. 検索メニューを開く ---
        print("検索メニューを開きます...")
        try:
            filter_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '絞り込み検索')]")))
            filter_btn.click()
            time.sleep(3)
        except:
            pass

        # --- 3. 「今月」ボタンをクリック ---
        print("「今月」ボタンを選択します...")
        try:
            current_month_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='今月']")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", current_month_btn)
            time.sleep(1)
            current_month_btn.click()
            print("「今月」ボタンをクリックしました")
            time.sleep(3)
        except Exception as e:
            print(f"「今月」ボタンの操作エラー: {e}")

        # --- 4. パートナー入力 ---
        print("パートナーを入力します...")
        try:
            partner_label = driver.find_element(By.XPATH, "//div[contains(text(), 'パートナー')] | //label[contains(text(), 'パートナー')]")
            partner_target = partner_label.find_element(By.XPATH, "./following::input[contains(@placeholder, '選択')][1]")
            partner_target.click()
            time.sleep(1)
            active_elem = driver.switch_to.active_element
            active_elem.send_keys("株式会社フルアウト")
            time.sleep(3)
            active_elem.send_keys(Keys.ENTER)
            print("パートナーを選択しました")
            time.sleep(2)
        except Exception as e:
            print(f"パートナー入力エラー: {e}")

        # --- 5. 検索ボタン実行 ---
        print("検索ボタンを探して押します...")
        try:
            search_btns = driver.find_elements(By.XPATH, "//input[@value='検索'] | //button[contains(text(), '検索')]")
            target_search_btn = None
            for btn in search_btns:
                if btn.is_displayed():
                    target_search_btn = btn
            if target_search_btn:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_search_btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", target_search_btn)
                print("検索ボタンをクリックしました")
            else:
                webdriver.ActionChains(driver).send_keys(Keys.ENTER).perform()
        except Exception as e:
            print(f"検索ボタン操作エラー: {e}")

        # --- 検索結果の反映待ち ---
        print("検索結果を待機中...")
        time.sleep(15)

        # --- 6. CSV生成ボタン ---
        print("CSV作成ボタンを押します...")
        try:
            csv_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'CSV') or @value='CSV作成' or @value='CSV生成']")))
            driver.execute_script("arguments[0].click();", csv_btn)
            print("CSVボタンをクリックしました")
        except Exception as e:
            print(f"CSVボタンエラー: {e}")
            return

        # ダウンロード待ち
        print("ダウンロード待機中...")
        time.sleep(5)
        csv_file_path = None
        for i in range(20):
            files = glob.glob(os.path.join(download_dir, "*.csv"))
            if files:
                csv_file_path = files[0]
                break
            time.sleep(3)

        if not csv_file_path:
            print("【エラー】CSVファイルが見つかりません。")
            return

        print(f"ダウンロード成功: {csv_file_path}")

        # --- 7. スプレッドシートへ転記 ---
        update_google_sheet(csv_file_path)

    except Exception as e:
        print(f"【エラー発生】: {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
