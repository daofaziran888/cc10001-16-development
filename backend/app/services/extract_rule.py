"""抽取模板业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import time
from typing import Any

from app.store import store

MODULE = "extract_rule"
LIST_FIELDS = ["规则编号", "目标站点", "页面类型", "字段路径", "提取方式", "缺省值", "校验正则", "规则优先级"]
# 规则版本与部署时间用于冲突裁决和结果追溯，列表不展示但要随登记保存。
EXTRA_FIELDS = ["规则版本", "提取表达式"]
REQUIRED_FIELDS = ["规则编号", "目标站点", "页面类型"]
STATUS_ORDER = ["草稿", "校验中", "已发布", "已废弃"]
ACTION_RULES = {"提交校验": "校验中", "发布规则": "已发布", "废弃规则": "已废弃"}
NEGATIVE_ACTIONS = []


class ExtractRuleService:
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
            rows = [row for row in rows if keyword.casefold() in str(row.get("规则编号", "")).casefold()]
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
            return None, f"抽取规则 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于抽取模板可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        if action == "发布规则":
            # 冲突裁决按最新部署版本，发布时间是裁决依据，发布时必须写入。
            entry["部署时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return entry, f"抽取规则已{action}"
