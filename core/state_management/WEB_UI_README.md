# State Management Web UI 使用说明

## 概述

State Management System 现已集成 Web UI 管理界面，提供图形化的配置和管理功能。

## 功能特性

### 已实现功能
- ✅ 用户认证系统（登录/登出）
- ✅ 基于角色的权限控制（管理员/普通用户）
- ✅ 仪表板（系统概览）
- ✅ 分析配置管理（CRUD）
- ✅ 路由规则管理（CRUD）
- ✅ MongoDB 实例管理（CRUD）
- ✅ 节点监控
- ✅ 用户管理（仅管理员）
- ✅ 响应式设计（Tailwind CSS）
- ✅ 表单验证和 CSRF 保护

### 技术栈
- **后端**: Flask 3.0 + Flask-Login + Flask-WTF + Flask-Bcrypt
- **前端**: Tailwind CSS + Alpine.js
- **数据库**: MongoDB
- **认证**: 基于会话的认证 + bcrypt 密码加密

## 安装步骤

### 1. 安装依赖

```bash
cd core/state_management
pip install -r requirements.txt
```

新增的依赖包括:
- Flask-Login==0.6.3
- Flask-WTF==1.2.1
- Flask-Bcrypt==1.0.1
- WTForms==3.1.1

### 2. 创建管理员账户

首次使用需要创建管理员账户：

```bash
# 交互式创建（推荐）
python init_admin.py

# 或者使用命令行参数
python init_admin.py --username admin --password your_password --email admin@example.com
```

### 3. 启动应用

```bash
# 开发模式
python app.py

# 或使用 Gunicorn（生产环境）
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### 4. 访问 Web UI

打开浏览器访问：
- **Web UI**: http://localhost:8000/
- **API 文档**: http://localhost:8000/api

## 使用指南

### 登录
1. 访问 http://localhost:8000/
2. 使用管理员账户登录
3. 默认用户名: `admin`（如果使用默认参数创建）

### 仪表板
登录后自动跳转到仪表板，显示：
- 系统统计信息（配置、规则、实例、节点数量）
- 最近更新的配置列表
- 在线节点列表

### 分析配置管理
**路径**: `/configs`

**功能**:
- 查看所有分析配置
- 创建新配置（管理员）
- 编辑配置（管理员）
- 删除配置（管理员）
- 上传模型文件（管理员）
- 启用/禁用配置（管理员）

**权限**:
- 普通用户：只读查看
- 管理员：完全访问

### 路由规则管理
**路径**: `/routing`

**功能**:
- 查看所有路由规则
- 创建新规则（管理员）
- 编辑规则（管理员）
- 删除规则（管理员）
- 测试规则匹配（管理员）

**规则示例**:
```json
{
  "conditions": {
    "machine_type": "pump",
    "location": "factory_A"
  },
  "actions": [
    {
      "analysis_method_id": "method_001",
      "config_id": "config_uuid",
      "mongodb_instance": "instance_uuid"
    }
  ]
}
```

### MongoDB 实例管理
**路径**: `/instances`

**功能**:
- 查看所有 MongoDB 实例
- 添加新实例（管理员）
- 编辑实例配置（管理员）
- 删除实例（管理员）
- 测试连接（管理员）

**注意**: 密码在列表页面中隐藏，仅在编辑页面可见。

### 节点监控
**路径**: `/nodes`

**功能**:
- 查看所有注册节点
- 查看节点状态（在线/离线）
- 查看节点详情（能力、任务数）
- 删除（注销）节点（管理员）

**节点状态**:
- 在线：最近 60 秒内有心跳
- 离线：超过 60 秒未心跳

### 用户管理（仅管理员）
**路径**: `/users`

**功能**:
- 查看所有用户
- 创建新用户
- 编辑用户信息（角色、邮箱、激活状态）
- 停用用户
- 重置密码

**角色说明**:
- **管理员**: 完全访问权限，可以管理所有资源和用户
- **普通用户**: 只读权限，可以查看配置和监控信息

### 个人设置
**修改密码**: `/profile/change-password`

## 目录结构

```
core/state_management/
├── app.py                          # 主应用（已更新集成 Web UI）
├── init_admin.py                   # 管理员初始化脚本
├── requirements.txt                # 依赖列表（已更新）
├── auth/                           # 认证模块
│   ├── __init__.py
│   ├── routes.py                   # 登录/登出路由
│   └── decorators.py               # 权限装饰器
├── forms/                          # 表单模块
│   ├── auth_forms.py              # 认证表单
│   └── config_forms.py            # 配置表单
├── views/                          # Web UI 视图
│   ├── dashboard.py               # 仪表板
│   ├── config_views.py            # 配置管理
│   ├── routing_views.py           # 路由规则
│   ├── instance_views.py          # 实例管理
│   ├── node_views.py              # 节点监控
│   └── user_views.py              # 用户管理
├── models/
│   └── user.py                    # 用户模型（新增）
├── templates/                      # HTML 模板
│   ├── base.html                  # 基础模板
│   ├── dashboard.html             # 仪表板
│   ├── partials/
│   │   └── sidebar_nav.html       # 侧边栏导航
│   ├── auth/
│   │   └── login.html             # 登录页面
│   ├── configs/
│   │   ├── list.html              # 配置列表
│   │   └── edit.html              # 配置编辑
│   └── ...                        # 其他模板
└── static/
    └── (Tailwind CSS 和 Alpine.js 通过 CDN 加载)
```

## 待完成的模板文件

以下模板文件需要根据业务需求创建（可参考已有模板）：

### 配置管理
- ✅ `templates/configs/list.html` - 配置列表（已完成）
- ✅ `templates/configs/edit.html` - 配置编辑（已完成）
- ⏳ `templates/configs/view.html` - 配置详情

### 路由规则
- ⏳ `templates/routing/list.html` - 规则列表
- ⏳ `templates/routing/edit.html` - 规则编辑
- ⏳ `templates/routing/view.html` - 规则详情

### MongoDB 实例
- ⏳ `templates/instances/list.html` - 实例列表
- ⏳ `templates/instances/edit.html` - 实例编辑
- ⏳ `templates/instances/view.html` - 实例详情

### 节点监控
- ⏳ `templates/nodes/list.html` - 节点列表
- ⏳ `templates/nodes/detail.html` - 节点详情

### 用户管理
- ⏳ `templates/users/list.html` - 用户列表
- ⏳ `templates/users/create.html` - 创建用户
- ⏳ `templates/users/edit.html` - 编辑用户
- ⏳ `templates/users/view.html` - 用户详情
- ⏳ `templates/users/change_password.html` - 修改密码

### 其他
- ⏳ `templates/auth/profile.html` - 个人资料

**注意**: 这些模板可以参考已完成的模板（如 `configs/list.html` 和 `configs/edit.html`）快速创建。

## 安全注意事项

### 1. SECRET_KEY
确保在生产环境中设置强密码的 SECRET_KEY：

```python
# config.py
SECRET_KEY = os.getenv('SECRET_KEY', 'your-very-secure-secret-key-here')
```

### 2. CSRF 保护
所有表单已启用 CSRF 保护，确保模板中包含 `{{ form.hidden_tag() }}`。

### 3. 密码安全
- 密码使用 bcrypt 加密存储
- 最小密码长度：6 个字符
- 建议定期修改密码

### 4. 角色权限
- 敏感操作（创建、编辑、删除）仅限管理员
- 普通用户只有只读权限

### 5. 会话管理
- 支持"记住我"功能
- 会话cookie设置为 HttpOnly 和 Secure（生产环境）

## API 兼容性

Web UI 不影响现有的 REST API 功能：
- 所有 API 端点保持不变
- API 路径: `/api/*`
- Web UI 路径: `/*`（除 `/api` 外）

## 故障排除

### 1. 无法登录
- 检查管理员账户是否已创建：`python init_admin.py`
- 检查 MongoDB 连接是否正常
- 查看日志文件：`logs/state_management.log`

### 2. 模板未找到
- 确保所有模板文件已创建
- 检查 `templates/` 目录结构

### 3. CSS 样式未加载
- 检查网络连接（Tailwind CSS 通过 CDN 加载）
- 如需离线使用，下载 Tailwind CSS 到 `static/css/`

### 4. 数据库错误
- 检查 MongoDB 配置（`config.py`）
- 确保 MongoDB 服务正在运行
- 运行 `init_admin.py` 创建索引

## 扩展开发

### 添加新页面
1. 在 `views/` 创建新的视图文件
2. 在 `forms/` 创建对应的表单类
3. 在 `templates/` 创建对应的模板
4. 在 `views/__init__.py` 中导入新视图

### 添加新权限级别
修改 `models/user.py` 的 `VALID_ROLES` 常量，并更新装饰器。

### 自定义样式
修改 `templates/base.html` 中的 Tailwind CSS 配置。

## 支持

如有问题，请查看：
- 日志文件：`logs/state_management.log`
- MongoDB 日志
- 浏览器开发者控制台

## 版本信息

- Web UI 版本: 1.0.0
- Flask 版本: 3.0.0
- Python 版本: 3.8+
