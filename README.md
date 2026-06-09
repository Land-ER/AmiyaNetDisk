
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0%2B-lightgrey?style=flat&logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite" alt="SQLite">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat" alt="License">
</p>

<h1 align="center">AmiyaNetDisk</h1>

<p align="center">轻量级 · 公共资源共享网盘 · 小型私人部署</p>

<div align="center">
  <p>简洁明亮扁平化设计 | 多角色权限管理 | 邮件验证码注册 | SHA-256 文件去重</p>
</div>

---

## 功能特性

| 模块 | 功能 |
|------|------|
| 文件搜索 | 公开搜索，多关键词模糊匹配，分页浏览，标签筛选，可选 embedding 语义搜索 |
| 文件夹分类 | 管理员创建多级文件夹，文件按树状目录浏览与归类 |
| 用户认证 | 邮箱注册（验证码）、登录、Session 管理、前端 SHA-256 密码传输 |
| 文件下载 | 需登录，下载日志记录，下载量统计 |
| 角色权限 | `user` -> `admin` -> `root` 三级角色，装饰器隔离权限 |
| 管理后台 | 仪表盘概览、文件/文件夹管理、标签编辑、下载日志、用户禁用/启用 |
| 安全设计 | 密码 bcrypt 存储、CSRF 保护、文件后缀白名单、HTTPOnly Session、可选校园网注册验证 |
| Root 管理 | 预设超级管理员，可任命/撤销普通管理员 |
| 文件去重 | SHA-256 哈希命名，相同文件仅存一份（秒传） |
| 容器化 | Docker + docker-compose 一键部署 |

---

## 项目结构

```
AmiyaNetDisk/
├── run.py                      # 应用入口
├── requirements.txt            # Python 依赖
├── Dockerfile                  # Docker 构建文件
├── docker-compose.yml          # Docker 编排文件
├── .env                        # 环境变量配置（不提交）
├── .env.example                # 环境变量模板
├── .gitignore
│
├── app/
│   ├── __init__.py             # 应用工厂 create_app()
│   ├── config.py               # 配置类（环境变量读取）
│   ├── models.py               # SQLAlchemy 数据模型（5个模型）
│   ├── forms.py                # WTForms 表单定义
│   ├── utils.py                # 工具函数（哈希、邮件、标签处理）
│   ├── decorators.py           # 权限装饰器（login/admin/root_required）
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py             # 注册 / 登录 / 登出 / 验证码
│   │   ├── main.py             # 首页 / 公开搜索
│   │   ├── file.py             # 文件下载
│   │   ├── admin.py            # 管理员后台
│   │   └── root.py             # Root 管理员管理
│   │
│   ├── templates/
│   │   ├── base.html           # 基础模板（导航栏 + Flash + 页脚）
│   │   ├── index.html          # 首页（搜索框居中）
│   │   ├── search_results.html # 搜索结果（卡片式分页）
│   │   ├── login.html          # 登录页
│   │   ├── register.html       # 注册页（验证码）
│   │   ├── admin/              # 管理后台模板
│   │   │   ├── dashboard.html
│   │   │   ├── files.html
│   │   │   ├── upload.html
│   │   │   ├── edit_file.html
│   │   │   ├── download_logs.html
│   │   │   └── users.html
│   │   └── root/
│   │       └── manage_admins.html
│   │
│   └── static/
│       ├── css/style.css       # 扁平化明亮样式
│       └── js/main.js          # 前端密码哈希 + 验证码逻辑
│
└── uploads/                    # 文件存储目录（哈希重命名）
    └── .gitkeep
```

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/yourname/AmiyaNetDisk.git
cd AmiyaNetDisk
```

### 2. 配置环境变量

复制环境变量模板并根据需要修改：

```bash
cp .env.example .env
```

核心配置项说明：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | Flask 密钥，生产环境务必修改 | `dev-secret-key` |
| `DATABASE_URL` | 数据库连接 | `sqlite:///app.db` |
| `SMTP_SERVER` | SMTP 邮件服务器地址 | `localhost` |
| `SMTP_PORT` | SMTP 端口 | `25` |
| `SMTP_USERNAME` | SMTP 用户名 | （空） |
| `SMTP_PASSWORD` | SMTP 密码 | （空） |
| `SMTP_FROM` | 发件人地址 | `noreply@example.com` |
| `ROOT_EMAIL` | 超级管理员邮箱 | `root@example.com` |
| `ROOT_PASSWORD` | 超级管理员密码 | `root123456` |
| `MAX_CONTENT_LENGTH` | 上传文件大小限制 | `104857600`（100MB） |
| `EMBEDDING_ENABLED` | 是否启用 embedding 语义搜索 | `false` |
| `EMBEDDING_MODEL` | 语义搜索模型名称 | `BAAI/bge-small-zh-v1.5` |
| `EMBEDDING_TOP_K` | 语义候选数量 | `50` |
| `CAMPUS_VERIFY_ENABLED` | 是否启用注册前校园网验证 | `false` |
| `CAMPUS_VERIFY_MIN_SUCCESS` | 校园网验证需成功加载的图片数 | `1` |
| `CAMPUS_VERIFY_TTL_SECONDS` | 校园网验证会话有效期 | `600` |
| `CAMPUS_VERIFY_CONFIG_PATH` | 校园网验证私有配置文件路径 | `app/campus-verify.json` |

> **关于 embedding 搜索**：默认安装保持轻量，语义搜索关闭。若要启用，请额外安装 `sentence-transformers`，再设置 `EMBEDDING_ENABLED=true`。首次启用模型会下载权重，建议在服务器上预热或使用持久化缓存。

> **关于校园网验证**：该功能验证注册时的网络环境是否能访问配置中的 HIT 图片资源，不等同于统一身份认证或学生身份认证。如需强身份认证，应接入学校官方 CAS/SSO。

> **关于 SMTP 配置**：注册和找回密码功能需要 SMTP 发送验证码邮件。开发时可使用 [MailHog](https://github.com/mailhog/MailHog) 等本地测试工具，设置 `SMTP_SERVER=localhost`, `SMTP_PORT=1025` 即可拦截邮件查看。

### 3. 安装依赖（本地开发）

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

如需运行测试，请安装开发依赖：

```bash
pip install -r requirements-dev.txt
```

### 4. 启动应用

```bash
# 开发模式（Flask 内置服务器，自动重载）
python run.py

# 或通过 flask 命令
flask run --host=0.0.0.0 --port=5000
```

访问 `http://localhost:5000`

> 首次启动会自动创建 SQLite 数据库文件和预设的 root 超级管理员账号。

### 5. 运行测试

```bash
python -m pytest -q
```

测试套件会使用临时数据库，覆盖文件夹树、上传归类、搜索、CSRF、开放重定向和校园网注册验证 gate。

---

## Docker 部署

### 方式一：docker-compose（推荐）

```bash
# 确保已配置 .env 文件
docker-compose up -d
```

### 方式二：手动 Docker 构建

```bash
docker build -t amiyanetdisk .
docker run -d \
  --name amiyanetdisk \
  -p 5000:5000 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/app.db:/app/app.db \
  --env-file .env \
  amiyanetdisk
```

> Docker 部署使用 **gunicorn**（4 workers）作为生产级 WSGI 服务器。

---

## 路由一览

### 公开路由（无需登录）

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/` | 首页（重定向到搜索页） |
| GET | `/search` | 文件搜索（分页 12 条/页） |
| GET | `/login` | 登录页面 |
| GET | `/register` | 注册页面 |
| GET | `/reset_password` | 找回密码页面 |
| POST | `/send_code` | 发送验证码（AJAX，注册/找回密码复用） |

### 需登录

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/download/<id>` | 下载文件（记录日志 + 计数） |
| GET | `/logout` | 退出登录 |

### 管理员（`admin` / `root` 角色）

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/admin/dashboard` | 仪表盘概览 |
| GET | `/admin/files` | 文件管理列表 |
| GET/POST | `/admin/upload` | 上传文件 |
| GET/POST | `/admin/file/<id>/edit` | 编辑文件标题/标签 |
| POST | `/admin/file/<id>/delete` | 删除文件 |
| GET | `/admin/download_logs` | 下载日志查询 |
| GET | `/admin/users` | 用户列表 |
| POST | `/admin/user/<id>/ban` | 禁用用户 |
| POST | `/admin/user/<id>/unban` | 启用用户 |
| GET/POST | `/admin/user/<id>/reset_password` | 管理员重置用户密码 |

### Root 专属

| 方法 | 路径 | 功能 |
|------|------|------|
| GET/POST | `/root/admins` | 管理员任命/撤销 |

---

## 机器人 API

管理员可在后台 `API Tokens` 页面创建机器人 Token。Token 明文只在创建后显示一次，数据库仅保存哈希。

请求时使用 Bearer Token：

```http
Authorization: Bearer and_xxx
```

当前开放接口：

| 方法 | 路径 | Scope | 功能 |
|------|------|-------|------|
| GET | `/api/v1/folders/tree` | `folders:read` | 读取文件夹树 |
| POST | `/api/v1/folders` | `folders:write` | 创建文件夹 |
| GET | `/api/v1/search?q=关键词` | `search:read` | 搜索文件 |
| GET | `/api/v1/files/<id>` | `files:read` | 读取文件详情与下载路径 |
| GET | `/api/v1/files/<id>/download` | `files:read` | 下载文件并记录下载日志 |
| POST | `/api/v1/files` | `files:upload` | 上传文件 |

创建文件夹 JSON 示例：

```json
{
  "parent_id": 1,
  "name": "数学学院",
  "description": "课程资料"
}
```

上传文件使用 `multipart/form-data`：

```text
file=@algebra.txt
title=高等代数期末复习资料
folder_id=2
search_tags=数学,代数
display_tags=数学
```

建议仅给机器人授予必要 scope；停用 Token 后会立即拒绝后续请求。删除类 API 暂未开放。

---

## 数据模型

### User 用户

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `email` | String(120) | 唯一，登录标识 |
| `password_hash` | String(128) | bcrypt 哈希 |
| `role` | String(20) | `user` / `admin` / `root` |
| `is_active` | Boolean | 管理员可禁用用户 |
| `created_at` | DateTime | 注册时间 |

### File 文件

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `title` | String(200) | 显示标题 |
| `filename_on_disk` | String(255) | SHA-256 哈希 + 扩展名 |
| `original_filename` | String(255) | 下载时还原的原始名 |
| `file_size` | Integer | 字节数 |
| `search_tags` | Text | JSON 数组 |
| `display_tags` | Text | JSON 数组，前端展示 |
| `uploader_id` | FK(User) | 上传者 |
| `download_count` | Integer | 累计下载次数 |
| `created_at` / `updated_at` | DateTime | 创建/更新时间 |

### 其他模型

- **VerificationCode** — 注册/找回密码验证码（6 位数字，有效期 10 分钟，60 秒重发限制）
- **DownloadLog** — 下载日志（文件、用户、IP、时间）
- **OperationLog** — 操作审计日志（上传、编辑、删除、禁言、密码重置、管理员变更等）

---

## 权限体系

```
+----------------------------------------------+
|                  公开用户                      |
|  首页 / 搜索 / 登录 / 注册 / 找回密码          |
+----------------------------------------------+
|                 user（注册用户）                |
|  文件下载                                      |
+----------------------------------------------+
|           admin（管理员，由 root 任命）          |
|  文件上传 / 编辑 / 删除 / 仪表盘               |
|  用户禁用/启用 / 重置用户密码                   |
+----------------------------------------------+
|          root（超级管理员，预设账号）             |
|  任命/撤销管理员                                |
+----------------------------------------------+
```

**权限装饰器**定义在 `app/decorators.py`：
- `@login_required` — 需登录
- `@admin_required` — 登录 + `admin` 或 `root`
- `@root_required` — 仅 `root`

---

## 安全策略

1. **密码处理**：前端使用 Web Crypto API 做 SHA-256 哈希后通过隐藏字段提交，避免改写可见密码框；后端拒收表单明文密码，并使用 Werkzeug 的 `generate_password_hash` 存储
2. **验证码**：60 秒重发限制，10 分钟有效期，一次性使用
3. **CSRF 保护**：Flask-WTF 所有表单自动 CSRF 令牌
4. **文件上传**：后缀白名单（`pdf, doc, docx, jpg, png, ...`），文件大小限制，SHA-256 重命名防冲突
5. **恶意文件防护**：哈希重命名隔离执行风险；Jinja2 自动 HTML 转义防 XSS
6. **Session 安全**：`HTTPOnly=True`, `SameSite=Lax`

---

## 前端说明

- **样式**：纯 CSS，无前端框架 — 浅蓝/白色主色调，卡片式布局，圆角边框，柔和阴影
- **响应式**：flexbox/grid 布局，适配桌面 -> 平板 -> 手机
- **密码哈希**：原生 `crypto.subtle.digest('SHA-256', ...)`，无外部依赖
- **验证码**：AJAX 发送 + 前端 60 秒倒计时

---

## 开发指南

### 添加新路由

1. 在 `app/routes/` 中创建新蓝图文件
2. 在 `app/__init__.py` 的 `create_app()` 中注册蓝图
3. 根据需要添加 `@login_required` / `@admin_required` / `@root_required`

### 添加新模型

1. 在 `app/models.py` 中定义新 SQLAlchemy 模型
2. 应用重启后自动 `db.create_all()`

### 修改数据库

- 开发阶段可删除 `app.db` 文件重建
- 生产环境建议使用 Flask-Migrate 管理迁移

---

## 依赖说明

```
Flask>=3.0          # Web 框架
Flask-SQLAlchemy    # ORM
Flask-Login         # Session 认证
Flask-WTF           # CSRF 保护 + 表单
Werkzeug>=3.0       # 密码哈希
python-dotenv       # 环境变量加载
gunicorn>=21.2      # 生产级 WSGI 服务器（Docker）
```

---

## 协议

MIT License
