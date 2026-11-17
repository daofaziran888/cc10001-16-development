"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import site_profile as router_site_profile
from app.routers import proxy_pool as router_proxy_pool
from app.routers import cookie_vault as router_cookie_vault
from app.routers import rate_limiter as router_rate_limiter
from app.routers import extract_rule as router_extract_rule
from app.routers import crawl_task as router_crawl_task
from app.routers import rpa_script as router_rpa_script
from app.routers import data_pipeline as router_data_pipeline
from app.routers import result_store as router_result_store
from app.routers import anti_block as router_anti_block
from app.routers import quality_check as router_quality_check
from app.routers import delta_sync as router_delta_sync
from app.routers import log_monitor as router_log_monitor
from app.routers import template_mgr as router_template_mgr
from app.routers import export_hub as router_export_hub
from app.routers import scheduler as router_scheduler
from app.routers import parse_engine as router_parse_engine
from app.routers import retry_queue as router_retry_queue
from app.routers import std_parse as router_std_parse

from app.routers import pipeline_api as router_pipeline_api

ROUTERS = [router_site_profile, router_proxy_pool, router_cookie_vault, router_rate_limiter, router_extract_rule, router_crawl_task, router_rpa_script, router_data_pipeline, router_result_store, router_anti_block, router_quality_check, router_delta_sync, router_log_monitor, router_template_mgr, router_export_hub, router_scheduler, router_parse_engine, router_retry_queue, router_std_parse, router_pipeline_api]
