import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / '.env'
ENV_EXAMPLE = BASE_DIR / '.env.example'

if not ENV_FILE.exists():
    if ENV_EXAMPLE.exists():
        import shutil
        shutil.copy(str(ENV_EXAMPLE), str(ENV_FILE))
        print("=" * 50)
        print("  [!] 检测到首次运行，已自动生成 .env 配置文件")
        print("  [!] 请用记事本打开 .env 文件")
        print("  [!] 在等号后面填入你的企业微信 Webhook 地址")
        print("  [!] 完成后重新运行本程序")
        print("=" * 50)
        os.system(f'start notepad "{ENV_FILE}"')
        sys.exit(0)
    else:
        print("=" * 50)
        print("  [错误] 找不到配置文件模板")
        print("  请从 GitHub 重新下载完整项目")
        print("=" * 50)
        sys.exit(1)

from system.sync_engine import main

if __name__ == "__main__":
    main()
