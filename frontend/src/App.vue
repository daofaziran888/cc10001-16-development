<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">采集工坊 · 爬虫与RPA开发平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向网页爬虫规则编排、自动化采集流程、代理调度、反爬对抗、结果校验与持久化发布的爬虫与RPA数据采集开发平台。</span>
        <span class="head-user">当前值班：{{ store.operator }} · {{ store.shiftLabel }}</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "站点画像", path: "/site_profile" }, { label: "代理调度", path: "/proxy_pool" }, { label: "凭证管理", path: "/cookie_vault" }, { label: "频控策略", path: "/rate_limiter" }, { label: "抽取模板", path: "/extract_rule" }, { label: "采集任务", path: "/crawl_task" }, { label: "RPA脚本库", path: "/rpa_script" }, { label: "采集流水线", path: "/data_pipeline" }, { label: "采集仓储", path: "/result_store" }, { label: "反爬对抗", path: "/anti_block" }, { label: "质量审计", path: "/quality_check" }, { label: "增量同步", path: "/delta_sync" }, { label: "采集监控", path: "/log_monitor" }, { label: "模板市场", path: "/template_mgr" }, { label: "数据分发", path: "/export_hub" }, { label: "定时调度", path: "/scheduler" }, { label: "解析引擎", path: "/parse_engine" }, { label: "标准化解析", path: "/std_parse" }, { label: "重试队列", path: "/retry_queue" }]
</script>
