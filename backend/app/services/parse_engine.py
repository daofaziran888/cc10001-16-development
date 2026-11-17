"""解析引擎业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import time
from typing import Any

from app.store import store

MODULE = "parse_engine"
LIST_FIELDS = ["配置编号", "页面类型", "引擎类型", "解析规则", "字符编码", "容错模式", "输出Schema", "版本号"]
# 列表字段之外的协作字段：不参与筛选，但登记时必须保留，否则标准化解析无法按站点/引擎路由。
EXTRA_FIELDS = ["目标站点"]
REQUIRED_FIELDS = ["配置编号", "页面类型", "引擎类型"]
STATUS_ORDER = ["草稿", "已验证", "已部署", "已停用"]
ACTION_RULES = {"提交验证": "已验证", "部署上线": "已部署", "停用配置": "已停用"}
NEGATIVE_ACTIONS = ["停用配置"]


class ParseEngineService:
    def list_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        for field, expected in (filters or {}).items():
            rows = [row for row in rows if expected.casefold() in str(row.get(field, "")).casefold()]
        if keyword:
            rows = [row for row in rows if keyword.casefold() in str(row.get("配置编号", "")).casefold()]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = (page - 1) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in LIST_FIELDS})
        entry.update({field: values.get(field) for field in EXTRA_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"解析配置 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于解析引擎可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        if action == "部署上线":
            # 部署时间决定同一字段冲突规则/配置版本的先后，必须随部署动作一起记录。
            entry["部署时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return entry, f"解析配置已{action}"
