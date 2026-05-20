"""日报文件名与标题使用的「自然日」，默认按 REPORT_TIMEZONE（北京时间）。"""

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

DEFAULT_REPORT_TIMEZONE = "Asia/Shanghai"


def report_timezone_name() -> str:
    return (os.getenv("REPORT_TIMEZONE") or DEFAULT_REPORT_TIMEZONE).strip() or DEFAULT_REPORT_TIMEZONE


def report_timezone() -> ZoneInfo:
    return ZoneInfo(report_timezone_name())


def report_today() -> date:
    """当前配置时区下的日历日期（用于日报文件名与标题）。"""
    return datetime.now(report_timezone()).date()
