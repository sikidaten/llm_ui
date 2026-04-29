# -*- coding: utf-8 -*-
import contextlib
import datetime
import io
import os
import subprocess
# open playwright
from playwright.sync_api import sync_playwright
from playwright_stealth.stealth import Stealth
import json
import re

from utils import chat_with_gpt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(BASE_DIR, "work")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "./")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def get_work_file_path(filename):
    ensure_dir(WORK_DIR)
    return os.path.join(WORK_DIR, filename)


def save_screenshot(page):
    DDHHMMSS = datetime.datetime.now().strftime("%d%H%M%S")
    screenshot_path = get_work_file_path(f"{DDHHMMSS}screenshot.png")
    page.screenshot(path=screenshot_path)
    return screenshot_path


def get_left_half_window_bounds():
    fallback_width = 960
    fallback_height = 1080
    try:
        output = subprocess.check_output(
            [
                "osascript",
                "-e",
                'tell application "Finder" to get bounds of window of desktop',
            ],
            text=True,
        ).strip()
        left, top, right, bottom = [int(value.strip()) for value in output.split(",")]
        width = max(((right - left) * 3) // 4, 800)
        height = max(bottom - top, 600)
        return left, top, width, height
    except Exception:
        return 0, 0, fallback_width, fallback_height


def save_download(download):
    ensure_dir(DOWNLOAD_DIR)
    filename = download.suggested_filename or "downloaded_file"
    target_path = os.path.join(DOWNLOAD_DIR, filename)
    base, ext = os.path.splitext(target_path)
    suffix = 1
    while os.path.exists(target_path):
        target_path = f"{base}_{suffix}{ext}"
        suffix += 1
    download.save_as(target_path)
    print(f"Downloaded file saved to {target_path}")
    return target_path


def get_latest_screenshot_image_path():
    import glob

    ensure_dir(WORK_DIR)
    list_of_files = glob.glob(os.path.join(WORK_DIR, "*.png"))
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def get_current_script_source():
    with open(__file__, "r", encoding="utf-8") as f:
        return f.read()


def action(browser,purpose):
    page=browser.contexts[0].pages[-1]
    exec_output = ""
    page.wait_for_load_state("networkidle")
    html=page.content()
    script_source = get_current_script_source()
    with open(get_work_file_path("page.html"), "w", encoding="utf-8") as f:
        f.write(html)
    save_screenshot(page)
    # exit()
    ret = chat_with_gpt(
        f"WEBのスクリーンショットが与えられます。\n目的:{purpose}、\nこの目的を実行したいです。実行すべき最低限必要な処理だけを記載してください。実行すべきPlaywrightのコードをPYTHONで生成してください:生成されたコードはexecで実実行されます。コードは最低限でいいです。現在Playwrightを実行中でページを開いていて、新たに起動する必要はありません。page変数は定義されています。awaitもつけないでください。各アクションの後は固定待機を使わず、必要ならpage.wait_for_load_state(\"networkidle\")を使ってください。fillするときもDelayを人間らしく200以上でランダムでキリが悪い値をハードコーディングで置いてください。Fillするときは適度にDelayしてください。ダウンロードやエクスポートの操作なら必ずwith page.expect_download() as download_info: を使ってクリックし、その後 download = download_info.value として save_download(download) を呼んでください。ダウンロード結果は result = save_download(download) のように result に代入してください。テキスト取得など確認結果がある場合も result に文字列を入れてください。アクションが成功したか失敗したかメッセージでわかるようにしてください。このファイル全体のコードを参考にしてください。\n{script_source=}\n{html=}",
        images=[get_latest_screenshot_image_path()]
    )
    print(ret)
    ret=ret.replace("```python","").replace("```","")
    try:
        stdout_buffer = io.StringIO()
        exec_locals = {"page": page, "browser": browser, "result": ""}
        with contextlib.redirect_stdout(stdout_buffer):
            exec(ret, globals(), exec_locals)
        exec_output = exec_locals.get("result") or stdout_buffer.getvalue().strip()
    except Exception as e:
        exec_output = f"Error occurred while executing generated code: {e}"
        print(exec_output)
    page.wait_for_load_state("networkidle")
    save_screenshot(page)
    return exec_output
    # exit()
    # Split html into 1000 character chunks
    # chunk_size = 10000
    # chunks = [html[i:i+chunk_size] for i in range(0, len(html), chunk_size)]
    # for chunk in chunks:

    #     ret = chat_with_gpt(
    #         f"HTMLが与えられます。ログインが必要なページかどうかを判断してください。もし必要なら、ログインボタンのIDやログインページへのリンクを返してください。"
    #         f"HTML fragment: {html}"
    #     )
    #     print("Sign in" in chunk)
    #     print(ret)  # Or handle each chunk as needed
    #     exit()
# open google drive
with sync_playwright() as p:
    window_x, window_y, window_width, window_height = get_left_half_window_bounds()
    browser = p.chromium.launch(
        headless=False,
        args=[
            f"--window-position={window_x},{window_y}",
            f"--window-size={window_width},{window_height}",
        ],
    )
    context = browser.new_context(
        accept_downloads=True,
        no_viewport=True,
        # user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    )
    context.on("download", save_download)
    page = context.new_page()
    # Stealth().apply_stealth_sync(page)
    page.goto("http://localhost:8501", wait_until="networkidle")
    # page.wait_for_load_state("networkidle")
    # check_login_needed(browser)
    # with open("config/xero.json","r") as f:
        # config=json.load(f)
    memory=''
    with open(os.path.join(BASE_DIR, "action.txt"),'r') as f:
        memory=f.read()
    memory='<---Current Point'+memory
    while True:
        page.wait_for_load_state("networkidle")
        save_screenshot(page)
        ret=chat_with_gpt(f'memoryに記載された一連のアクションを実行したいです。ここには現在位置が記載されています。画面のスクショを見て、次に行うべきアクションを決定してください。updateされたmemoryと次のアクションをjsonで記載してください.memoryにはアクションの全体や現在位置、書き残すべきことを記載してください。例{{"memory":"<memory_content>", "nextaction":"<nextaction_content>"}}。もしアクションが終了したら一言DONEと返してください。\n{memory}',images=[get_latest_screenshot_image_path()])
        if 'DONE' in ret:
            print("All actions completed.")
            input()
            break
        ret=json.loads(ret)
        memory=ret["memory"]
        nextaction=ret["nextaction"]
        print(f"Next Action: {nextaction}")
        action_result = action(browser,purpose=nextaction)
        memory+='<---already tryed'+nextaction+f' and the result is {action_result}'
        print(f"Updated memory: {memory}")
    exit()
    

    action(browser,purpose='必要ならログインして',context=config)
    action(browser,purpose='press not now button',context=config)

    action(browser,purpose='new billのとなりの3点ドットボタンを押す',context=config)
    action(browser,purpose='push export bills button',context=config)
    action(browser,purpose='push export',context=config)
    input()

    # check login needed
    # all locators (text and button)
    # Example usage:
    # list_all_locators(page)
    
    browser.close()
# auto-naming files
# uploading files
