<template>
  <el-row :gutter="16">
    <el-col :span="24">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="user-header">
            <div class="user-title">
              <div>用户管理</div>
              <div class="card-subtitle">仅展示普通用户账号与声纹状态</div>
            </div>
            <div class="user-actions">
              <el-button plain @click="onUserRefresh" :loading="usersLoading">
                刷新
              </el-button>
              <el-button type="primary" @click="onCreateUser">新建用户</el-button>
            </div>
          </div>
          <el-form :inline="true" :model="userFilters" size="small" class="user-filter-form">
            <el-form-item label="关键词">
              <el-input v-model="userFilters.q" placeholder="用户名 / 姓名 / 手机 / 邮箱" clearable />
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="userFilters.is_active" clearable placeholder="全部">
                <el-option label="启用" value="true" />
                <el-option label="禁用" value="false" />
              </el-select>
            </el-form-item>
            <el-form-item label="声纹">
              <el-select v-model="userFilters.has_voiceprint" clearable placeholder="全部">
                <el-option label="已录入" value="true" />
                <el-option label="未录入" value="false" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="onUserSearch">查询</el-button>
              <el-button @click="onUserReset">重置</el-button>
            </el-form-item>
          </el-form>
          <div class="user-batch">
            <div class="user-batch-info">已选 {{ selectedUserIds.length }} 个</div>
            <div class="user-batch-actions">
              <el-button size="small" :disabled="!selectedUserIds.length" @click="onBatchToggle(true)">
                批量启用
              </el-button>
              <el-button size="small" :disabled="!selectedUserIds.length" @click="onBatchToggle(false)">
                批量禁用
              </el-button>
              <el-button size="small" :disabled="!selectedUserIds.length" @click="onBatchClearVoiceprint">
                批量清理声纹
              </el-button>
              <el-button size="small" :disabled="!selectedUserIds.length" @click="onBatchResetPassword">
                批量重置密码
              </el-button>
              <el-button
                size="small"
                type="danger"
                plain
                :disabled="!selectedUserIds.length"
                @click="onBatchDelete"
              >
                批量删除
              </el-button>
            </div>
          </div>
        </template>
        <el-table
          :data="users"
          border
          style="width: 100%"
          size="small"
          row-key="id"
          v-loading="usersLoading"
          @selection-change="onUserSelectionChange"
        >
          <el-table-column type="selection" width="44" />
          <el-table-column prop="username" label="用户名" width="140" />
          <el-table-column prop="full_name" label="姓名" width="120" />
          <el-table-column prop="phone" label="联系电话" width="140" />
          <el-table-column prop="email" label="邮箱" min-width="180" />
          <el-table-column prop="department" label="部门" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'danger'" effect="light">
                {{ row.is_active ? "启用" : "禁用" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="声纹" width="110">
            <template #default="{ row }">
              <el-tag :type="row.has_voiceprint ? 'success' : 'info'" effect="light">
                {{ row.has_voiceprint ? "已录入" : "未录入" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="注册时间" width="185">
            <template #default="{ row }">
              <span class="time-text">{{ formatDateTime(row.date_joined) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="最近登录" width="185">
            <template #default="{ row }">
              <span class="time-text">{{ formatDateTime(row.last_login) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="240">
            <template #default="{ row }">
              <div class="user-action-stack">
                <el-button size="small" @click="onEditUser(row)">编辑</el-button>
                <el-button size="small" @click="onResetPassword(row)">重置密码</el-button>
                <el-button size="small" plain @click="onResetVoiceprint(row)">清理声纹</el-button>
                <el-button size="small" type="danger" plain @click="onDeleteUser(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-col>
  </el-row>
  <el-row style="margin-top: 8px">
    <el-col :span="24" style="text-align: right">
      <el-pagination
        layout="prev, pager, next, jumper"
        background
        :page-size="usersPageSize"
        :current-page="usersPage"
        :total="usersTotal"
        @current-change="onUserPageChange"
      />
    </el-col>
  </el-row>
</template>

<script setup>
defineProps({
  users: { type: Array, required: true },
  usersTotal: { type: Number, required: true },
  usersPage: { type: Number, required: true },
  usersPageSize: { type: Number, required: true },
  usersLoading: { type: Boolean, required: true },
  userFilters: { type: Object, required: true },
  selectedUserIds: { type: Array, required: true },
  formatDateTime: { type: Function, required: true },
  onUserRefresh: { type: Function, required: true },
  onCreateUser: { type: Function, required: true },
  onUserSearch: { type: Function, required: true },
  onUserReset: { type: Function, required: true },
  onBatchToggle: { type: Function, required: true },
  onBatchClearVoiceprint: { type: Function, required: true },
  onBatchResetPassword: { type: Function, required: true },
  onBatchDelete: { type: Function, required: true },
  onUserSelectionChange: { type: Function, required: true },
  onUserPageChange: { type: Function, required: true },
  onEditUser: { type: Function, required: true },
  onResetPassword: { type: Function, required: true },
  onResetVoiceprint: { type: Function, required: true },
  onDeleteUser: { type: Function, required: true }
});
</script>
