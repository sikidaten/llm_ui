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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(BASE_DIR, "work")
DOWNLOAD_DIR = BASE_DIR
API_KEY_PATH = os.path.join(BASE_DIR, "api.key")
START_URL = "http://localhost:3000"
MAX_STEPS = 50
NETWORK_IDLE_TIMEOUT_MS = 15000

import base64

MIME_TYPE_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


# Function to encode the image as a data URL (mime type follows the extension)
def encode_image(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    mime_type = MIME_TYPE_BY_EXT.get(ext, "image/jpeg")
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


from openai import OpenAI

_client = None


def get_client():
    global _client
    if _client is None:
        with open(API_KEY_PATH, "r", encoding="utf-8") as f:
            api_key = f.read().strip()
        _client = OpenAI(api_key=api_key)
    return _client


def chat_with_gpt(message: str, images=None) -> str:
    # print(f"Message: {message}")
    """
    Send a message (and optional images) to ChatGPT and get a response.
    Args:
        message: The user message to send
        images: List of local image file paths (optional)
    Returns:
        The assistant's response
    """
    client = get_client()
    # Build the input structure as in the JS example
    content = [
        {"type": "input_text", "text": message}
    ]
    for image in images or []:
        if not image:
            continue
        content.append({"type": "input_image", "image_url": encode_image(image)})
    response = client.responses.create(
        model="gpt-5.5",
        reasoning={'effort': 'none'},
        input=[
            {
                "role": "user",
                "content": content
            }
        ],
    )
    print(response.output_text)
    # time.sleep(2)
    print("========================================")
    return response.output_text


def strip_code_fences(text: str) -> str:
    """Remove a surrounding ```lang ... ``` block from an LLM response."""
    text = text.strip()
    match = re.match(r"^```[A-Za-z0-9_+-]*\s*\n?(.*?)\n?\s*```$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return re.sub(r"```[A-Za-z0-9_+-]*", "", text).strip()


def parse_llm_json(text: str):
    """Parse a JSON object out of an LLM response, or return None."""
    cleaned = strip_code_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def get_work_file_path(filename):
    ensure_dir(WORK_DIR)
    return os.path.join(WORK_DIR, filename)


def wait_for_idle(page, timeout=NETWORK_IDLE_TIMEOUT_MS):
    """Wait for network idle without letting a timeout abort the run."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception as e:
        print(f"[warn] networkidle wait did not settle: {e}")


def get_active_page(browser):
    """Return the newest page that is still open (clicks may spawn new tabs)."""
    for context in browser.contexts:
        for page in reversed(context.pages):
            if not page.is_closed():
                return page
    return None


def save_screenshot(page):
    timestamp = datetime.datetime.now().strftime("%d%H%M%S%f")
    screenshot_path = get_work_file_path(f"{timestamp}screenshot.png")
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


_saved_downloads = {}


def save_download(download):
    # The context-level "download" listener and the generated code both call this
    # for the same download, so remember what was already written to disk.
    if download in _saved_downloads:
        return _saved_downloads[download]
    ensure_dir(DOWNLOAD_DIR)
    filename = download.suggested_filename or "downloaded_file"
    target_path = os.path.join(DOWNLOAD_DIR, filename)
    base, ext = os.path.splitext(target_path)
    suffix = 1
    while os.path.exists(target_path):
        target_path = f"{base}_{suffix}{ext}"
        suffix += 1
    download.save_as(target_path)
    _saved_downloads[download] = target_path
    print(f"Downloaded file saved to {target_path}")
    return target_path


def get_latest_screenshot_image_path():
    import glob

    ensure_dir(WORK_DIR)
    list_of_files = glob.glob(os.path.join(WORK_DIR, "*.png"))
    if not list_of_files:
        return None
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def get_current_script_source():
    with open(__file__, "r", encoding="utf-8") as f:
        return f.read()


def action(browser, purpose):
    page = get_active_page(browser)
    if page is None:
        return "Error: no open page available"
    exec_output = ""
    wait_for_idle(page)
    html = page.content()
    script_source = get_current_script_source()
    with open(get_work_file_path("page.html"), "w", encoding="utf-8") as f:
        f.write(html)
    screenshot_path = save_screenshot(page)
    # exit()
    ret = chat_with_gpt(
        f"WEBのスクリーンショットとHTMLが与えられます。\n目的:{purpose}、\nこの目的を実行したいです。実行すべき最低限必要な処理だけを記載してください。実行すべきPlaywrightのコードをPYTHONで生成してください:生成されたコードはexecで実実行されます。コードは最低限でいいです。現在Playwrightを実行中でページを開いていて、新たに起動する必要はありません。page変数は定義されています。awaitもつけないでください。各アクションの後は固定待機を使わず、必要ならpage.wait_for_load_state(\"networkidle\")を使ってください。Fillするときは適度にDelayしてください。ただしError occurred while executing generated code: Locator.fill() got an unexpected keyword argument 'delay'に注意してください。ダウンロードやエクスポートの操作なら必ずwith page.expect_download() as download_info: を使ってクリックし、その後 download = download_info.value として save_download(download) を呼んでください。ダウンロード結果は result = save_download(download) のように result に代入してください。テキスト取得など確認結果がある場合も result に文字列を入れてください。アクションが成功したか失敗したかメッセージでわかるようにしてください。画像を読み取って解析が必要な場合は、chat_with_gptを用いることがおすすめです。ただし呼び出し回数が増えないように、複数の画像や項目をまとめてよみとるなど回数を減らす工夫をしてください。この実行ファイルのコードを参考にしてください。\n{script_source=}\n\n\n\n\nこれはこのページのHTMLです。コード生成の参考にしてください。入力時はその項目が見えるようにスクロールしてから入力してください。:\n{html}",
        images=[screenshot_path]
    )
    print(ret)
    ret = strip_code_fences(ret)
    try:
        stdout_buffer = io.StringIO()
        # Single namespace: exec() with separate globals/locals breaks generated
        # code that defines helper functions or comprehensions using `page`.
        exec_namespace = dict(globals())
        exec_namespace.update({"page": page, "browser": browser, "result": ""})
        with contextlib.redirect_stdout(stdout_buffer):
            exec(ret, exec_namespace)
        exec_output = exec_namespace.get("result") or stdout_buffer.getvalue().strip()
    except Exception as e:
        exec_output = f"Error occurred while executing generated code: {e}"
        print(exec_output)
    page = get_active_page(browser) or page
    wait_for_idle(page)
    save_screenshot(page)
    return exec_output


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
    page.goto(START_URL, wait_until="networkidle")
    # check_login_needed(browser)
    memory = ''
    with open(os.path.join(BASE_DIR, "action.txt"), 'r', encoding="utf-8") as f:
        memory = f.read()
    memory = '<---Current Point\n' + memory
    for step in range(MAX_STEPS):
        page = get_active_page(browser) or page
        wait_for_idle(page)
        screenshot_path = save_screenshot(page)
        ret = chat_with_gpt(f'memoryに記載された一連のアクションを実行したいです。ここには現在位置が記載されています。画面のスクショを見て、次に行うべきアクションを決定してください。updateされたmemoryと次のアクションをjsonで記載してください.memoryにはアクションの全体や現在位置、書き残すべきことを記載してください。例{{"memory":"<memory_content>", "nextaction":"<nextaction_content>"}}。もしアクションが終了したら一言DONEと返してください。1ステップごとにコストがかかるので、同じ画面での複数項目の入力などはまとめてください\n{memory}', images=[screenshot_path])
        # Parse first: a JSON payload whose memory mentions "DONE" is not a stop signal.
        parsed = parse_llm_json(ret)
        if parsed is None:
            if 'DONE' in ret:
                print("All actions completed.")
                break
            print(f"[warn] could not parse response as JSON, retrying:\n{ret}")
            memory += '\n<---前回の応答がJSONとして解釈できませんでした。必ずJSONだけを返してください。'
            continue
        memory = parsed["memory"]
        nextaction = parsed["nextaction"]
        print(f"Next Action: {nextaction}")
        action_result = action(browser, purpose=nextaction)
        memory += '<---already tryed' + nextaction + f' and the result is {action_result}'
        print(f"Updated memory: {memory}")
    else:
        print(f"Stopped after reaching the {MAX_STEPS} step limit.")

    with contextlib.suppress(EOFError, KeyboardInterrupt):
        input("Press Enter to close the browser...")
    browser.close()
# auto-naming files
# uploading files
