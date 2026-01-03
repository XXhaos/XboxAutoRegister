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
import shutil

# === 配置区域 ===
INPUT_CSV = 'E:\Downloads\outlook账号.csv'  # 原始输入文件
FINAL_FAILED_CSV = 'failed.csv'  # 最终输出的失败文件
SUCCESS_CSV = 'success.csv'  # 成功记录文件
TEMP_FAILED_CSV = 'temp_failed.csv'  # 中间过程临时文件

POWERSHELL_SCRIPT = r"E:\ClashScript\rotate.ps1"
GECKODRIVER_PATH = "geckodriver.exe"
FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"


# ================= 工具函数 =================

def rotate_ip():
    print(">>> [系统] 正在切换 IP (后台运行中)...")
    try:
        subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", POWERSHELL_SCRIPT],
            check=True,
            shell=True
        )
        print(">>> [系统] IP 切换完成，等待网络恢复...")
        time.sleep(2)
    except subprocess.CalledProcessError as e:
        print(f"!!! IP 切换失败: {e}")


def get_existing_success_accounts():
    """读取已成功的账号，用于去重"""
    if not os.path.exists(SUCCESS_CSV):
        return set()

    existing_emails = set()
    try:
        with open(SUCCESS_CSV, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if "----" in line:
                    email = line.split("----")[0].strip()
                    existing_emails.add(email)
    except:
        pass
    return existing_emails


def append_to_csv(file_path, email, password):
    """追加写入一行 CSV (实时保存)"""
    file_exists = os.path.exists(file_path)
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            if not file_exists:
                f.write("卡号\n")  # 如果文件不存在，先写表头
            f.write(f"{email}----{password}\n")
            f.flush()
    except Exception as e:
        print(f"写入文件 {file_path} 失败: {e}")


def read_accounts_from_file(file_path):
    """通用文件读取函数"""
    print(f"正在读取文件: {file_path} ...")
    account_list = []
    try:
        try:
            f = open(file_path, 'r', encoding='utf-8')
            lines = f.readlines()
        except UnicodeDecodeError:
            f = open(file_path, 'r', encoding='gb18030')
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

        return account_list

    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return []


def login_process(driver, email, password):
    """
    业务逻辑核心
    返回: True(成功) / False(失败)
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

                if "xbox.com" in current_url:
                    print(f"√√√ 直接跳转到了 Xbox 首页，成功！")
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

        clicked_yes = False
        try:
            yes_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='primaryButton']"))
            )
            yes_btn.click()
            clicked_yes = True
        except:
            pass

        if clicked_yes:
            time.sleep(3)

            # 点击 "保存并继续"
        print("   [关键] 等待 '保存并继续' 按钮 (60s)...")
        try:
            save_btn = WebDriverWait(driver, 60).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., '保存并继续')]"))
            )
            save_btn.click()
            time.sleep(3)
        except Exception as e:
            print(f"   [失败] 60秒内未找到 '保存并继续' 按钮。")
            return False

            # 检测成功标志
        print("   [关键] 等待 '可选诊断数据' 标志 (60s)...")
        try:
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(., '可选诊断数据')]"))
            )
            print(f"√√√√√√ 成功！账号 {email} 处理完毕！")
            return True

        except Exception as e:
            print(f"   [失败] 超时未检测到成功标志。")
            return False

    except Exception as e:
        print(f"!!! 发生未知异常: {e}")
        return False


def run_batch(input_file, output_fail_file, round_name="第一轮"):
    """批量执行函数"""
    print(f"\n========== 启动 {round_name} 处理 ==========")

    # 1. 读取账号
    all_accounts = read_accounts_from_file(input_file)
    if not all_accounts:
        print(f"{round_name} 没有读取到有效账号，跳过。")
        return 0

    # 2. 过滤已成功账号
    success_set = get_existing_success_accounts()
    pending_accounts = []

    for acc in all_accounts:
        if acc['email'] in success_set:
            if round_name == "第一轮":
                print(f"--- 跳过已成功账号: {acc['email']}")
        else:
            pending_accounts.append(acc)

    if not pending_accounts:
        print(f"✨ {round_name} 所有账号都已存在于 {SUCCESS_CSV} 中，无需处理。")
        return 0

    print(f"{round_name} 待处理账号: {len(pending_accounts)} 个。")

    # 创建失败文件（如果是0失败，最后会删除）
    with open(output_fail_file, 'w', encoding='utf-8') as f:
        f.write("卡号\n")

    df = pd.DataFrame(pending_accounts)
    fail_count = 0

    for index, row in df.iterrows():
        driver = None
        email = row['email']
        password = row['password']

        try:
            rotate_ip()
            print(f">>> [{round_name}] 正在启动 Firefox (无头模式) - 进度 {index + 1}/{len(pending_accounts)}: {email}")

            options = Options()
            options.binary_location = FIREFOX_BINARY_PATH
            options.add_argument("-headless")
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

            is_success = login_process(driver, email, password)

            if is_success:
                print(f"OOO [{round_name}] 账号 {email} 成功！写入 {SUCCESS_CSV}...")
                append_to_csv(SUCCESS_CSV, email, password)
            else:
                print(f"XXX [{round_name}] 账号 {email} 失败，写入临时失败记录...")
                append_to_csv(output_fail_file, email, password)
                fail_count += 1

        except Exception as e:
            print(f"!!! [{round_name}] 运行异常: {e}")
            append_to_csv(output_fail_file, email, password)
            fail_count += 1

        finally:
            if driver:
                print(">>> 关闭后台浏览器...")
                try:
                    driver.quit()
                except:
                    pass
                time.sleep(2)

    return fail_count


def main():
    if not os.path.exists(FIREFOX_BINARY_PATH):
        print(f"❌ 错误: 找不到 Firefox，请检查路径: {FIREFOX_BINARY_PATH}")
        return

    # === 第一轮：跑原始文件，输出到 temp ===
    fails_round_1 = run_batch(INPUT_CSV, TEMP_FAILED_CSV, round_name="第一轮")

    # 检查第一轮结果
    if fails_round_1 == 0:
        print("\n🎉🎉🎉 第一轮完美结束！所有账号全部成功！")

        # 清理逻辑：因为没有失败，所以不需要 failed.csv，也不需要 temp
        if os.path.exists(TEMP_FAILED_CSV): os.remove(TEMP_FAILED_CSV)
        if os.path.exists(FINAL_FAILED_CSV): os.remove(FINAL_FAILED_CSV)

        return  # 直接退出

    # === 第二轮：复活赛 ===
    print(f"\n⚠️ 第一轮结束，{fails_round_1} 个账号需要重试。")
    print("🚀 等待 3 秒开始第二轮复活赛...")
    time.sleep(3)

    # 跑临时文件，输出到最终文件
    fails_round_2 = run_batch(TEMP_FAILED_CSV, FINAL_FAILED_CSV, round_name="第二轮(复活赛)")

    # === 最终清理逻辑 ===
    print(f"\n========================================")
    print(f"所有流程结束。")
    print(f"第一轮失败: {fails_round_1}")
    print(f"第二轮救回: {fails_round_1 - fails_round_2}")
    print(f"最终失败数: {fails_round_2}")

    # 如果第二轮后失败数为 0，删除 final_failed.csv
    if fails_round_2 == 0:
        print(f"🎉 恭喜！复活赛全部成功，删除 {FINAL_FAILED_CSV}")
        if os.path.exists(FINAL_FAILED_CSV):
            os.remove(FINAL_FAILED_CSV)
    else:
        print(f"⚠️ 仍有失败账号，请查看: {FINAL_FAILED_CSV}")

    # 总是删除中间临时文件
    if os.path.exists(TEMP_FAILED_CSV):
        try:
            os.remove(TEMP_FAILED_CSV)
        except:
            pass

    print(f"========================================")


if __name__ == "__main__":
    main()