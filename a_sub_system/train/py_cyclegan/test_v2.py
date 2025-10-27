import os


def print_tree(output_file, exclude_dirs):
    def generate_tree(startpath):
        tree_str = ""
        for root, dirs, files in os.walk(startpath):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            level = root.replace(startpath, '').count(os.sep)
            indent = '│   ' * (level - 1) + '├── ' if level > 0 else ''
            tree_str += f'{indent}{os.path.basename(root)}/\n'

            subindent = '│   ' * level + '├── '
            for f in files:
                tree_str += f'{subindent}{f}\n'
        return tree_str

    return generate_tree('.')


def serialize_files(output_file=""):

    exclude_dirs = {'.venv', '.idea', '.git','__pycache__','.pytest_cache','temp','scripts'}
    exclude_content = {'.md',".db",".rds"}


    if not output_file:
        # output_file = "all_files.md"
        root_dir = os.path.basename(os.path.abspath('.'))
        output_file = f"{root_dir}---all_files.md"

    with open(output_file, 'w', encoding='utf-8') as f:
        # 首先寫入目錄樹結構
        f.write("# ")
        f.write(output_file)
        f.write("\n")
        f.write("# 目錄結構\n```\n")
        f.write(print_tree(output_file, exclude_dirs))
        f.write("```\n---\n")

        # 接著寫入檔案內容
        for root, dirs, files in os.walk('.', topdown=True):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file == output_file:
                    continue

                file_path = os.path.join(root, file)[2:]
                file_ext = os.path.splitext(file)[1]

                f.write(f"\n{file_path}:\n")
                if file_ext not in exclude_content:
                    try:
                        # 嘗試不同的編碼方式
                        encodings = ['utf-8', 'utf-16', 'big5', 'cp950', 'gb18030']
                        content = None

                        for encoding in encodings:
                            try:
                                with open(os.path.join(root, file), 'r', encoding=encoding) as content_file:
                                    content = content_file.read()
                                break
                            except UnicodeDecodeError:
                                continue

                        if content is None:
                            # 如果所有編碼都失敗，使用二進制模式讀取
                            with open(os.path.join(root, file), 'rb') as content_file:
                                content = content_file.read().decode('utf-8', errors='replace')

                        f.write("```\n")
                        f.write(content)
                        f.write("\n```\n")
                    except Exception as e:
                        print(f"無法讀取檔案 {file_path}: {str(e)}")

                else:
                    f.write("```\n[內容已忽略]\n```\n")
                f.write("---\n")


if __name__ == "__main__":
    serialize_files()