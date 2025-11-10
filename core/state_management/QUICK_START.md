# State Management Web UI - 快速启动指南

## 🚀 快速开始（5 分钟）

### 步骤 1: 安装依赖
```bash
cd core/state_management
pip install -r requirements.txt
```

### 步骤 2: 创建管理员账户
```bash
python init_admin.py
```
按提示输入用户名和密码，或使用默认值：
```bash
python init_admin.py --username admin --password admin123 --email admin@example.com
```

### 步骤 3: 启动服务
```bash
python app.py
```

### 步骤 4: 访问 Web UI
打开浏览器访问：**http://localhost:8000**

使用刚创建的管理员账户登录即可！

---

## 📁 完整的文件结构

```
core/state_management/
├── app.py                          ✅ 已集成 Web UI
├── init_admin.py                   ✅ 管理员初始化脚本
├── requirements.txt                ✅ 已更新依赖
├── config.py
├── Dockerfile
│
├── auth/                           ✅ 认证模块
│   ├── __init__.py
│   ├── routes.py
│   └── decorators.py
│
├── forms/                          ✅ 表单模块
│   ├── __init__.py
│   ├── auth_forms.py
│   └── config_forms.py
│
├── views/                          ✅ Web UI 视图
│   ├── __init__.py
│   ├── dashboard.py
│   ├── config_views.py
│   ├── routing_views.py
│   ├── instance_views.py
│   ├── node_views.py
│   └── user_views.py
│
├── models/
│   ├── analysis_config.py
│   ├── routing_rule.py
│   ├── mongodb_instance.py
│   ├── node_status.py
│   ├── config_version.py
│   └── user.py                     ✅ 新增：用户模型
│
├── templates/                      ✅ 所有模板已完成
│   ├── base.html                   ✅ 基础布局
│   ├── dashboard.html              ✅ 仪表板
│   ├── partials/
│   │   └── sidebar_nav.html        ✅ 侧边栏导航
│   ├── auth/
│   │   ├── login.html              ✅ 登录页面
│   │   └── profile.html            ✅ 个人资料
│   ├── configs/
│   │   ├── list.html               ✅ 配置列表
│   │   ├── edit.html               ✅ 配置编辑
│   │   └── view.html               ✅ 配置详情
│   ├── routing/
│   │   ├── list.html               ✅ 规则列表
│   │   ├── edit.html               ✅ 规则编辑
│   │   └── view.html               ✅ 规则详情
│   ├── instances/
│   │   ├── list.html               ✅ 实例列表
│   │   ├── edit.html               ✅ 实例编辑
│   │   └── view.html               ✅ 实例详情
│   ├── nodes/
│   │   ├── list.html               ✅ 节点列表
│   │   └── detail.html             ✅ 节点详情
│   └── users/
│       ├── list.html               ✅ 用户列表
│       ├── create.html             ✅ 创建用户
│       ├── edit.html               ✅ 编辑用户
│       ├── view.html               ✅ 用户详情
│       └── change_password.html    ✅ 修改密码
│
├── api/                            # REST API（保持不变）
│   ├── config_api.py
│   ├── routing_api.py
│   ├── node_api.py
│   └── instance_api.py
│
├── services/                       # 后台服务（保持不变）
│   ├── task_scheduler.py
│   ├── node_monitor.py
│   └── config_manager.py
│
└── utils/                          # 工具类（保持不变）
    ├── mongodb_handler.py
    └── rabbitmq_handler.py
```

---

## ✅ 已完成的功能

### 🔐 认证与授权
- ✅ 用户登录/登出
- ✅ 会话管理（支持"记住我"）
- ✅ 密码加密（bcrypt）
- ✅ CSRF 保护
- ✅ 基于角色的权限控制（管理员/普通用户）

### 📊 仪表板
- ✅ 系统概览（配置、规则、实例、节点统计）
- ✅ 最近更新的配置列表
- ✅ 在线节点列表

### ⚙️ 配置管理
- ✅ 配置列表（支持过滤）
- ✅ 创建/编辑/删除配置（管理员）
- ✅ 查看配置详情
- ✅ 启用/禁用配置
- ✅ 模型文件上传（预留功能）

### 🔀 路由规则管理
- ✅ 规则列表（支持过滤、按优先级排序）
- ✅ 创建/编辑/删除规则（管理员）
- ✅ 查看规则详情
- ✅ 启用/禁用规则
- ✅ JSON 格式的条件和操作配置

### 💾 MongoDB 实例管理
- ✅ 实例列表（支持过滤）
- ✅ 创建/编辑/删除实例（管理员）
- ✅ 查看实例详情
- ✅ 启用/禁用实例
- ✅ 连接测试功能

### 🖥️ 节点监控
- ✅ 节点列表（在线/离线状态）
- ✅ 节点详情（能力、任务负载）
- ✅ 统计信息（总数、在线、离线）
- ✅ 删除（注销）节点（管理员）

### 👥 用户管理（仅管理员）
- ✅ 用户列表（支持显示已停用用户）
- ✅ 创建新用户
- ✅ 编辑用户信息（角色、邮箱、激活状态）
- ✅ 查看用户详情
- ✅ 停用用户
- ✅ 重置密码

### 👤 个人设置
- ✅ 查看个人资料
- ✅ 修改密码

### 🎨 界面设计
- ✅ 响应式设计（支持桌面和移动设备）
- ✅ Tailwind CSS 样式
- ✅ Alpine.js 交互
- ✅ Font Awesome 图标
- ✅ 侧边栏导航
- ✅ Flash 消息提示
- ✅ 表单验证

---

## 🔑 默认账户

如果使用 `python init_admin.py` 创建：
- **用户名**: admin
- **密码**: （您在创建时输入的密码）

---

## 📱 功能导航

### 管理员功能
1. **仪表板** - `/` 或 `/dashboard`
2. **配置管理** - `/configs`
3. **路由规则** - `/routing`
4. **MongoDB 实例** - `/instances`
5. **节点监控** - `/nodes`
6. **用户管理** - `/users`
7. **个人资料** - `/auth/profile`
8. **修改密码** - `/profile/change-password`

### 普通用户功能
- 只读访问：仪表板、配置、规则、实例、节点
- 无法创建、编辑或删除任何资源
- 无法访问用户管理

---

## 🔧 配置说明

### 环境变量
在生产环境中，建议设置以下环境变量：

```bash
export FLASK_ENV=production
export SECRET_KEY=your-very-secure-secret-key-here
export MONGODB_HOST=your-mongodb-host
export MONGODB_PORT=27021
export MONGODB_USERNAME=web_ui
export MONGODB_PASSWORD=your-secure-password
```

### 数据库配置
确保 MongoDB 已启动并可访问，配置位于 [config.py](config.py:38-56)

---

## 🐛 故障排除

### 1. 无法登录
```bash
# 重新创建管理员账户
python init_admin.py
```

### 2. 依赖安装失败
```bash
# 使用 pip 升级
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. MongoDB 连接失败
- 检查 MongoDB 服务是否运行
- 检查 `config.py` 中的连接配置
- 查看日志文件：`logs/state_management.log`

### 4. 端口被占用
修改 [config.py](config.py:28) 中的 `PORT` 配置：
```python
PORT = 8001  # 改为其他端口
```

---

## 🔒 安全建议

1. **更改默认密码**：首次登录后立即修改密码
2. **设置强密码**：使用至少 8 个字符，包含大小写字母、数字和特殊字符
3. **定期更新**：定期修改密码和更新系统
4. **限制访问**：通过防火墙限制 8000 端口的访问
5. **使用 HTTPS**：在生产环境中配置 SSL/TLS

---

## 📚 相关文档

- 详细使用说明：[WEB_UI_README.md](WEB_UI_README.md)
- API 文档：访问 `/api` 端点
- 原有 README：[../README.md](../README.md)

---

## 🎉 开始使用

现在您可以：
1. 登录系统：http://localhost:8000
2. 查看仪表板了解系统状态
3. 管理配置、规则和实例
4. 监控节点状态
5. 管理用户账户（如果您是管理员）

祝您使用愉快！🚀
