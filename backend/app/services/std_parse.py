"""原始采集页标准化解析：按已部署解析配置与抽取规则生成结果数据集。

数据流：raw_page + parse_engine + extract_rule -> std_parse -> result_store

设计要点：
- 解析只接受“已部署”的解析配置，且页面类型、目标站点必须与页面一致；
- 每条结果记录都带配置版本、字段路径、来源页面与命中的抽取规则；
- 同一字段的冲突规则不会静默覆盖：未采用/候选规则全部写入 rule_hits；
- 同一页面 + 配置 + 版本重复提交时只返回第一次生成的数据集，不重复生成批次。
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from app.store import store
from app.services.result_store import ResultStoreService

PAGE_MODULE = "raw_page"
CONFIG_MODULE = "parse_engine"
RULE_MODULE = "extract_rule"

DATASET_KEY = "std_parse_datasets"
RESULT_KEY = "std_parse_results"
BATCH_KEY = "std_parse_batches"

CONFLICT_POLICIES = {
    "latest_deploy": "按最新部署版本选择一条，其余规则记录为未采用",
    "candidates": "输出多个候选值并把字段标记为待确认",
}

FIELD_PARSED = "已解析"
FIELD_PENDING = "待确认"
FIELD_INVALID = "校验失败"
FIELD_MISSING = "缺失"
FIELD_NO_RULE = "缺规则"

STATUS_KEYS = [FIELD_PARSED, FIELD_PENDING, FIELD_INVALID, FIELD_MISSING, FIELD_NO_RULE]


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _next_joint_id(key: str) -> int:
    return max((int(row.get("id", 0)) for row in store.joint_rows(key)), default=0) + 1


def _load_json(text: Any) -> Any:
    if isinstance(text, (dict, list)):
        return text
    try:
        return json.loads(str(text or ""))
    except (TypeError, ValueError):
        return None


def _read_path(data: Any, path: str) -> Any:
    """按点号路径读取 JSON 内容；路径为空时返回原始内容。"""
    if not path:
        return data
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            index = _as_int(part, -1)
            if index < 0 or index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


def _normalize(value: Any, type_name: str) -> tuple[Any, str | None]:
    """按输出 Schema 的类型收敛字段值，返回 (值, 错误说明)。"""
    if value is None:
        return None, None
    kind = (type_name or "string").strip().lower()
    if kind in ("string", "str", "text", ""):
        return str(value), None
    if kind in ("integer", "int"):
        if isinstance(value, bool):
            return None, "布尔值不能转换为整数"
        if isinstance(value, int):
            return value, None
        if isinstance(value, float) and value.is_integer():
            return int(value), None
        text = str(value).strip()
        if re.fullmatch(r"[+-]?\d+", text):
            return int(text), None
        return None, f"值「{value}」不是整数"
    if kind in ("number", "float", "decimal"):
        if isinstance(value, bool):
            return None, "布尔值不能转换为数值"
        if isinstance(value, (int, float)):
            return float(value), None
        text = str(value).strip()
        if re.fullmatch(r"[+-]?\d+(\.\d+)?", text):
            return float(text), None
        return None, f"值「{value}」不是数值"
    if kind in ("boolean", "bool"):
        if isinstance(value, bool):
            return value, None
        text = str(value).strip().lower()
        if text in ("true", "1", "yes", "是"):
            return True, None
        if text in ("false", "0", "no", "否"):
            return False, None
        return None, f"值「{value}」不是布尔值"
    return str(value), None


def _extract(rule: dict[str, Any], page: dict[str, Any], content: Any, field_path: str) -> Any:
    """按抽取方式从原始页面内容中取值；通配规则的路径由配置字段补齐。"""
    method = str(rule.get("提取方式") or "JSON路径").strip()
    rule_path = str(rule.get("字段路径") or "").strip()
    path = field_path if rule_path in ("", "*") else rule_path
    if method in ("缺省值", "固定值", "常量"):
        return rule.get("缺省值")
    if method in ("页面标题", "标题"):
        if isinstance(content, dict) and content.get("html_title") not in (None, ""):
            return content.get("html_title")
        raw_text = str(page.get("页面内容") or "")
        match = re.search(r"<title[^>]*>(.*?)</title>", raw_text, re.S | re.I)
        if match:
            return match.group(1).strip()
        return _read_path(content, "title")
    if method in ("正则", "正则捕获"):
        pattern = str(rule.get("提取表达式") or rule.get("校验正则") or "")
        raw_text = str(page.get("页面内容") or "")
        if not pattern:
            return None
        match = re.search(pattern, raw_text, re.S)
        if not match:
            return None
        return match.group(1) if match.groups() else match.group(0)
    return _read_path(content, path)


class StdParseService:
    def __init__(self) -> None:
        self._result_svc = ResultStoreService()

    # ---------- 原始采集页 ----------

    def list_raw_pages(
        self,
        *,
        filters: dict[str, str] | None = None,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(PAGE_MODULE)
        for field, expected in (filters or {}).items():
            rows = [row for row in rows if expected.casefold() in str(row.get(field, "")).casefold()]
        if keyword:
            rows = [row for row in rows if keyword.casefold() in str(row.get("页面编号", "")).casefold()]
        total = len(rows)
        start = (page - 1) * size
        # 列表不返回完整的页面内容，避免把原始大字段带进列表接口。
        items = [
            {key: value for key, value in row.items() if key != "页面内容"}
            for row in rows[start:start + size]
        ]
        return items, total

    def get_raw_page(self, page_id: int) -> dict[str, Any] | None:
        return store.find(PAGE_MODULE, page_id)

    # ---------- 候选规则与配置 ----------

    def list_deployed_configs(self, raw_page_id: int | None = None) -> list[dict[str, Any]]:
        configs = [row for row in store.rows(CONFIG_MODULE) if row.get("status") == "已部署"]
        if raw_page_id is not None:
            page = self.get_raw_page(raw_page_id)
            if page is not None:
                configs = [
                    row for row in configs
                    if str(row.get("页面类型", "")) == str(page.get("页面类型", ""))
                    and (
                        not row.get("目标站点")
                        or not page.get("目标站点")
                        or str(row.get("目标站点")) == str(page.get("目标站点"))
                    )
                ]
        return configs

    def _matching_rules(self, page: dict[str, Any], field_path: str) -> list[dict[str, Any]]:
        """取当前页面已发布的规则；精确字段路径优先，没有时用通配规则兜底。"""
        site = str(page.get("目标站点") or "")
        page_type = str(page.get("页面类型") or "")
        # 已废弃规则不得被新建解析引用；只有已发布规则参与字段解析。
        published = [row for row in store.rows(RULE_MODULE) if row.get("status") == "已发布"]
        scoped = [
            row for row in published
            if str(row.get("目标站点") or "") in ("", "*", site)
            and str(row.get("页面类型") or "") in ("", "*", page_type)
        ]
        exact = [row for row in scoped if str(row.get("字段路径") or "") == field_path]
        if exact:
            return exact
        wildcard = [row for row in scoped if str(row.get("字段路径") or "") == "*"]
        if wildcard:
            return wildcard
        # 没有精确规则也没有通配规则时，如实返回空，字段状态记为“缺规则”。
        return []

    @staticmethod
    def _deploy_key(rule: dict[str, Any]) -> tuple[str, int]:
        """规则部署时间越新越优先；没有部署时间时按规则 id 兜底。"""
        deployed_at = str(rule.get("部署时间") or rule.get("发布时间") or "")
        return deployed_at, _as_int(rule.get("id"))

    @staticmethod
    def _rule_version(rule: dict[str, Any]) -> str:
        return str(rule.get("规则版本") or rule.get("版本号") or "")

    def _extract_with_rules(
        self,
        field: dict[str, Any],
        page: dict[str, Any],
        content: Any,
        conflict_policy: str,
    ) -> dict[str, Any]:
        """解析单个字段，并返回带规则命中明细的结果。"""
        field_name = str(field.get("name") or field.get("字段") or field.get("path") or "")
        field_path = str(field.get("path") or field.get("字段路径") or "")
        field_type = str(field.get("type") or field.get("类型") or "string")
        required = bool(field.get("required", False))
        default = field.get("default")

        rules = self._matching_rules(page, field_path)
        rule_hits: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        applied: dict[str, Any] | None = None
        value: Any = None
        conflict = False
        status = FIELD_PARSED
        validation: dict[str, Any] = {
            "passed": True, "pattern": "", "message": "", "expected_type": field_type,
            "required": required, "default_used": False,
        }

        if not rules:
            status = FIELD_NO_RULE
            validation.update({"passed": False, "message": "没有匹配的已发布抽取规则"})
            return {
                "field_name": field_name, "field_path": field_path, "value": None,
                "candidates": [], "field_status": status, "rule_hits": [],
                "applied_rule": None, "conflict": False, "validation": validation,
            }

        # 精确规则 / 通配规则各自按优先级分组；最高优先级组内再做冲突裁决。
        extracted: list[tuple[dict[str, Any], Any]] = [
            (rule, _extract(rule, page, content, field_path)) for rule in rules
        ]
        highest = max(_as_int(rule.get("规则优先级")) for rule, _ in extracted)
        top = [(rule, val) for rule, val in extracted if _as_int(rule.get("规则优先级")) == highest]
        lower = [(rule, val) for rule, val in extracted if _as_int(rule.get("规则优先级")) != highest]

        top_sorted = sorted(top, key=lambda item: self._deploy_key(item[0]), reverse=True)
        distinct_values = []
        for rule, val in top_sorted:
            normalized = json.dumps(val, ensure_ascii=False, sort_keys=True) if isinstance(val, (dict, list)) else str(val)
            if normalized not in distinct_values:
                distinct_values.append(normalized)

        # 最新部署版本若恰好取不到值，退到同组内下一个有值的规则，避免可用值被空值静默掩盖。
        usable = [(rule, val) for rule, val in top_sorted if not _is_empty(val)]
        chosen_rule, chosen_value = (usable or top_sorted)[0]
        # 有值规则在部署顺序中的位置；用于区分“因空值让位”和“按冲突裁决未采用”。
        chosen_is_latest = chosen_rule is top_sorted[0][0]

        if len(top_sorted) > 1 and len(distinct_values) > 1:
            conflict = True
            if conflict_policy == "candidates":
                status = FIELD_PENDING
                validation.update({"passed": False, "message": "存在同优先级冲突候选，字段待人工确认"})
                for rule, val in top_sorted:
                    candidates.append({
                        "rule_id": int(rule.get("id", 0)),
                        "rule_code": str(rule.get("规则编号", "")),
                        "rule_version": self._rule_version(rule),
                        "priority": _as_int(rule.get("规则优先级")),
                        "value": val,
                        "deployed_at": str(rule.get("部署时间") or ""),
                    })
                applied = chosen_rule
                value = chosen_value
                for rule, val in top_sorted:
                    hit = {
                        "rule_id": int(rule.get("id", 0)),
                        "rule_code": str(rule.get("规则编号", "")),
                        "rule_path": str(rule.get("字段路径") or ""),
                        "rule_version": self._rule_version(rule),
                        "priority": _as_int(rule.get("规则优先级")),
                        "value": val,
                        "deployed_at": str(rule.get("部署时间") or ""),
                        "status": "候选",
                        "note": "同优先级冲突，保留为候选值；字段待人工确认",
                    }
                    if rule is chosen_rule:
                        hit["note"] += "，当前记录主值取该规则"
                    rule_hits.append(hit)
            else:
                applied = chosen_rule
                value = chosen_value
                for rule, val in top_sorted:
                    hit = {
                        "rule_id": int(rule.get("id", 0)),
                        "rule_code": str(rule.get("规则编号", "")),
                        "rule_path": str(rule.get("字段路径") or ""),
                        "rule_version": self._rule_version(rule),
                        "priority": _as_int(rule.get("规则优先级")),
                        "value": val,
                        "deployed_at": str(rule.get("部署时间") or ""),
                        "status": "命中" if rule is chosen_rule else "未采用",
                    }
                    if rule is not chosen_rule:
                        if _is_empty(val):
                            hit["note"] = "最新部署规则取值为空，字段值改用同组内下一个有值规则"
                        else:
                            hit["note"] = "同优先级但提取值不同，按最新部署版本被裁决为未采用"
                    elif not chosen_is_latest:
                        hit["note"] = "最新部署规则取值为空，当前规则为同组下一个有值规则"
                    rule_hits.append(hit)
        else:
            applied = chosen_rule
            value = chosen_value
            for rule, val in top_sorted:
                hit = {
                    "rule_id": int(rule.get("id", 0)),
                    "rule_code": str(rule.get("规则编号", "")),
                    "rule_path": str(rule.get("字段路径") or ""),
                    "rule_version": self._rule_version(rule),
                    "priority": _as_int(rule.get("规则优先级")),
                    "value": val,
                    "deployed_at": str(rule.get("部署时间") or ""),
                    "status": "命中" if rule is chosen_rule else "值一致",
                }
                if rule is not chosen_rule:
                    hit["note"] = "同优先级且提取值一致，记录为一致规则"
                rule_hits.append(hit)

        chosen_repr = (
            json.dumps(value, ensure_ascii=False, sort_keys=True)
            if isinstance(value, (dict, list)) else str(value)
        )
        for rule, val in lower:
            val_repr = (
                json.dumps(val, ensure_ascii=False, sort_keys=True)
                if isinstance(val, (dict, list)) else str(val)
            )
            same_value = val_repr == chosen_repr
            rule_hits.append({
                "rule_id": int(rule.get("id", 0)),
                "rule_code": str(rule.get("规则编号", "")),
                "rule_path": str(rule.get("字段路径") or ""),
                "rule_version": self._rule_version(rule),
                "priority": _as_int(rule.get("规则优先级")),
                "value": val,
                "deployed_at": str(rule.get("部署时间") or ""),
                "status": "值一致" if same_value else "未采用",
                "note": (
                    "优先级低于当前命中规则，但提取值一致"
                    if same_value
                    else "优先级低于当前命中规则，未覆盖字段值"
                ),
            })

        # 校验正则来自生效规则；通配规则没有正则时只做类型与必填校验。
        pattern = str(chosen_rule.get("校验正则") or "")
        validation["pattern"] = pattern
        raw_missing = _is_empty(value)
        if raw_missing:
            effective_default = default
            if effective_default is None and str(chosen_rule.get("缺省值") or "") != "":
                effective_default = chosen_rule.get("缺省值")
            if effective_default is not None and str(effective_default) != "":
                value = effective_default
                validation["default_used"] = True
                raw_missing = False
            elif required:
                status = FIELD_MISSING
                validation.update({"passed": False, "message": "必填字段在原始页面中缺失"})
            else:
                status = FIELD_MISSING
                validation.update({"passed": False, "message": "字段在原始页面中缺失且没有缺省值"})
        if not raw_missing and status != FIELD_PENDING:
            normalized, type_error = _normalize(value, field_type)
            if type_error:
                status = FIELD_INVALID
                validation.update({"passed": False, "message": type_error})
                value = value
            else:
                value = normalized
        elif not raw_missing and status == FIELD_PENDING:
            # 候选模式下仍按类型收敛主候选值，类型错误会保留在记录里给人工确认。
            normalized, type_error = _normalize(value, field_type)
            if type_error:
                validation["message"] = type_error
            else:
                value = normalized
            candidates = [
                {**item, "value": _normalize(item["value"], field_type)[0]}
                for item in candidates
            ]

        if status not in (FIELD_MISSING, FIELD_NO_RULE, FIELD_PENDING) and pattern and value is not None:
            if not re.search(pattern, str(value)):
                status = FIELD_INVALID
                validation.update({"passed": False, "message": f"校验正则 {pattern} 未通过"})

        if status == FIELD_PARSED and validation["default_used"]:
            validation["message"] = "原始字段缺失，使用缺省值"
        elif status == FIELD_PARSED:
            validation["message"] = "校验通过"

        return {
            "field_name": field_name,
            "field_path": field_path,
            "value": value,
            "candidates": candidates,
            "field_status": status,
            "rule_hits": rule_hits,
            "applied_rule": applied,
            "conflict": conflict,
            "validation": validation,
        }

    # ---------- 解析执行 ----------

    def run(
        self,
        raw_page_id: int,
        config_id: int,
        conflict_policy: str = "latest_deploy",
    ) -> dict[str, Any]:
        policy = (conflict_policy or "latest_deploy").strip()
        if policy not in CONFLICT_POLICIES:
            return {"ok": False, "error": f"未知的冲突处理策略「{policy}」"}

        page = self.get_raw_page(raw_page_id)
        if page is None:
            return {"ok": False, "error": f"原始采集页 {raw_page_id} 不存在"}
        config = store.find(CONFIG_MODULE, config_id)
        if config is None:
            return {"ok": False, "error": f"解析配置 {config_id} 不存在"}
        if config.get("status") != "已部署":
            return {"ok": False, "error": f"解析配置 {config_id} 尚未部署，不能用于标准化解析"}
        if str(config.get("页面类型") or "") != str(page.get("页面类型") or ""):
            return {
                "ok": False,
                "error": (
                    f"解析配置页面类型「{config.get('页面类型')}」与原始页面「{page.get('页面类型')}」不一致，"
                    "不能跨引擎解析"
                ),
            }
        if config.get("目标站点") and page.get("目标站点") and str(config.get("目标站点")) != str(page.get("目标站点")):
            return {"ok": False, "error": "解析配置的目标站点与原始采集页不一致"}

        config_version = str(config.get("版本号") or "未标注")
        dedupe_key = f"{raw_page_id}:{config_id}:{config_version}"
        existing = next(
            (row for row in store.joint_rows(DATASET_KEY) if row.get("dedupe_key") == dedupe_key),
            None,
        )
        if existing is not None:
            return self._dataset_payload(existing, duplicate=True, requested_policy=policy)

        content = _load_json(page.get("页面内容"))
        if content is None:
            return {"ok": False, "error": f"原始采集页 {raw_page_id} 的内容不是合法 JSON，无法解析"}

        rule_spec = _load_json(config.get("解析规则"))
        fields: list[dict[str, Any]] = []
        if isinstance(rule_spec, dict):
            raw_fields = rule_spec.get("fields") or []
            if isinstance(raw_fields, dict):
                raw_fields = [
                    {"name": name, "path": path, "type": "string"}
                    for name, path in raw_fields.items()
                ]
            if isinstance(raw_fields, list):
                fields = [item for item in raw_fields if isinstance(item, dict)]
        if not fields:
            return {"ok": False, "error": "解析配置没有声明可解析的字段规则（解析规则.fields）"}

        # 先按页面 + 配置版本算出字段结果，再一次性写入数据集、批次与仓储批次；
        # 仓储写入失败会回滚已写的结果记录，避免留下半成品数据集。
        dataset_id = _next_joint_id(DATASET_KEY)
        batch_record_id = _next_joint_id(BATCH_KEY)
        created_at = _now()
        dataset_code = f"DS-{dataset_id:04d}"
        result_batch_code = f"STDP-{raw_page_id}-{config_id}-{dataset_id}"
        page_code = str(page.get("页面编号") or f"PAGE-{raw_page_id}")

        records: list[dict[str, Any]] = []
        status_counts = {key: 0 for key in STATUS_KEYS}
        rule_sources: list[dict[str, Any]] = []
        pending_fields = 0
        conflict_fields = 0
        failed_fields = 0

        result_id = _next_joint_id(RESULT_KEY)
        for field in fields:
            parsed = self._extract_with_rules(field, page, content, policy)
            status = parsed["field_status"]
            status_counts[status] = status_counts.get(status, 0) + 1
            if status == FIELD_PENDING:
                pending_fields += 1
            if status in (FIELD_INVALID, FIELD_MISSING, FIELD_NO_RULE):
                failed_fields += 1
            if parsed["conflict"]:
                conflict_fields += 1
            applied = parsed["applied_rule"]
            record = {
                "id": result_id,
                "dataset_id": dataset_id,
                "dataset_code": dataset_code,
                "batch_record_id": batch_record_id,
                "result_batch_code": result_batch_code,
                "raw_page_id": raw_page_id,
                "page_code": page_code,
                "source_url": str(page.get("来源URL") or ""),
                "target_site": str(page.get("目标站点") or ""),
                "page_type": str(page.get("页面类型") or ""),
                "field_name": parsed["field_name"],
                "field_path": parsed["field_path"],
                "value": parsed["value"],
                "candidates": parsed["candidates"],
                "field_status": status,
                "conflict": parsed["conflict"],
                "config_id": config_id,
                "config_code": str(config.get("配置编号") or ""),
                "config_version": config_version,
                "applied_rule_id": int(applied.get("id", 0)) if applied else None,
                "applied_rule_code": str(applied.get("规则编号") or "") if applied else "",
                "applied_rule_version": self._rule_version(applied) if applied else "",
                "rule_hits": parsed["rule_hits"],
                "validation": parsed["validation"],
                "extracted_at": created_at,
            }
            store.joint_append(RESULT_KEY, record)
            records.append(record)
            result_id += 1
            for hit in parsed["rule_hits"]:
                rule_sources.append({
                    "field_path": parsed["field_path"],
                    "field_name": parsed["field_name"],
                    "rule_id": hit["rule_id"],
                    "rule_code": hit["rule_code"],
                    "rule_version": hit["rule_version"],
                    "priority": hit["priority"],
                    "status": hit["status"],
                })

        # 合并重复规则来源，保留每个字段的命中/未采用状态，供跨模块链路追溯。
        merged_sources: dict[str, dict[str, Any]] = {}
        for item in rule_sources:
            key = f"{item['rule_id']}:{item['field_path']}:{item['status']}"
            merged_sources[key] = item
        rule_sources = list(merged_sources.values())
        # 规则来源摘要只按规则 + 状态归并，避免同一通配规则按字段重复堆叠。
        source_groups: dict[str, dict[str, Any]] = {}
        for item in rule_sources:
            key = f"{item['rule_code']}@{item['rule_version'] or '-'}:{item['status']}"
            group = source_groups.setdefault(
                key,
                {
                    "rule_code": item["rule_code"],
                    "rule_version": item["rule_version"],
                    "status": item["status"],
                    "fields": [],
                },
            )
            if item["field_path"] not in group["fields"]:
                group["fields"].append(item["field_path"])
        source_summary = "; ".join(
            f"{group['rule_code']}@{group['rule_version'] or '-'}({group['status']}: "
            f"{'、'.join(group['fields'])})"
            for group in sorted(
                source_groups.values(), key=lambda item: (item["rule_code"], item["status"]))
        )

        if pending_fields:
            batch_status = FIELD_PENDING
            result_store_status = "已落盘"
        elif failed_fields:
            batch_status = "部分失败"
            result_store_status = "校验失败"
        else:
            batch_status = "已完成"
            result_store_status = "校验通过"

        checksum = hashlib.sha256(
            json.dumps(
                {
                    "dataset": dataset_code,
                    "page": raw_page_id,
                    "config": [config_id, config_version],
                    "records": [
                        [record["field_path"], record["field_status"], record["value"]]
                        for record in records
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16]

        # 标准化结果同时写入采集仓储，下游审计/分发可以直接消费该批次。
        extra_values = {
            "配置编号": str(config.get("配置编号") or ""),
            "配置版本": config_version,
            "解析数据集": dataset_code,
            "规则来源": source_summary,
            "字段状态分布": json.dumps(status_counts, ensure_ascii=False),
            "待确认字段数": str(pending_fields),
        }
        batch_values = {
            "批次编号": result_batch_code,
            "关联任务": page_code,
            "原始行数": str(len(fields)),
            "有效行数": str(len(fields) - failed_fields - pending_fields),
            "存储路径": f"/store/std_parse/{dataset_code}/{checksum}.json",
            "压缩格式": "json",
            "校验摘要": checksum,
            "落地时间": created_at,
            **extra_values,
        }
        result_entry, missing = self._result_svc.create_entry(batch_values)
        if result_entry is None:
            # 仓储写入失败时不留下半成品数据集。
            self._drop_dataset_records(dataset_id)
            return {"ok": False, "error": f"结果批次写入失败：缺少 {'、'.join(missing)}"}
        result_entry.update(extra_values)
        result_entry["status"] = result_store_status
        result_entry["pending"] = batch_status != "已完成"
        result_entry["abnormal"] = failed_fields > 0

        dataset = {
            "id": dataset_id,
            "数据集编号": dataset_code,
            "dedupe_key": dedupe_key,
            "raw_page_id": raw_page_id,
            "页面编号": page_code,
            "source_url": str(page.get("来源URL") or ""),
            "target_site": str(page.get("目标站点") or ""),
            "page_type": str(page.get("页面类型") or ""),
            "config_id": config_id,
            "config_code": str(config.get("配置编号") or ""),
            "config_version": config_version,
            "conflict_policy": policy,
            "batch_record_id": batch_record_id,
            "result_batch_id": int(result_entry["id"]),
            "result_batch_code": result_batch_code,
            "field_count": len(fields),
            "record_count": len(records),
            "pending_fields": pending_fields,
            "failed_fields": failed_fields,
            "conflict_fields": conflict_fields,
            "field_status_counts": status_counts,
            "rule_sources": rule_sources,
            "规则来源": source_summary,
            "status": batch_status,
            "checksum": checksum,
            "created_at": created_at,
        }
        batch = {
            "id": batch_record_id,
            "batch_id": batch_record_id,
            "批次编号": result_batch_code,
            "dataset_id": dataset_id,
            "dataset_code": dataset_code,
            "raw_page_id": raw_page_id,
            "config_id": config_id,
            "config_code": str(config.get("配置编号") or ""),
            "config_version": config_version,
            "conflict_policy": policy,
            "total_fields": len(fields),
            "field_status_counts": status_counts,
            "pending_fields": pending_fields,
            "failed_fields": failed_fields,
            "conflict_fields": conflict_fields,
            "rule_sources": rule_sources,
            "规则来源": source_summary,
            "result_batch_id": int(result_entry["id"]),
            "result_batch_code": result_batch_code,
            "status": batch_status,
            "created_at": created_at,
        }
        store.joint_append(DATASET_KEY, dataset)
        store.joint_append(BATCH_KEY, batch)
        return {
            "ok": True,
            "duplicate": False,
            "message": f"标准化解析完成，字段状态：{batch_status}",
            "dataset": dataset,
            "batch": batch,
            "records": records,
            "result_entry": result_entry,
        }

    def _drop_dataset_records(self, dataset_id: int) -> None:
        remaining = [
            row for row in store.joint_rows(RESULT_KEY)
            if int(row.get("dataset_id", 0)) != dataset_id
        ]
        store.joint_replace(RESULT_KEY, remaining)

    def _dataset_payload(
        self,
        dataset: dict[str, Any],
        *,
        duplicate: bool,
        requested_policy: str,
    ) -> dict[str, Any]:
        batch = next(
            (row for row in store.joint_rows(BATCH_KEY) if int(row.get("dataset_id", 0)) == int(dataset["id"])),
            None,
        )
        records = [
            row for row in store.joint_rows(RESULT_KEY)
            if int(row.get("dataset_id", 0)) == int(dataset["id"])
        ]
        result_entry = store.find("result_store", int(dataset.get("result_batch_id", 0)))
        message = (
            f"重复提交，返回首次解析结果 {dataset.get('数据集编号')}；"
            f"本次冲突策略「{requested_policy}」不覆盖已生成结果"
        )
        return {
            "ok": True,
            "duplicate": duplicate,
            "message": message,
            "dataset": dataset,
            "batch": batch,
            "records": records,
            "result_entry": result_entry,
        }

    # ---------- 查询 ----------

    def list_datasets(
        self,
        *,
        keyword: str | None = None,
        config_version: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = list(reversed(store.joint_rows(DATASET_KEY)))
        if keyword:
            needle = keyword.casefold()
            rows = [
                row for row in rows
                if needle in str(row.get("数据集编号", "")).casefold()
                or needle in str(row.get("页面编号", "")).casefold()
                or needle in str(row.get("config_code", "")).casefold()
            ]
        if config_version:
            rows = [row for row in rows if str(row.get("config_version", "")) == config_version]
        total = len(rows)
        start = (page - 1) * size
        # 列表行把批次状态、规则来源摘要与批次编号一并带出，页面无需逐条再查批次表。
        batch_by_dataset = {
            int(row.get("dataset_id", 0)): row for row in store.joint_rows(BATCH_KEY)
        }
        items = []
        for row in rows[start:start + size]:
            batch = batch_by_dataset.get(int(row.get("id", 0)), {})
            items.append({
                **row,
                "batch_status": batch.get("status", ""),
                "result_batch_code": batch.get("批次编号", row.get("result_batch_code", "")),
                "source_summary": batch.get("规则来源", ""),
            })
        return items, total

    def list_batches(
        self,
        *,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = list(reversed(store.joint_rows(BATCH_KEY)))
        total = len(rows)
        start = (page - 1) * size
        return rows[start:start + size], total

    def get_dataset(self, dataset_id: int) -> dict[str, Any] | None:
        return next(
            (row for row in store.joint_rows(DATASET_KEY) if int(row.get("id", 0)) == dataset_id),
            None,
        )

    def dataset_detail(self, dataset_id: int) -> dict[str, Any] | None:
        dataset = self.get_dataset(dataset_id)
        if dataset is None:
            return None
        payload = self._dataset_payload(
            dataset, duplicate=False, requested_policy=str(dataset.get("conflict_policy", ""))
        )
        batch = payload.get("batch") or {}
        dataset = {
            **dataset,
            "batch_status": batch.get("status", ""),
            "source_summary": batch.get("规则来源", ""),
        }
        payload["dataset"] = dataset
        return payload

    def list_records(self, dataset_id: int | None = None) -> list[dict[str, Any]]:
        rows = store.joint_rows(RESULT_KEY)
        if dataset_id is not None:
            rows = [row for row in rows if int(row.get("dataset_id", 0)) == dataset_id]
        return list(rows)

    def lineage(self, dataset_id: int) -> dict[str, Any] | None:
        """跨模块追溯：数据集 -> 结果批次 -> 采集仓储批次 -> 下游审计/分发记录。"""
        dataset = self.get_dataset(dataset_id)
        if dataset is None:
            return None
        batch = next(
            (row for row in store.joint_rows(BATCH_KEY) if int(row.get("dataset_id", 0)) == dataset_id),
            None,
        )
        result_batch_id = int(dataset.get("result_batch_id", 0))
        result_entry = store.find("result_store", result_batch_id)
        audits = [
            row for row in store.joint_rows("audit_records")
            if int(row.get("batch_id", 0)) == result_batch_id
        ]
        dispatches = [
            row for row in store.joint_rows("dispatch_logs")
            if int(row.get("batch_id", 0)) == result_batch_id
        ]
        # 规则来源随批次一路保留；这里显式带出，避免下游只拿到数值结果。
        rule_sources = (batch or {}).get("rule_sources") or dataset.get("rule_sources") or []
        return {
            "dataset": {
                "id": dataset["id"],
                "数据集编号": dataset.get("数据集编号"),
                "config_code": dataset.get("config_code"),
                "config_version": dataset.get("config_version"),
                "raw_page_id": dataset.get("raw_page_id"),
                "页面编号": dataset.get("页面编号"),
                "source_url": dataset.get("source_url"),
                "conflict_policy": dataset.get("conflict_policy"),
                "checksum": dataset.get("checksum"),
            },
            "batch": batch,
            "result_store": result_entry,
            "downstream": {"audits": audits, "dispatches": dispatches},
            "rule_sources": rule_sources,
        }

    def get_batch(self, batch_id: int) -> dict[str, Any] | None:
        return next(
            (row for row in store.joint_rows(BATCH_KEY) if int(row.get("id", 0)) == batch_id),
            None,
        )

    def preview_rules(self, raw_page_id: int, config_id: int) -> dict[str, Any] | None:
        """预览页面 + 配置下每个字段会命中哪些已发布规则，便于人工排查冲突。"""
        page = self.get_raw_page(raw_page_id)
        config = store.find(CONFIG_MODULE, config_id)
        if page is None or config is None:
            return None
        rule_spec = _load_json(config.get("解析规则"))
        fields = []
        if isinstance(rule_spec, dict) and isinstance(rule_spec.get("fields"), list):
            fields = [item for item in rule_spec["fields"] if isinstance(item, dict)]
        preview = []
        for field in fields:
            path = str(field.get("path") or "")
            rules = self._matching_rules(page, path)
            preview.append({
                "field_name": str(field.get("name") or path),
                "field_path": path,
                "rules": [
                    {
                        "rule_id": int(rule.get("id", 0)),
                        "rule_code": str(rule.get("规则编号", "")),
                        "priority": _as_int(rule.get("规则优先级")),
                        "rule_version": self._rule_version(rule),
                        "deployed_at": str(rule.get("部署时间") or ""),
                        "field_path": str(rule.get("字段路径") or ""),
                    }
                    for rule in sorted(rules, key=self._deploy_key, reverse=True)
                ],
            })
        return {"raw_page_id": raw_page_id, "config_id": config_id, "fields": preview}


std_parse_service = StdParseService()
