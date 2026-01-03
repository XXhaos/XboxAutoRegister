from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import time
import os

# === 配置区域 ===
INPUT_CSV = r'input\outlook账号_part_6.csv'  # 原始输入文件
TEMP_RETRY_CSV = r'output\temp_retry.csv'  # 第一轮失败存放处（复活赛的输入）
FINAL_FAILED_CSV = r'output\failed.csv'  # 最终失败文件
SUCCESS_CSV = r'output\success.csv'  # 成功文件

POWERSHELL_SCRIPT = r"E:\ClashScript\rotate.ps1"
GECKODRIVER_PATH = "geckodriver.exe"
FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"


# ================= 工具函数 =================

def rotate_ip():
    """切换IP"""
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


def append_to_csv(file_path, email, password):
    """追加写入一行 CSV"""
    file_exists = os.path.exists(file_path)
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            if not file_exists:
                f.write("卡号\n")
            f.write(f"{email}----{password}\n")
            f.flush()
    except Exception as e:
        print(f"写入文件 {file_path} 失败: {e}")


def read_file_lines(file_path):
    """读取文件所有行"""
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='gb18030') as f:
                return f.readlines()
        except:
            return []


def rewrite_source_file(file_path, lines):
    """重写源文件（用于删除行）"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        print(f"!!! 更新源文件失败: {e}")


def parse_account(line):
    """解析账号密码"""
    line = line.strip()
    if not line or "卡号" in line:
        return None, None

    email = ""
    pwd = ""
    # 支持 ---- 分割
    if "----" in line:
        parts = line.split("----")
        email = parts[0].strip()
        if len(parts) > 1:
            pwd = parts[1].strip()
    # 支持 , 分割
    elif "," in line:
        parts = line.split(",")
        email = parts[0].strip()
        if len(parts) > 1:
            pwd = parts[1].strip()

    if email and pwd:
        return email, pwd
    return None, None


def count_valid_accounts(file_path):
    """统计有效账号数"""
    lines = read_file_lines(file_path)
    count = 0
    for line in lines:
        e, _ = parse_account(line)
        if e:
            count += 1
    return count


def login_process(driver, email, password):
    """
    业务逻辑：登录 Xbox
    返回: True(成功) / False(失败)
    """
    print(f"=== 开始处理: {email} ===")

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
                print(">>> URL 检测超时 (60s)，强制下一步")
                break

            try:
                current_url = driver.current_url

                if "xbox.com" in current_url:
                    print(f"√√√ 直接跳转到了 Xbox 首页，成功！")
                    return True

                if "account.live.com" in current_url or "login.live.com" in current_url:
                    try:
                        # 处理跳过按钮
                        skip_btns = driver.find_elements(By.ID, "iShowSkip")
                        if skip_btns and skip_btns[0].is_displayed():
                            print(">>> 点击 '跳过'...")
                            skip_btns[0].click()
                            time.sleep(2)
                            continue

                        # 处理常规确认按钮
                        primary_btns = driver.find_elements(By.XPATH, "//button[@data-testid='primaryButton']")
                        if primary_btns and primary_btns[0].is_displayed():
                            print(f">>> 检测到主按钮，点击确认...")
                            break
                    except:
                        pass
                    time.sleep(1)
                else:
                    break
            except:
                break

        # === 4. 后续确认流程 ===
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
        print("   [关键] 等待 '保存并继续' (60s)...")
        try:
            save_btn = WebDriverWait(driver, 60).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., '保存并继续')]"))
            )
            save_btn.click()
            time.sleep(3)
        except:
            print(f"   [失败] 未找到 '保存并继续'")
            return False

        # 检测成功标志
        print("   [关键] 等待 '可选诊断数据' (60s)...")
        try:
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(., '可选诊断数据')]"))
            )
            print(f"√√√√√√ 成功！账号 {email} 处理完毕！")
            return True

        except:
            print(f"   [失败] 未检测到成功标志")
            return False

    except Exception as e:
        print(f"!!! 发生未知异常: {e}")
        return False


def run_process_loop(source_file, success_output, fail_output, round_name):
    """
    通用处理循环：
    1. 读取 source_file
    2. 处理一个 -> 删一个
    3. 成功 -> success_output
    4. 失败 -> fail_output
    """
    print(f"\n========== 启动 {round_name} ==========")
    print(f"输入: {source_file}")
    print(f"失败将存入: {fail_output}")

    # 1. 统计总数
    total_count = count_valid_accounts(source_file)
    if total_count == 0:
        print(f"✨ {round_name} 无待处理账号，跳过。")
        return 0

    print(f"📊 {round_name} 待处理任务数: {total_count}")

    processed_count = 0
    fail_count = 0

    while True:
        # 2. 读取文件寻找下一个
        all_lines = read_file_lines(source_file)

        target_line_index = -1
        email = None
        password = None

        for i, line in enumerate(all_lines):
            e, p = parse_account(line)
            if e and p:
                target_line_index = i
                email = e
                password = p
                break

        # 3. 如果找不到，说明本轮结束
        if target_line_index == -1:
            print(f"\n🎉 {round_name} 结束！(进度: {processed_count}/{total_count})")
            break

        processed_count += 1
        print(f"\n--------------------------------------------------")
        print(f"🚀 [{round_name}] 进度: {processed_count}/{total_count} | 账号: {email}")
        print(f"--------------------------------------------------")

        driver = None
        try:
            rotate_ip()  # 换IP

            # 启动浏览器
            options = Options()
            options.binary_location = FIREFOX_BINARY_PATH
            options.add_argument("-headless")  # 无头模式
            options.add_argument("--width=1920")
            options.add_argument("--height=1080")
            options.set_preference("general.useragent.override",
                                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0")
            options.add_argument("-private")

            # 性能优化参数
            options.set_preference("security.webauth.webauthn", False)
            options.set_preference("security.webauth.u2f", False)
            options.set_preference("signon.rememberSignons", False)

            service = Service(GECKODRIVER_PATH)
            driver = webdriver.Firefox(service=service, options=options)

            # 执行
            is_success = login_process(driver, email, password)

            # 结果分流
            if is_success:
                print(f"OOO 成功 -> 写入 {success_output}")
                append_to_csv(success_output, email, password)
            else:
                print(f"XXX 失败 -> 写入 {fail_output}")
                append_to_csv(fail_output, email, password)
                fail_count += 1

        except Exception as e:
            print(f"!!! 运行异常: {e}")
            append_to_csv(fail_output, email, password)
            fail_count += 1

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

            # 4. 【核心】从源文件移除该行（即时保存进度）
            if target_line_index != -1 and target_line_index < len(all_lines):
                check_e, _ = parse_account(all_lines[target_line_index])
                if check_e == email:
                    del all_lines[target_line_index]
                    rewrite_source_file(source_file, all_lines)

            time.sleep(2)

    # 循环结束，尝试删除源文件（如果已空）
    final_lines = read_file_lines(source_file)
    has_valid = any(parse_account(x)[0] for x in final_lines)
    if not has_valid:
        print(f"🗑️ {source_file} 已处理完毕，删除文件。")
        try:
            os.remove(source_file)
        except:
            pass

    return fail_count


def main():
    if not os.path.exists(FIREFOX_BINARY_PATH):
        print(f"❌ 错误: 找不到 Firefox，请检查路径: {FIREFOX_BINARY_PATH}")
        return

    # === 第一轮：初赛 ===
    # 输入: outlook账号.csv
    # 失败去向: temp_retry.csv (临时复活池)
    fail_round_1 = run_process_loop(INPUT_CSV, SUCCESS_CSV, TEMP_RETRY_CSV, "第一轮(初赛)")

    if fail_round_1 == 0:
        print("\n🎉🎉🎉 第一轮全胜！无需复活赛。")
        if os.path.exists(TEMP_RETRY_CSV): os.remove(TEMP_RETRY_CSV)
        return

    # === 第二轮：复活赛 ===
    print(f"\n⚠️ 第一轮产生了 {fail_round_1} 个失败账号，准备进入复活赛...")
    print("⏳ 等待 5 秒...")
    time.sleep(5)

    # 输入: temp_retry.csv (第一轮的失败者)
    # 失败去向: failed.csv (最终失败记录)
    fail_round_2 = run_process_loop(TEMP_RETRY_CSV, SUCCESS_CSV, FINAL_FAILED_CSV, "第二轮(复活赛)")

    print(f"\n================ 最终统计 ================")
    print(f"第一轮失败: {fail_round_1}")
    print(f"第二轮救回: {fail_round_1 - fail_round_2}")
    print(f"最终失败数: {fail_round_2}")

    if fail_round_2 == 0:
        print("🎉 复活赛全部成功！")
        if os.path.exists(FINAL_FAILED_CSV): os.remove(FINAL_FAILED_CSV)
    else:
        print(f"😭 仍有账号失败，请查看: {FINAL_FAILED_CSV}")


if __name__ == "__main__":
    main()