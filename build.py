"""
一键打包脚本

使用方法：
    python build.py                  # 默认打包 GUI 版本
    python build.py --gui            # 同上（默认就是 GUI）
    python build.py --cli            # 打包 CLI 版本（无 GUI 依赖，更小）
    python build.py --clean --gui    # 清理后重新打包 GUI 版
    python build.py --onefile        # 单文件模式（启动慢 5-10s）

Windows 上的常见问题：
- PermissionError [WinError 5] 通常是之前打包的 exe 还在跑
- 脚本会自动 kill 相关进程、清理、等待
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent


def kill_running_exe():
    """杀掉之前打包的 exe（避免文件锁）"""
    if sys.platform != "win32":
        return
    
    exe_names = ["GameOpsMonitor.exe", "GameOpsMonitor-CLI.exe"]
    killed = False
    for name in exe_names:
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", name],
                capture_output=True, text=True, timeout=5
            )
            if "成功" in result.stdout or "SUCCESS" in result.stdout:
                print(f"  ✓ 已结束 {name}")
                killed = True
        except Exception as e:
            pass
    
    if not killed:
        print(f"  ⚪ 没有运行中的 GameOpsMonitor 进程")


def wait_for_files_unlock(path: Path, max_wait: int = 60) -> bool:
    """等待文件解锁（杀软扫描中），最长 60s"""
    if not path.exists():
        return True

    start = time.time()
    last_print = 0
    while time.time() - start < max_wait:
        try:
            test_file = path / "_test_unlock.tmp"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except PermissionError:
            elapsed = int(time.time() - start)
            if elapsed - last_print >= 5:
                print(f"  ⏳ 还在等文件解锁... ({elapsed}s / {max_wait}s)")
                last_print = elapsed
            time.sleep(1)
    return False


def find_what_locks(path: Path) -> list[str]:
    """找出占用文件锁的进程名（Windows）"""
    if sys.platform != "win32":
        return []
    try:
        ps_cmd = (
            f'Get-Process | Where-Object {{$_.Modules.FileName -like "*{path.name}*"}} '
            f'| Select-Object -ExpandProperty ProcessName'
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10,
        )
        procs = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        return procs
    except Exception:
        return []


def force_remove_with_powershell(path: Path) -> bool:
    """用 PowerShell Remove-Item -Force 强删"""
    if not path.exists():
        return True
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f'Remove-Item -Path "{path}" -Recurse -Force -ErrorAction SilentlyContinue; '
             f'if (Test-Path "{path}") {{ exit 1 }} else {{ exit 0 }}'],
            capture_output=True, timeout=30,
        )
        return result.returncode == 0 and not path.exists()
    except Exception as e:
        print(f"  PowerShell 强删失败: {e}")
        return False


def force_remove_with_cmd(path: Path) -> bool:
    """用 cmd 的 rd /s /q 强删（最后兜底）"""
    if not path.exists():
        return True
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["cmd", "/c", "rd", "/s", "/q", str(path)],
            capture_output=True, timeout=30,
        )
        return result.returncode == 0 and not path.exists()
    except Exception as e:
        print(f"  cmd rd 强删失败: {e}")
        return False


def find_what_locks(path: Path) -> list[str]:
    """找出占用文件锁的进程名（Windows）"""
    if sys.platform != "win32":
        return []
    
    try:
        # 用 PowerShell 找占用进程
        ps_cmd = f'Get-Process | Where-Object {{$_.Modules.FileName -like "*{path.name}*"}} | Select-Object -ExpandProperty ProcessName'
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10,
        )
        procs = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        return procs
    except Exception:
        return []


def clean(force: bool = True):
    """清理构建产物（Windows 友好版：杀掉进程 + 等解锁 + PowerShell 强删 + cmd 兜底）"""
    print("🧹 清理构建产物...")

    # 1. 先杀进程
    kill_running_exe()

    # 2. 删除 build/ 和 dist/（多轮重试）
    for d in ['build', 'dist']:
        path = ROOT / d
        if not path.exists():
            continue

        deleted = False
        # 第 1 轮：直接删
        try:
            shutil.rmtree(path)
            print(f"  ✓ 删除 {d}/")
            deleted = True
        except PermissionError:
            # 第 2 轮：等解锁
            print(f"  ⚠️  {d}/ 锁住，等解锁（最多 60s）...")
            if wait_for_files_unlock(path, max_wait=60):
                try:
                    shutil.rmtree(path)
                    print(f"  ✓ {d}/ 解锁后已清理")
                    deleted = True
                except Exception as e:
                    print(f"  ❌ 解锁后 Python rmtree 仍失败: {e}")

        if not deleted:
            # 第 3 轮：找占用进程 + 强杀
            print(f"  🔍 查找占用进程...")
            procs = find_what_locks(path)
            if procs:
                print(f"  锁文件被这些进程占用: {procs}")
                print(f"  尝试结束它们...")
                for proc_name in procs:
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/IM", f"{proc_name}.exe"],
                            capture_output=True, timeout=5,
                        )
                    except Exception:
                        pass
                time.sleep(3)
            else:
                print(f"  ⚠️  没找到具体进程（杀软静默扫描中）")

            # 第 4 轮：PowerShell 强删
            print(f"  💪 尝试 PowerShell 强删...")
            if force_remove_with_powershell(path):
                print(f"  ✓ PowerShell 强删成功")
                deleted = True
            else:
                # 第 5 轮：cmd rd /s /q 兜底
                print(f"  💪 尝试 cmd rd /s /q 兜底...")
                if force_remove_with_cmd(path):
                    print(f"  ✓ cmd 强删成功")
                    deleted = True
                else:
                    print(f"  ❌ 所有方法都失败")

        if not deleted:
            print()
            print(f"  ⚠️  {d}/ 未能清理，PyInstaller 会自己再试")
            print()
            print(f"  💡 如果还是失败，最后手段：")
            print(f"     1. 关闭所有 Python / GameOpsMonitor 进程")
            print(f"     2. 临时关闭杀软实时防护（360 / Defender）")
            print(f"     3. 重启电脑后立刻跑（不要打开其他东西）")
            print(f"     4. 把项目挪到非 OneDrive 目录（如 D:\\Projects\\）")
            print()

    # 3. 清理 .spec.bak
    for spec in ROOT.glob('*.spec.bak'):
        try:
            spec.unlink()
        except Exception:
            pass

    print("✓ 清理完成")


def check_pyinstaller():
    """检查 PyInstaller 是否安装"""
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller 未安装")
        print("   请运行: pip install pyinstaller")
        sys.exit(1)


def build(gui: bool = True, onefile: bool = False, clean_first: bool = False, force_clean: bool = False):
    """执行打包"""
    if clean_first or force_clean:
        clean(force=True)
    else:
        # 即使不传 --clean，也要杀进程（防止锁文件）
        kill_running_exe()
    
    check_pyinstaller()
    
    # 选择 spec 文件
    if gui:
        spec_name = 'game_ops_monitor.spec'
    else:
        spec_name = 'cli.spec'
    
    spec_path = ROOT / spec_name
    if not spec_path.exists():
        print(f"❌ 找不到 {spec_name}")
        sys.exit(1)
    
    # 构建命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        str(spec_path),
        '--noconfirm',
        '--clean',
    ]
    
    if onefile:
        cmd.extend(['--onefile'])
    
    print(f"\n📦 开始打包 {'GUI' if gui else 'CLI'} 版本...")
    print(f"   命令: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, cwd=ROOT)
    
    if result.returncode == 0:
        print("\n" + "="*60)
        print("✅ 打包成功！")
        print("="*60)
        
        dist = ROOT / 'dist'
        if gui:
            exe_name = 'GameOpsMonitor'
        else:
            exe_name = 'GameOpsMonitor-CLI'
        
        if (dist / f'{exe_name}.exe').exists():
            print(f"\n🪟 Windows: {dist / f'{exe_name}.exe'}")
        if (dist / exe_name / exe_name).exists():
            print(f"🐧 Linux:   {dist / exe_name / exe_name}")
        if (dist / f'{exe_name}.app').exists():
            print(f"🍎 macOS:   {dist / f'{exe_name}.app'}")
        
        # 体积统计
        print(f"\n📊 产物大小:")
        total = 0
        for f in dist.rglob('*'):
            if f.is_file():
                size_mb = f.stat().st_size / 1024 / 1024
                total += size_mb
                if size_mb > 5:
                    print(f"   {size_mb:>6.1f} MB  {f.relative_to(dist)}")
        print(f"   {'-'*30}")
        print(f"   {total:>6.1f} MB  TOTAL")
    else:
        print("\n❌ 打包失败")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='打包 GameOpsMonitor')
    parser.add_argument('--clean', action='store_true', help='先清理再打包（推荐）')
    parser.add_argument('--gui', action='store_true', default=True, help='打包 GUI 版本（默认）')
    parser.add_argument('--cli', action='store_true', help='打包 CLI 版本（无 GUI 依赖）')
    parser.add_argument('--onefile', action='store_true', help='单文件模式（启动慢但分发简单）')
    parser.add_argument('--force', action='store_true', help='强制清理（即使有锁也尝试）')
    args = parser.parse_args()
    
    gui = not args.cli
    build(gui=gui, onefile=args.onefile, clean_first=args.clean, force_clean=args.force)


if __name__ == '__main__':
    main()
