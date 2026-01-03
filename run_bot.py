from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import time
import pandas as pd
import os

# === 配置区域 ===
CSV_FILE = 'E:\Downloads\outlook账号.csv'
POWERSHELL_SCRIPT = r"E:\ClashScript\rotate.ps1"
GECKODRIVER_PATH = "geckodriver.exe"
FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"


def rotate_ip():
    print(">>> 正在切换 IP...")
    try:
        subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", POWERSHELL_SCRIPT],
            check=True,
            shell=True
        )
        print(">>> IP 切换完成，等待网络恢复...")
        time.sleep(2)
    except subprocess.CalledProcessError as e:
        print(f"!!! IP 切换失败: {e}")


def login_process(driver, email, password):
    print(f"=== 开始处理账号: {email} ===")

    # 登录页
    driver.get("https://www.xbox.com/en-us/auth/msa?action=logIn")

    # 1. 输入账号
    try:
        WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "usernameEntry"))
        ).send_keys(email)
    except:
        pass

    time.sleep(1)
    try:
        driver.find_element(By.XPATH, "//button[@data-testid='primaryButton']").click()
    except:
        pass

    # 2. 输入密码
    WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.NAME, "passwd"))
    ).send_keys(password.strip())

    time.sleep(1.5)
    driver.find_element(By.XPATH, "//button[@data-testid='primaryButton']").click()

    # === 3. URL检测循环 ===
    print(">>> 进入 URL 监控模式...")
    loop_start_time = time.time()

    while True:
        if time.time() - loop_start_time > 60:
            print(">>> URL 检测超时 (60s)，强制进入下一步")
            break

        try:
            current_url = driver.current_url

            # 如果直接到了首页，这里先不返回成功，因为我们要严格检查诊断数据标志
            # 但如果直接跳过了诊断数据页到了首页，也需要处理（看你的需求，如果是必须出诊断页，那这里就不return）

            if "account.live.com" in current_url or "login.live.com" in current_url:
                try:
                    # 优先点跳过
                    skip_btns = driver.find_elements(By.ID, "iShowSkip")
                    if skip_btns and skip_btns[0].is_displayed():
                        print(">>> 检测到 '跳过' 按钮，点击...")
                        skip_btns[0].click()
                        time.sleep(2)
                        continue

                        # 看到主按钮，说明到了确认页，跳出循环
                    primary_btns = driver.find_elements(By.XPATH, "//button[@data-testid='primaryButton']")
                    if primary_btns and primary_btns[0].is_displayed():
                        print(f">>> 检测到主按钮，跳出循环进入确认流程...")
                        break

                except Exception as e:
                    pass
                time.sleep(1)
            else:
                print(f">>> URL 已变更 ({current_url})，跳出循环...")
                break

        except Exception as e:
            print(f"循环检测出错: {e}")
            break

    # === 4. 后续确认流程 (严格执行) ===
    print(">>> 正在执行确认流程 (必须步骤)...")

    # --- 步骤 1: 点击 "是否保持登录" ---
    clicked_yes = False
    try:
        yes_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='primaryButton']"))
        )
        print("1. 点击 '是否保持登录' (是)...")
        yes_btn.click()
        clicked_yes = True
    except:
        print("1. [警告] 未找到 '是否保持登录' 按钮，尝试继续...")

    if clicked_yes:
        print("   -> 等待页面加载 (3秒)...")
        time.sleep(3)

        # --- 步骤 2: 点击 "保存并继续" (必选！死等！) ---
    print("2. [必须步骤] 等待 '保存并继续' 按钮 (60秒超时)...")
    try:
        save_btn = WebDriverWait(driver, 60).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., '保存并继续')]"))
        )
        print("   -> 找到了！点击 '保存并继续'...")
        save_btn.click()
        time.sleep(3)  # 点击后等待
    except Exception as e:
        print(f"   [!!!失败!!!] 未找到 '保存并继续' 按钮。账号 {email} 处理失败。")
        return  # 这一步没过，直接算失败，结束当前账号

    # --- 步骤 3: 检测成功标志 (必选！死等！) ---
    print("3. [必须步骤] 等待 '可选诊断数据' 成功标志 (60秒超时)...")
    try:
        # 这里使用 60秒 超长等待，必须等到它出现
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.XPATH, "//h1[contains(., '可选诊断数据')]"))
        )
        # 只有运行到这里，才算成功
        print(f"√√√√√√ 成功！检测到 '可选诊断数据'。账号 {email} 完美完成！")

    except Exception as e:
        print(f"   [!!!失败!!!] 等待60秒仍未出现 '可选诊断数据' 标志。")
        print(f"   当前 URL: {driver.current_url}")
        print(f"   账号 {email} 判定为失败。")


def main():
    if not os.path.exists(FIREFOX_BINARY_PATH):
        print(f"❌ 错误: 找不到 Firefox，请检查路径: {FIREFOX_BINARY_PATH}")
        return

    print(f"正在读取文件: {CSV_FILE} ...")
    account_list = []
    try:
        try:
            f = open(CSV_FILE, 'r', encoding='utf-8')
            lines = f.readlines()
        except UnicodeDecodeError:
            f = open(CSV_FILE, 'r', encoding='gb18030')
            lines = f.readlines()
        finally:
            if 'f' in locals(): f.close()

        for line in lines:
            line = line.strip()
            if not line or "卡号" in line:
                continue

            email = ""
            pwd = ""
            if "----" in line:
                parts = line.split("----")
                email = parts[0].strip()
                if len(parts) > 1:
                    pwd = parts[1].strip()
            elif "," in line:
                parts = line.split(",")
                email = parts[0].strip()
                if len(parts) > 1:
                    pwd = parts[1].strip()

            if email and pwd:
                account_list.append({'email': email, 'password': pwd})

        print(f"成功加载 {len(account_list)} 个账号")

    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return

    # 定义 DataFrame
    df = pd.DataFrame(account_list)

    for index, row in df.iterrows():
        driver = None
        try:
            rotate_ip()
            print(f">>> 正在启动 Firefox (隐私模式) - 第 {index + 1} 个账号...")

            options = Options()
            options.binary_location = FIREFOX_BINARY_PATH
            options.add_argument("-private")

            options.set_preference("security.webauth.webauthn", False)
            options.set_preference("security.webauth.u2f", False)
            options.set_preference("security.webauth.webauthn_enable_softtoken", False)
            options.set_preference("security.webauth.webauthn_enable_usbtoken", False)
            options.set_preference("signon.rememberSignons", False)
            options.set_preference("dom.webnotifications.enabled", False)

            service = Service(GECKODRIVER_PATH)
            driver = webdriver.Firefox(service=service, options=options)

            login_process(driver, row['email'], row['password'])

        except Exception as e:
            print(f"!!! 账号 {row.get('email', '未知')} 发生错误: {e}")

        finally:
            if driver:
                print(">>> 关闭当前浏览器...")
                try:
                    driver.quit()
                except:
                    pass
                time.sleep(2)


if __name__ == "__main__":
    main()