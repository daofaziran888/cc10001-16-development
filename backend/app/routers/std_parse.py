"""原始采集页标准化解析接口：读取原始页面、已部署配置与抽取规则，生成标准化结果。

接口分成三组：
- 原始采集页与候选配置：/raw-pages、/deployed-configs、/preview
- 解析执行：/run
- 结果查看：/datasets、/batches
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.schemas import PageResult
from app.services.std_parse import CONFLICT_POLICIES, std_parse_service

router = APIRouter(prefix="/api/std_parse", tags=["标准化解析"])

PAGE_LIST_FIELDS = ["页面编号", "目标站点", "页面类型", "来源URL", "采集任务", "采集时间"]


class RunParsePayload(BaseModel):
    raw_page_id: int = Field(gt=0)
    config_id: int = Field(gt=0)
    conflict_policy: str = "latest_deploy"


def page_filters(request: Request) -> dict[str, str]:
    return {
        key: value.strip()
        for key, value in request.query_params.items()
        if key in PAGE_LIST_FIELDS and value.strip()
    }


@router.get("/policies")
def list_policies() -> dict[str, object]:
    """列出冲突规则的两种裁决方式，页面据此展示可选策略。"""
    return {
        "items": [
            {"key": key, "description": description}
            for key, description in CONFLICT_POLICIES.items()
        ]
    }


@router.get("/raw-pages", response_model=PageResult[dict])
def list_raw_pages(
    request: Request,
    keyword: str | None = Query(default=None, description="按页面编号检索"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> PageResult[dict]:
    """列出可标准化的原始采集页（不含完整页面内容）。"""
    items, total = std_parse_service.list_raw_pages(
        filters=page_filters(request), keyword=keyword, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/raw-pages/{page_id}", response_model=dict)
def get_raw_page(page_id: int) -> dict:
    """读取单条原始采集页，包含完整页面内容供预览。"""
    entry = std_parse_service.get_raw_page(page_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"原始采集页 {page_id} 不存在")
    return entry


@router.get("/deployed-configs", response_model=list)
def list_deployed_configs(raw_page_id: int | None = Query(default=None, ge=1)) -> list:
    """只返回已部署的解析配置；带页面时按页面类型和站点过滤。"""
    return std_parse_service.list_deployed_configs(raw_page_id)


@router.get("/preview")
def preview_rules(
    raw_page_id: int = Query(ge=1),
    config_id: int = Query(ge=1),
) -> dict:
    """预览每个字段会命中的已发布规则，含同优先级冲突，便于先排查再解析。"""
    result = std_parse_service.preview_rules(raw_page_id, config_id)
    if result is None:
        raise HTTPException(status_code=404, detail="原始采集页或解析配置不存在")
    return result


@router.post("/run")
def run_parse(payload: RunParsePayload) -> dict:
    """按已部署配置执行标准化解析；重复提交返回首次解析结果而不是重新生成。"""
    result = std_parse_service.run(
        payload.raw_page_id, payload.config_id, payload.conflict_policy)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/datasets", response_model=PageResult[dict])
def list_datasets(
    keyword: str | None = Query(default=None),
    config_version: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> PageResult[dict]:
    """标准化解析结果数据集列表，最新生成的数据集排在前面。"""
    items, total = std_parse_service.list_datasets(
        keyword=keyword, config_version=config_version, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: int, include_records: bool = Query(default=False)) -> dict:
    """读取数据集详情；include_records 控制是否带出字段结果与规则来源。"""
    detail = std_parse_service.dataset_detail(dataset_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"标准化数据集 {dataset_id} 不存在")
    if not include_records:
        detail.pop("records", None)
    return detail


@router.get("/datasets/{dataset_id}/records", response_model=list)
def list_dataset_records(dataset_id: int) -> list:
    """读取数据集的字段结果：值、字段路径、状态、命中/未采用规则与校验结果。"""
    if std_parse_service.get_dataset(dataset_id) is None:
        raise HTTPException(status_code=404, detail=f"标准化数据集 {dataset_id} 不存在")
    return std_parse_service.list_records(dataset_id)


@router.get("/datasets/{dataset_id}/lineage", response_model=dict)
def get_dataset_lineage(dataset_id: int) -> dict:
    """跨模块链路：配置版本、结果批次、仓储批次与下游审计/分发，规则来源全程保留。"""
    result = std_parse_service.lineage(dataset_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"标准化数据集 {dataset_id} 不存在")
    return result


@router.get("/batches", response_model=PageResult[dict])
def list_batches(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> PageResult[dict]:
    """标准化解析结果批次记录，含字段状态分布与规则来源摘要。"""
    items, total = std_parse_service.list_batches(page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/batches/{batch_id}", response_model=dict)
def get_batch(batch_id: int) -> dict:
    entry = std_parse_service.get_batch(batch_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"标准化结果批次 {batch_id} 不存在")
    return entry
