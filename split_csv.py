import os
import shutil


def split_to_input_folder(input_file, rows_per_file=15):
    """
    将原始 CSV 切分并存入 ./input/ 文件夹，完成后删除原文件
    """
    target_dir = "input"

    # 1. 检查源文件
    if not os.path.exists(input_file):
        print(f"❌ 错误：找不到源文件 '{input_file}'")
        return

    # 2. 创建 input 文件夹（如果不存在）
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"📁 已创建目录: {target_dir}")

    # 3. 读取内容
    try:
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(input_file, 'r', encoding='gb18030') as f:
                lines = f.readlines()
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return

    if len(lines) < 2:
        print("⚠️ 文件中没有足够的账号数据。")
        return

    # 提取表头和数据行
    header = lines[0]
    data_lines = [l for l in lines[1:] if l.strip()]
    total_accounts = len(data_lines)

    print(f"📂 发现 {total_accounts} 个账号，准备切分...")

    # 4. 开始切分并写入 input 文件夹
    file_count = 0
    success_count = 0

    for i in range(0, total_accounts, rows_per_file):
        file_count += 1
        chunk = data_lines[i: i + rows_per_file]

        # 生成输出路径，例如: input/outlook账号_part_1.csv
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_filename = f"{base_name}_part_{file_count}.csv"
        output_path = os.path.join(target_dir, output_filename)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(header)
                f.writelines(chunk)
            success_count += 1
            print(f"✅ 已存入: {output_path} ({len(chunk)} 个账号)")
        except Exception as e:
            print(f"❌ 写入 {output_path} 失败: {e}")
            return  # 安全起见，失败则不删除原文件

    # 5. 彻底删除原大文件
    if success_count > 0:
        try:
            os.remove(input_file)
            print(f"\n🚀 分割完成！共生成 {success_count} 个文件并存入 '{target_dir}' 文件夹。")
            print(f"🗑️ 原始文件 '{input_file}' 已删除。")
        except Exception as e:
            print(f"\n⚠️ 子文件已生成，但删除原文件失败: {e}")


if __name__ == "__main__":
    split_to_input_folder('outlook账号.csv', rows_per_file=15)