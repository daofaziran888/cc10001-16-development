<template>
  <section class="page std-parse" data-module="std_parse">
    <header class="page-head">
      <div>
        <h2>标准化解析</h2>
        <p class="page-desc">
          读取原始采集页数据、已部署解析配置与抽取规则，按配置版本解析字段并记录规则来源，
          生成标准化解析结果数据集与结果批次记录。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-parse" type="button" @click="openParse">
          发起标准化解析
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="tabs" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        :data-testid="`tab-${tab.key}`"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 原始采集页 -->
    <div v-if="activeTab === 'pages'">
      <form class="filter-bar" @submit.prevent="reloadRawPages">
        <label class="filter-item">
          <span>页面编号</span>
          <input v-model="pageKeyword" data-testid="page-keyword" placeholder="按页面编号检索" />
        </label>
        <button class="btn" data-testid="page-query" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetPageFilters">重置条件</button>
      </form>
      <table class="data-table" data-testid="raw-page-table">
        <thead>
          <tr>
            <th>页面编号</th>
            <th>目标站点</th>
            <th>页面类型</th>
            <th>来源URL</th>
            <th>采集任务</th>
            <th>采集时间</th>
            <th>内容摘要</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rawPageRows" :key="String(row.id)" :data-testid="`raw-page-row-${row.id}`">
            <td>{{ row.页面编号 }}</td>
            <td>{{ row.目标站点 }}</td>
            <td>{{ row.页面类型 }}</td>
            <td>{{ row.来源URL }}</td>
            <td>{{ row.采集任务 }}</td>
            <td>{{ row.采集时间 }}</td>
            <td>{{ row.内容摘要 }}</td>
            <td>
              <button
                class="link"
                type="button"
                :data-testid="`raw-page-parse-${row.id}`"
                @click="parseFromPage(row)"
              >
                用该页面解析
              </button>
            </td>
          </tr>
          <tr v-if="!rawPageRows.length">
            <td colspan="8" class="empty-state">暂无原始采集页数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 标准化结果数据集 -->
    <div v-else-if="activeTab === 'datasets'">
      <form class="filter-bar" @submit.prevent="reloadDatasets">
        <label class="filter-item">
          <span>数据集 / 页面 / 配置</span>
          <input v-model="datasetKeyword" data-testid="dataset-keyword" placeholder="按数据集编号、页面编号或配置编号检索" />
        </label>
        <label class="filter-item">
          <span>配置版本</span>
          <input v-model="datasetVersion" data-testid="dataset-version" placeholder="如 v3" />
        </label>
        <button class="btn" data-testid="dataset-query" type="submit">查询</button>
        <button class="btn ghost" data-testid="dataset-reset" type="button" @click="resetDatasetFilters">重置条件</button>
      </form>

      <table class="data-table" data-testid="dataset-table">
        <thead>
          <tr>
            <th>数据集编号</th>
            <th>来源页面</th>
            <th>页面类型</th>
            <th>配置版本</th>
            <th>批次编号</th>
            <th>字段状态</th>
            <th>规则来源</th>
            <th>生成时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in datasets"
            :key="String(row.id)"
            :data-testid="`dataset-row-${row.id}`"
            :data-batch-status="row.batch_status"
            :class="{ selected: selectedDatasetId === row.id }"
          >
            <td>{{ row.数据集编号 }}</td>
            <td>{{ row.页面编号 }}</td>
            <td>{{ row.page_type }}</td>
            <td>{{ row.config_code }} / {{ row.config_version }}</td>
            <td>{{ row.result_batch_code }}</td>
            <td>
              <span
                v-for="(count, status) in row.field_status_counts"
                v-show="count"
                :key="status"
                class="status-chip"
                :class="`field-${status}`"
                >{{ status }} {{ count }}</span
              >
            </td>
            <td class="rule-source-cell" :title="row.source_summary">{{ row.source_summary }}</td>
            <td>{{ row.created_at }}</td>
            <td>
              <button class="link" type="button" :data-testid="`dataset-detail-${row.id}`" @click="selectDataset(row)">
                查看解析结果
              </button>
            </td>
          </tr>
          <tr v-if="!datasets.length">
            <td colspan="9" class="empty-state">暂无标准化解析结果，可先对原始采集页发起解析</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 结果批次 -->
    <div v-else-if="activeTab === 'batches'">
      <table class="data-table" data-testid="batch-table">
        <thead>
          <tr>
            <th>批次编号</th>
            <th>数据集编号</th>
            <th>配置版本</th>
            <th>冲突策略</th>
            <th>字段状态</th>
            <th>待确认 / 失败</th>
            <th>规则来源</th>
            <th>批次状态</th>
            <th>生成时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in batches" :key="String(row.id)" :data-testid="`batch-row-${row.id}`" :data-status="row.status">
            <td>{{ row.批次编号 }}</td>
            <td>{{ row.dataset_code }}</td>
            <td>{{ row.config_code }} / {{ row.config_version }}</td>
            <td>{{ policyLabel(row.conflict_policy) }}</td>
            <td>
              <span
                v-for="(count, status) in row.field_status_counts"
                v-show="count"
                :key="status"
                class="status-chip"
                :class="`field-${status}`"
                >{{ status }} {{ count }}</span
              >
            </td>
            <td>{{ row.pending_fields }} / {{ row.failed_fields }}</td>
            <td class="rule-source-cell" :title="row.规则来源">{{ row.规则来源 }}</td>
            <td>{{ row.status }}</td>
            <td>{{ row.created_at }}</td>
          </tr>
          <tr v-if="!batches.length">
            <td colspan="9" class="empty-state">暂无标准化解析结果批次</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 字段结果与规则来源 -->
    <div v-else>
      <div v-if="!selectedDataset" class="empty-state detail-empty">
        请先在“标准化结果数据集”里选择一条记录查看字段解析结果。
      </div>
      <template v-else>
        <article class="detail-card" data-testid="dataset-detail">
          <header class="detail-head">
            <div>
              <strong>{{ selectedDataset.数据集编号 }}</strong>
              <span class="muted">
                来源页面 {{ selectedDataset.页面编号 }} · 配置 {{ selectedDataset.config_code }} /
                {{ selectedDataset.config_version }} · 批次 {{ selectedDataset.result_batch_code }}
              </span>
            </div>
            <button class="btn ghost" type="button" @click="activeTab = 'datasets'">返回数据集列表</button>
          </header>
          <dl class="detail-grid">
            <div><dt>来源 URL</dt><dd>{{ selectedDataset.source_url || '—' }}</dd></div>
            <div><dt>页面类型</dt><dd>{{ selectedDataset.page_type }}</dd></div>
            <div><dt>冲突策略</dt><dd>{{ policyLabel(selectedDataset.conflict_policy) }}</dd></div>
            <div><dt>字段状态分布</dt><dd>{{ statusSummary(selectedDataset.field_status_counts) }}</dd></div>
            <div><dt>批次状态</dt><dd>{{ selectedDataset.batch_status }}</dd></div>
            <div><dt>校验摘要</dt><dd>{{ selectedDataset.checksum }}</dd></div>
          </dl>
          <div v-if="lineage" class="lineage" data-testid="dataset-lineage">
            <span class="lineage-label">跨模块链路</span>
            数据集 {{ lineage.dataset?.数据集编号 }} → 解析批次 {{ lineage.batch?.批次编号 }}（{{ lineage.batch?.status }}）
            → 采集仓储批次 {{ lineage.result_store?.批次编号 || '未写入' }}
            <span v-if="lineage.result_store?.规则来源"> · 仓储规则来源：{{ lineage.result_store.规则来源 }}</span>
          </div>
        </article>

        <table class="data-table" data-testid="record-table">
          <thead>
            <tr>
              <th>字段</th>
              <th>字段路径</th>
              <th>解析值</th>
              <th>字段状态</th>
              <th>配置版本</th>
              <th>命中规则</th>
              <th>规则来源</th>
              <th>校验结果</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="record in records"
              :key="String(record.id)"
              :data-testid="`record-row-${record.id}`"
              :data-field-status="record.field_status"
            >
              <td>{{ record.field_name }}</td>
              <td>{{ record.field_path }}</td>
              <td>
                <span v-if="record.value !== null && record.value !== ''">{{ record.value }}</span>
                <span v-else class="muted">—</span>
                <ul v-if="record.candidates && record.candidates.length" class="candidate-list">
                  <li v-for="candidate in record.candidates" :key="candidate.rule_id">
                    候选 {{ candidate.rule_code }}@{{ candidate.rule_version }}：
                    {{ candidate.value }}
                  </li>
                </ul>
              </td>
              <td>
                <span class="status-chip" :class="`field-${record.field_status}`">{{ record.field_status }}</span>
                <span v-if="record.conflict" class="conflict-flag">冲突</span>
              </td>
              <td>{{ record.config_version }}</td>
              <td>{{ record.applied_rule_code || '—' }}{{ record.applied_rule_version ? `@${record.applied_rule_version}` : '' }}</td>
              <td>
                <ul class="rule-hit-list">
                  <li v-for="hit in record.rule_hits" :key="`${hit.rule_id}-${hit.status}`">
                    {{ hit.rule_code }}@{{ hit.rule_version || '-' }}（优先级 {{ hit.priority }}）—
                    {{ hit.status }}
                    <span v-if="hit.note" class="muted">：{{ hit.note }}</span>
                  </li>
                </ul>
              </td>
              <td>
                <span :class="record.validation?.passed ? 'pass-text' : 'fail-text'">
                  {{ record.validation?.passed ? '通过' : '未通过' }}
                </span>
                <span class="muted">{{ record.validation?.message }}</span>
                <span v-if="record.validation?.default_used" class="muted">（使用缺省值）</span>
              </td>
            </tr>
            <tr v-if="!records.length">
              <td colspan="8" class="empty-state">该数据集没有字段结果</td>
            </tr>
          </tbody>
        </table>
      </template>
    </div>

    <!-- 发起解析 -->
    <div v-if="showParse" class="modal-backdrop" data-testid="parse-modal">
      <form class="modal" @submit.prevent="submitParse">
        <h3>发起标准化解析</h3>
        <label class="create-field">
          <span>原始采集页</span>
          <select v-model="parseValues.raw_page_id" data-testid="parse-page" @change="reloadCandidates">
            <option :value="0" disabled>请选择原始采集页</option>
            <option v-for="page in rawPages" :key="page.id" :value="page.id">
              {{ page.页面编号 }} · {{ page.页面类型 }} · {{ page.来源URL }}
            </option>
          </select>
        </label>
        <label class="create-field">
          <span>已部署解析配置</span>
          <select v-model="parseValues.config_id" data-testid="parse-config" @change="reloadPreview">
            <option :value="0" disabled>请选择已部署解析配置</option>
            <option v-for="config in configs" :key="config.id" :value="config.id">
              {{ config.配置编号 }} / 版本 {{ config.版本号 }} · {{ config.页面类型 }}
            </option>
          </select>
        </label>
        <div v-if="previewFields.length" class="preview-rules" data-testid="rule-preview">
          <span class="preview-title">命中规则预览（按部署时间倒序）</span>
          <div v-for="field in previewFields" :key="field.field_path" class="preview-row">
            <span class="preview-field">{{ field.field_name }} · {{ field.field_path }}</span>
            <span
              v-for="rule in field.rules"
              :key="rule.rule_id"
              class="status-chip"
              :class="{ 'rule-conflict': hasConflict(field.rules) }"
            >
              {{ rule.rule_code }}@{{ rule.rule_version || '-' }} 优先级 {{ rule.priority }}
            </span>
            <span v-if="!field.rules.length" class="muted">无已发布规则</span>
            <span v-if="hasConflict(field.rules)" class="conflict-flag">同优先级冲突</span>
          </div>
        </div>
        <label class="create-field">
          <span>冲突规则处理策略</span>
          <select v-model="parseValues.conflict_policy" data-testid="parse-policy">
            <option v-for="policy in policies" :key="policy.key" :value="policy.key">
              {{ policy.key }} · {{ policy.description }}
            </option>
          </select>
        </label>
        <p class="muted parse-hint">
          同一字段存在两条同优先级且提取值不同的已发布规则时，所选策略决定字段状态；
          未采用或候选规则都会记录在结果里，不会静默覆盖字段。
        </p>
        <div class="page-actions">
          <button class="btn" type="button" @click="showParse = false">取消</button>
          <button class="btn primary" data-testid="submit-parse" type="submit" :disabled="parsing">
            {{ parsing ? '解析中…' : '开始解析' }}
          </button>
        </div>
      </form>
    </div>

    <footer class="page-foot">
      <span>
        共 {{ activeTab === 'batches' ? batches.length : datasets.length }} 条
        {{ activeTab === 'batches' ? '结果批次' : '结果数据集' }}记录
      </span>
      <span v-if="noticeMessage" data-testid="parse-notice" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text" data-testid="parse-error">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/std_parse'

const tabs = [
  { key: 'pages', label: '原始采集页' },
  { key: 'datasets', label: '标准化结果数据集' },
  { key: 'batches', label: '结果批次' },
  { key: 'records', label: '字段结果与规则来源' },
]

const activeTab = ref('datasets')
const datasets = ref<Row[]>([])
const batches = ref<Row[]>([])
const records = ref<Row[]>([])
const datasetTotal = ref(0)
const selectedDatasetId = ref<number | null>(null)
const datasetKeyword = ref('')
const datasetVersion = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')

const rawPages = ref<Row[]>([])
const rawPageRows = ref<Row[]>([])
const pageKeyword = ref('')
const configs = ref<Row[]>([])
const previewFields = ref<Row[]>([])
const policies = ref<{ key: string; description: string }[]>([])
const showParse = ref(false)
const parsing = ref(false)
const parseValues = ref({ raw_page_id: 0, config_id: 0, conflict_policy: 'latest_deploy' })

const selectedDataset = computed(
  () => datasets.value.find((row) => row.id === selectedDatasetId.value) ?? null,
)
const lineage = ref<Row | null>(null)

const stats = computed(() => {
  const pending = datasets.value.reduce((sum, row) => sum + Number(row.pending_fields || 0), 0)
  const conflicts = datasets.value.reduce((sum, row) => sum + Number(row.conflict_fields || 0), 0)
  return [
    { label: '结果数据集', value: datasetTotal.value },
    { label: '待确认字段', value: pending },
    { label: '冲突字段', value: conflicts },
  ]
})

function policyLabel(key: string) {
  return policies.value.find((item) => item.key === key)?.description ?? key
}

function statusSummary(counts: Record<string, number> | undefined) {
  if (!counts) return '—'
  return Object.entries(counts)
    .filter(([, count]) => count)
    .map(([status, count]) => `${status} ${count}`)
    .join(' / ')
}

function decorate(rows: Row[]) {
  return rows.map((row) => ({
    ...row,
    batch_status: row.batch_status ?? row.status ?? '',
    source_summary: row.source_summary ?? row.规则来源 ?? '',
  }))
}

async function reloadDatasets() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (datasetKeyword.value.trim()) query.set('keyword', datasetKeyword.value.trim())
  if (datasetVersion.value.trim()) query.set('config_version', datasetVersion.value.trim())
  query.set('size', '50')
  try {
    const response = await request(`${ENDPOINT}/datasets?${query.toString()}`)
    if (!response.ok) throw new Error('标准化结果数据集读取失败')
    const payload = await response.json()
    const items: Row[] = decorate(payload.items ?? [])
    datasets.value = items
    datasetTotal.value = payload.total ?? items.length
    if (selectedDatasetId.value && !items.some((row) => row.id === selectedDatasetId.value)) {
      selectedDatasetId.value = null
      records.value = []
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '标准化结果数据集读取失败'
  }
}

async function reloadBatches() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/batches?size=50`)
    if (!response.ok) throw new Error('标准化结果批次读取失败')
    const payload = await response.json()
    batches.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '标准化结果批次读取失败'
  }
}

async function selectDataset(row: Row) {
  selectedDatasetId.value = row.id
  records.value = []
  lineage.value = null
  errorMessage.value = ''
  try {
    const [recordResponse, lineageResponse] = await Promise.all([
      request(`${ENDPOINT}/datasets/${row.id}/records`),
      request(`${ENDPOINT}/datasets/${row.id}/lineage`),
    ])
    if (!recordResponse.ok) throw new Error('字段解析结果读取失败')
    records.value = await recordResponse.json()
    lineage.value = lineageResponse.ok ? await lineageResponse.json() : null
    activeTab.value = 'records'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '字段解析结果读取失败'
  }
}

async function reloadRawPages() {
  errorMessage.value = ''
  const query = new URLSearchParams({ size: '50' })
  if (pageKeyword.value.trim()) query.set('keyword', pageKeyword.value.trim())
  try {
    const response = await request(`${ENDPOINT}/raw-pages?${query.toString()}`)
    if (!response.ok) throw new Error('原始采集页读取失败')
    const payload = await response.json()
    rawPageRows.value = payload.items ?? []
    rawPages.value = rawPageRows.value
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '原始采集页读取失败'
  }
}

function resetPageFilters() {
  pageKeyword.value = ''
  void reloadRawPages()
}

async function parseFromPage(row: Row) {
  showParse.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  if (!policies.value.length) await loadOptions()
  parseValues.value = {
    raw_page_id: row.id,
    config_id: 0,
    conflict_policy: policies.value.length ? policies.value[0].key : 'latest_deploy',
  }
  previewFields.value = []
  await reloadCandidates()
}

async function switchTab(key: string) {
  activeTab.value = key
  if (key === 'batches') await reloadBatches()
  if (key === 'pages') await reloadRawPages()
}

function resetDatasetFilters() {
  datasetKeyword.value = ''
  datasetVersion.value = ''
  void reloadDatasets()
}

async function loadOptions() {
  try {
    const [pageResponse, policyResponse] = await Promise.all([
      request(`${ENDPOINT}/raw-pages?size=50`),
      request(`${ENDPOINT}/policies`),
    ])
    if (pageResponse.ok) {
      const payload = await pageResponse.json()
      rawPages.value = payload.items ?? []
    }
    if (policyResponse.ok) {
      const payload = await policyResponse.json()
      policies.value = payload.items ?? []
    }
  } catch {
    // 选项加载失败时仍允许打开弹窗，提交时会给出错误说明。
  }
}

async function reloadCandidates() {
  parseValues.value.config_id = 0
  configs.value = []
  previewFields.value = []
  if (!parseValues.value.raw_page_id) return
  try {
    const response = await request(`${ENDPOINT}/deployed-configs?raw_page_id=${parseValues.value.raw_page_id}`)
    if (!response.ok) throw new Error('已部署解析配置读取失败')
    configs.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '已部署解析配置读取失败'
  }
}

async function reloadPreview() {
  previewFields.value = []
  if (!parseValues.value.raw_page_id || !parseValues.value.config_id) return
  try {
    const response = await request(
      `${ENDPOINT}/preview?raw_page_id=${parseValues.value.raw_page_id}&config_id=${parseValues.value.config_id}`,
    )
    if (!response.ok) return
    const payload = await response.json()
    previewFields.value = payload.fields ?? []
  } catch {
    // 预览失败只影响提示，不阻塞解析。
  }
}

function hasConflict(rules: Row[]) {
  if (rules.length < 2) return false
  const topPriority = Math.max(...rules.map((rule) => Number(rule.priority)))
  return rules.filter((rule) => Number(rule.priority) === topPriority).length > 1
}

async function openParse() {
  showParse.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  parseValues.value = {
    raw_page_id: 0,
    config_id: 0,
    conflict_policy: policies.value.length ? policies.value[0].key : 'latest_deploy',
  }
  configs.value = []
  previewFields.value = []
  if (!rawPages.value.length) await loadOptions()
}

async function submitParse() {
  if (!parseValues.value.raw_page_id || !parseValues.value.config_id) {
    errorMessage.value = '请先选择原始采集页与已部署解析配置'
    return
  }
  parsing.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/run`, {
      method: 'POST',
      body: JSON.stringify(parseValues.value),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.detail || payload.message || '标准化解析失败')
    }
    showParse.value = false
    noticeMessage.value = payload.message ?? '标准化解析完成'
    await reloadDatasets()
    if (payload.dataset) {
      await selectDataset(payload.dataset)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '标准化解析失败'
  } finally {
    parsing.value = false
  }
}

onMounted(async () => {
  await Promise.all([reloadDatasets(), loadOptions()])
})
</script>

<style scoped>
.tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}
.tab {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 6px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 13px;
}
.tab.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.status-chip {
  display: inline-block;
  padding: 1px 6px;
  margin: 0 4px 2px 0;
  border-radius: 4px;
  font-size: 12px;
  background: #eef2f7;
}
.field-已解析 { background: #e7f6ec; color: #157347; }
.field-待确认 { background: #fff4d6; color: #a16207; }
.field-校验失败 { background: #fde8e8; color: #b42318; }
.field-缺失 { background: #f1f1f4; color: #475569; }
.field-缺规则 { background: #ede9fe; color: #6d28d9; }
.conflict-flag {
  margin-left: 4px;
  font-size: 12px;
  color: #b42318;
}
.rule-source-cell {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rule-hit-list,
.candidate-list {
  margin: 2px 0 0;
  padding-left: 16px;
  font-size: 12px;
  color: #334155;
}
.detail-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.detail-head .muted { margin-left: 8px; font-size: 12px; }
.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 0;
}
.detail-grid dt { font-size: 12px; color: var(--muted); }
.detail-grid dd { margin: 0 0 4px; font-size: 13px; }
.detail-empty { padding: 40px 0; background: #fff; border: 1px solid var(--border); border-radius: 8px; }
.muted { color: var(--muted); font-size: 12px; }
.pass-text { color: #157347; font-size: 12px; margin-right: 4px; }
.fail-text { color: #b42318; font-size: 12px; margin-right: 4px; }
.notice-text { color: #157347; }
.lineage {
  margin-top: 10px;
  padding: 8px 10px;
  background: #f5f8ff;
  border: 1px solid #dbe6ff;
  border-radius: 6px;
  font-size: 12px;
  color: #1f3a8a;
}
.lineage-label {
  font-weight: 600;
  margin-right: 6px;
}
.parse-hint { margin: 4px 0 12px; }
.create-field select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
}
.preview-rules {
  border: 1px dashed var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  margin: 0 0 12px;
  max-height: 200px;
  overflow-y: auto;
}
.preview-title { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.preview-row { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-bottom: 4px; font-size: 12px; }
.preview-field { min-width: 150px; }
.status-chip.rule-conflict { background: #fde8e8; color: #b42318; }
tr.selected { background: #eef4ff; }
</style>
