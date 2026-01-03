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
CSV_FILE = 'E:\Downloads\outlook账号.csv'  # 输入文件
FAILED_CSV = 'failed.csv'  # 输出失败文件
POWERSHELL_SCRIPT = r"E:\ClashScript\rotate.ps1"
GECKODRIVER_PATH = "geckodriver.exe"
FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"


def rotate_ip():
    print(">>> 正在切换 IP (后台运行中)...")
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
    """
    返回 True 表示成功，返回 False 表示失败
    """
    print(f"=== 开始处理账号: {email} ===")

    try:
        driver.get("https://www.xbox.com/en-us/auth/msa?action=logIn")

        # 1. 输入账号
        try:
            WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((By.ID, "usernameEntry"))
            ).send_keys(email)
        except:
            pass  # 可能已经在密码页

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

                # 如果直接跳到了首页，视为成功
                if "xbox.com" in current_url:
                    print(f"√√√ 直接跳转到了 Xbox 首页，账号 {email} 成功！")
                    return True

                if "account.live.com" in current_url or "login.live.com" in current_url:
                    try:
                        skip_btns = driver.find_elements(By.ID, "iShowSkip")
                        if skip_btns and skip_btns[0].is_displayed():
                            print(">>> 检测到 '跳过' 按钮，点击...")
                            skip_btns[0].click()
                            time.sleep(2)
                            continue

                        primary_btns = driver.find_elements(By.XPATH, "//button[@data-testid='primaryButton']")
                        if primary_btns and primary_btns[0].is_displayed():
                            print(f">>> 检测到主按钮，跳出循环进入确认流程...")
                            break

                    except:
                        pass
                    time.sleep(1)
                else:
                    break

            except:
                break

        # === 4. 后续确认流程 ===
        print(">>> 正在执行确认流程...")

        # 点击 "是否保持登录"
        clicked_yes = False
        try:
            yes_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='primaryButton']"))
            )
            yes_btn.click()
            clicked_yes = True
        except:
            print("   [提示] 未找到 '是否保持登录' (可能跳过)")

        if clicked_yes:
            time.sleep(3)

            # 点击 "保存并继续" (必选)
        print("   [关键] 等待 '保存并继续' 按钮 (60s)...")
        try:
            save_btn = WebDriverWait(driver, 60).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., '保存并继续')]"))
            )
            save_btn.click()
            time.sleep(3)
        except Exception as e:
            print(f"   [失败] 未找到 '保存并继续' 按钮。")
            return False  # 必须返回失败

        # 检测成功标志 (必选)
        print("   [关键] 等待 '可选诊断数据' 标志 (60s)...")
        try:
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(., '可选诊断数据')]"))
            )
            print(f"√√√√√√ 成功！账号 {email} 处理完毕！")
            return True  # 成功！

        except Exception as e:
            print(f"   [失败] 超时未检测到成功标志。")
            return False  # 失败

    except Exception as e:
        print(f"!!! 发生未知异常: {e}")
        return False


def main():
    if not os.path.exists(FIREFOX_BINARY_PATH):
        print(f"❌ 错误: 找不到 Firefox，请检查路径: {FIREFOX_BINARY_PATH}")
        return

    # === 1. 初始化 failed.csv ===
    print(f"初始化失败记录文件: {FAILED_CSV} ...")
    with open(FAILED_CSV, 'w', encoding='utf-8') as f:
        f.write("卡号\n")  # 写入第一行表头

    # === 2. 读取输入文件 ===
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

    df = pd.DataFrame(account_list)

    # === 3. 开始循环处理 ===
    for index, row in df.iterrows():
        driver = None
        current_email = row['email']
        current_password = row['password']

        try:
            rotate_ip()
            print(f">>> 正在启动 Firefox (无头模式) - 第 {index + 1} 个账号: {current_email} ...")

            options = Options()
            options.binary_location = FIREFOX_BINARY_PATH
            options.add_argument("-headless")  # 启用无头模式
            options.add_argument("--width=1920")
            options.add_argument("--height=1080")
            options.set_preference("general.useragent.override",
                                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0")
            options.add_argument("-private")

            options.set_preference("security.webauth.webauthn", False)
            options.set_preference("security.webauth.u2f", False)
            options.set_preference("security.webauth.webauthn_enable_softtoken", False)
            options.set_preference("security.webauth.webauthn_enable_usbtoken", False)
            options.set_preference("signon.rememberSignons", False)
            options.set_preference("dom.webnotifications.enabled", False)

            service = Service(GECKODRIVER_PATH)
            driver = webdriver.Firefox(service=service, options=options)

            # 执行登录，获取结果
            is_success = login_process(driver, current_email, current_password)

            if not is_success:
                print(f"XXX 账号 {current_email} 处理失败，写入 {FAILED_CSV} ...")
                # 写入失败文件
                with open(FAILED_CSV, 'a', encoding='utf-8') as f:
                    f.write(f"{current_email}----{current_password}\n")
            else:
                print(f"OOO 账号 {current_email} 处理成功！")

        except Exception as e:
            print(f"!!! 运行异常: {e}")
            # 异常也算失败，写入文件
            with open(FAILED_CSV, 'a', encoding='utf-8') as f:
                f.write(f"{current_email}----{current_password}\n")

        finally:
            if driver:
                print(">>> 关闭后台浏览器...")
                try:
                    driver.quit()
                except:
                    pass
                time.sleep(2)


if __name__ == "__main__":
    main()