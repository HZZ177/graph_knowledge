# Backend (FastAPI)

## 安装依赖

```bash
pip install -r backend/requirements.txt
```

## 启动开发服务器

在项目根目录下执行：

```bash
uvicorn backend.app.main:app --reload --port 8000
```

启动后可访问：

- 健康检查: http://localhost:8000/health
- Swagger 文档: http://localhost:8000/docs
