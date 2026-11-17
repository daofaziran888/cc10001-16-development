"""分发调度器：读取采集仓储批次并生成分发记录。

数据流：result_store -> export_hub
"""
from __future__ import annotations

import time
from typing import Any

from app.store import store
from app.services.export_hub import ExportHubService

RESULT_MODULE = "result_store"


class ExportDispatcher:
    def __init__(self) -> None:
        self._export_svc = ExportHubService()

    def _next_log_id(self) -> int:
        rows = store.joint_rows("dispatch_logs")
        return max((int(r.get("id", 0)) for r in rows), default=0) + 1

    def dispatch_batch(self, batch_id: int, channel_format: str = "json") -> dict[str, Any]:
        """读取指定采集仓储批次，生成分发记录并写入数据分发通道。"""
        batch = store.find(RESULT_MODULE, batch_id)
        if batch is None:
            return {"ok": False, "error": f"结果批次 {batch_id} 不存在"}

        if batch.get("status") != "校验通过":
            return {"ok": False, "error": f"批次 {batch_id} 未通过校验，禁止分发"}

        # 创建分发通道记录（跨模块数据产物）
        export_values = {
            "通道编号": f"DISP-{batch_id}-{int(time.time())}",
            "输出格式": channel_format,
            "目标地址": f"s3://exports/{batch_id}.{channel_format}",
            "加密方式": "AES-256",
            "压缩选项": "gzip",
            "分片大小": str(batch.get("有效行数", "0")),
            "重试上限": "3",
            "回调地址": f"https://callback.example.com/{batch_id}",
        }
        export_entry, missing = self._export_svc.create_entry(export_values)
        if export_entry is None:
            return {"ok": False, "error": f"分发记录写入失败：缺少 {missing}"}

        # 记录分发日志（联合存储）
        log = {
            "id": self._next_log_id(),
            "batch_id": batch_id,
            "batch_code": str(batch.get("批次编号", "")),
            "export_entry_id": export_entry["id"],
            "channel_format": channel_format,
            "target": export_values["目标地址"],
            "config_code": str(batch.get("配置编号", "") or ""),
            "config_version": str(batch.get("配置版本", "") or ""),
            "rule_sources": str(batch.get("规则来源", "") or ""),
            "dispatched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "已启用",
        }
        store.joint_append("dispatch_logs", log)

        # 更新批次状态
        batch["status"] = "已分发"
        batch["pending"] = False

        return {
            "ok": True,
            "log": log,
            "export_entry": export_entry,
        }

    def dispatch_all_ready(self) -> dict[str, Any]:
        """对所有校验通过的批次执行自动分发。"""
        batches = [b for b in store.rows(RESULT_MODULE) if b.get("status") == "校验通过"]
        results: list[dict[str, Any]] = []
        for batch in batches:
            res = self.dispatch_batch(int(batch["id"]))
            results.append(res)
        succeeded = sum(1 for r in results if r.get("ok"))
        return {"ok": True, "dispatched": len(results), "succeeded": succeeded, "results": results}

    def list_logs(self) -> list[dict[str, Any]]:
        return list(store.joint_rows("dispatch_logs"))

    def get_log(self, log_id: int) -> dict[str, Any] | None:
        return store.joint_find("dispatch_logs", log_id)


export_dispatcher = ExportDispatcher()
