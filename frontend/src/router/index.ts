import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
const SiteProfile = () => import('@/views/site_profile/index.vue')
const ProxyPool = () => import('@/views/proxy_pool/index.vue')
const CookieVault = () => import('@/views/cookie_vault/index.vue')
const RateLimiter = () => import('@/views/rate_limiter/index.vue')
const ExtractRule = () => import('@/views/extract_rule/index.vue')
const CrawlTask = () => import('@/views/crawl_task/index.vue')
const RpaScript = () => import('@/views/rpa_script/index.vue')
const DataPipeline = () => import('@/views/data_pipeline/index.vue')
const ResultStore = () => import('@/views/result_store/index.vue')
const AntiBlock = () => import('@/views/anti_block/index.vue')
const QualityCheck = () => import('@/views/quality_check/index.vue')
const DeltaSync = () => import('@/views/delta_sync/index.vue')
const LogMonitor = () => import('@/views/log_monitor/index.vue')
const TemplateMgr = () => import('@/views/template_mgr/index.vue')
const ExportHub = () => import('@/views/export_hub/index.vue')
const Scheduler = () => import('@/views/scheduler/index.vue')
const ParseEngine = () => import('@/views/parse_engine/index.vue')
const RetryQueue = () => import('@/views/retry_queue/index.vue')
const StdParse = () => import('@/views/std_parse/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    { path: '/site_profile', name: 'site_profile', component: SiteProfile },
    { path: '/proxy_pool', name: 'proxy_pool', component: ProxyPool },
    { path: '/cookie_vault', name: 'cookie_vault', component: CookieVault },
    { path: '/rate_limiter', name: 'rate_limiter', component: RateLimiter },
    { path: '/extract_rule', name: 'extract_rule', component: ExtractRule },
    { path: '/crawl_task', name: 'crawl_task', component: CrawlTask },
    { path: '/rpa_script', name: 'rpa_script', component: RpaScript },
    { path: '/data_pipeline', name: 'data_pipeline', component: DataPipeline },
    { path: '/result_store', name: 'result_store', component: ResultStore },
    { path: '/anti_block', name: 'anti_block', component: AntiBlock },
    { path: '/quality_check', name: 'quality_check', component: QualityCheck },
    { path: '/delta_sync', name: 'delta_sync', component: DeltaSync },
    { path: '/log_monitor', name: 'log_monitor', component: LogMonitor },
    { path: '/template_mgr', name: 'template_mgr', component: TemplateMgr },
    { path: '/export_hub', name: 'export_hub', component: ExportHub },
    { path: '/scheduler', name: 'scheduler', component: Scheduler },
    { path: '/parse_engine', name: 'parse_engine', component: ParseEngine },
    { path: '/retry_queue', name: 'retry_queue', component: RetryQueue },
    { path: '/std_parse', name: 'std_parse', component: StdParse },
  ],
})

export default router
