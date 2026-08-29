"""
GUI 启动入口

用法：
    python -m src.gui_main
    或
    python src/gui_main.py

崩溃时日志写到 game_ops_monitor.log，方便排查
"""
import logging
import sys
import traceback
from pathlib import Path

# 让脚本能从项目根目录运行
sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置日志：同时输出到 stderr 和 game_ops_monitor.log
LOG_FILE = Path(__file__).parent.parent / "game_ops_monitor.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)

# 全局异常钩子：捕获所有未处理异常，写到日志
def exception_handler(exc_type, exc_value, exc_tb):
    """捕获所有未捕获异常，写到日志 + stderr"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    logger = logging.getLogger("uncaught")
    logger.error(
        "💥 未捕获异常: %s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    )
    # 仍然调用默认处理（让程序退出）
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = exception_handler

# PyQt6 异常钩子
def qt_exception_handler(exc_type, exc_value, exc_tb):
    """Qt 事件循环里的异常"""
    logger = logging.getLogger("qt_uncaught")
    logger.error(
        "💥 Qt 未捕获异常: %s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    )

from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow, run

# PyQt6 不用 setExceptionHandler，用 sys.excepthook 即可
# Qt 事件循环里的异常会通过 sys.excepthook 抛出


def main():
    """主函数"""
    return run()


if __name__ == "__main__":
    sys.exit(main())
