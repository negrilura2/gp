<template>
  <el-card shadow="never" class="panel-card">
    <template #header>
      <div class="settings-header">
        <div>
          <div class="settings-title">管理员列表</div>
          <div class="card-subtitle">进入时需要验证高层密码</div>
        </div>
        <div class="settings-actions">
          <el-button :disabled="!adminListUnlocked" @click="onAdminListRefresh">刷新</el-button>
          <el-button type="primary" :disabled="!adminListUnlocked" @click="onCreateAdmin">
            新建管理员
          </el-button>
        </div>
      </div>
    </template>
    <div v-if="adminListUnlocked">
      <el-form :inline="true" :model="adminFilters" size="small" class="user-filter-form">
        <el-form-item label="关键词">
          <el-input v-model="adminFilters.q" placeholder="用户名 / 姓名 / 手机 / 邮箱" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="adminFilters.is_active" clearable placeholder="全部">
            <el-option label="启用" value="true" />
            <el-option label="禁用" value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onAdminSearch">查询</el-button>
          <el-button @click="onAdminReset">重置</el-button>
        </el-form-item>
      </el-form>
      <div class="user-batch">
        <div class="user-batch-info">已选 {{ selectedAdminIds.length }} 个</div>
        <div class="user-batch-actions">
          <el-button size="small" :disabled="!selectedAdminIds.length" @click="onAdminBatchToggle(true)">
            批量启用
          </el-button>
          <el-button size="small" :disabled="!selectedAdminIds.length" @click="onAdminBatchToggle(false)">
            批量禁用
          </el-button>
          <el-button size="small" :disabled="!selectedAdminIds.length" @click="onAdminBatchResetPassword">
            批量重置密码
          </el-button>
        </div>
      </div>
      <el-table
        :data="adminList"
        size="small"
        stripe
        :loading="adminListLoading"
        @selection-change="onAdminSelectionChange"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column prop="username" label="账号" min-width="120" />
        <el-table-column prop="full_name" label="姓名" min-width="120" />
        <el-table-column prop="phone" label="联系电话" min-width="140" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="department" label="部门" min-width="120" />
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? "启用" : "禁用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" min-width="160">
          <template #default="{ row }">
            {{ row.last_login ? formatDateTime(row.last_login) : "--" }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="160">
          <template #default="{ row }">
            {{ row.date_joined ? formatDateTime(row.date_joined) : "--" }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="220">
          <template #default="{ row }">
            <div class="user-action-stack">
              <el-button size="small" @click="onEditAdmin(row)">编辑</el-button>
              <el-button size="small" @click="onResetAdminPassword(row)">重置密码</el-button>
              <el-button size="small" plain @click="onAdminToggle(row)">
                {{ row.is_active ? "禁用" : "启用" }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-empty v-else description="进入时需要验证高层密码" />
  </el-card>
</template>

<script setup>
defineProps({
  adminListUnlocked: { type: Boolean, required: true },
  adminFilters: { type: Object, required: true },
  selectedAdminIds: { type: Array, required: true },
  adminList: { type: Array, required: true },
  adminListLoading: { type: Boolean, required: true },
  formatDateTime: { type: Function, required: true },
  onAdminListRefresh: { type: Function, required: true },
  onCreateAdmin: { type: Function, required: true },
  onAdminSearch: { type: Function, required: true },
  onAdminReset: { type: Function, required: true },
  onAdminBatchToggle: { type: Function, required: true },
  onAdminBatchResetPassword: { type: Function, required: true },
  onAdminSelectionChange: { type: Function, required: true },
  onEditAdmin: { type: Function, required: true },
  onResetAdminPassword: { type: Function, required: true },
  onAdminToggle: { type: Function, required: true }
});
</script>
