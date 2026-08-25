# 上海市桥隧群数字孪生平台
![alt text](image.png)

本项目基于中小规模桥隧数字孪生场景（约 60 座桥、暂无实时数据）设计，目标是低成本、快速上线、可平滑扩展。

## 技术架构

- 前端：`Vue 3` + `Vite` + `Pinia` + `CesiumJS` + `Element Plus` + `ECharts`
- 后端：`Node.js` + `Express` + `JWT`
- 数据库：`PostgreSQL` + `PostGIS`
- 部署：`Nginx` + `PM2` + 单机 PostgreSQL

## 目录结构

- `frontend`：三维展示与管理界面
- `backend`：REST API 与鉴权
- `sql`：数据库初始化脚本（含 PostGIS）

## 启动说明

### 1) 初始化数据库

推荐一键初始化（自动建库 + 执行脚本）：

```bash
cd backend
npm install
copy .env.example .env
# 按实际数据库修改 .env（需要 DB_USER 具备 CREATE DATABASE 权限）
npm run db:init
```

说明：
- 如果已安装 PostGIS：会执行 `sql/schema.sql` + `sql/seed.sql`
- 如果未安装 PostGIS：会自动降级执行 `sql/schema_nopostgis.sql` + `sql/seed_nopostgis.sql`（先跑通业务，再装 PostGIS 也不影响继续开发）

或手动在 PostgreSQL 中执行：

- `sql/schema.sql`
- `sql/seed.sql`

### 2) 启动后端

```bash
cd backend
npm install
copy .env.example .env
# 按实际数据库修改 .env
npm run dev
```

### 坐标系（定位偏移纠正）

Cesium 定位使用 **WGS84（经纬度）**。如果你的桥梁坐标来自：
- 高德/腾讯：通常为 `GCJ-02`
- 百度：通常为 `bd-09`

在 `backend/.env` 配置（**默认 `bd09`**，与百度台账一致）：

- `COORD_SOURCE=bd09`（默认，接口会把 bd-09 转为 GCJ-02 再转为 WGS84）
- `COORD_SOURCE=wgs84`（数据已是 GPS/WGS84 时用）
- `COORD_SOURCE=gcj02`（数据已是，接口会把gcj02 转为 WGS84）

后端接口返回时会自动转换为 WGS84，用于 Cesium 定位。

### 启动时自动迁移（避免列表为空）

后端启动时会自动执行：

- 为 `bridges` 表补齐 `wgs_lon` / `wgs_lat`（若旧库未跑过迁移）
- 若 `bridges` 为空，会自动补种 3 条示例桥梁（南浦/杨浦/卢浦）

若你曾出现「桥梁列表 No Data」，请**重启后端**一次。

仍无数据时：

1. 浏览器打开 `http://localhost:3000/health`，看 `bridgeCount` 是否为 `3`（或大于 0）。若 `dbError` 有内容，说明数据库连接或表结构有问题。
2. 在后端目录执行一次修复脚本（不启动服务也可补种）：

```bash
cd backend
npm run db:repair
```

3. 前端若 token 过期会返回 401，请**重新登录**后再查列表。

### 3. AI 服务 (FastAPI) - 必须启动以支持推演
```bash
# 确保已安装 torch, fastapi, uvicorn, pandas
python ai_models/api_server.py
```

### 4. 前端 (Vue 3)
```bash
cd frontend
npm install
npm run dev
```

## 后端核心接口

- `POST /api/auth/login`：JWT 登录（admin / visitor）
- `GET /api/bridges`：桥梁分页与筛选
- `GET /api/bridges/:id`：单桥详情
- `POST /api/bridges/spatial/search`：空间范围查询（BBox）
- `GET /api/models/:bridgeCode/tileset`：模型地址

## 默认账号

- 管理员：`admin / admin123`
- 游客：`visitor / visitor123`

## 后续扩展

- 实时监测：增加 WebSocket + TimescaleDB
- 告警中心：规则引擎 + 通知策略
- 视频融合：摄像头流接入与联动
