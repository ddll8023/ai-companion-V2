# AI Companion — 项目知识

## 数据库操作

### 删除数据库的正确方式

SQLite WAL 模式下，`.db-wal` 和 `.db-shm` 文件会遗留旧事务。如果只删 `.db` 文件，应用重启时 SQLite 会从 WAL 中恢复表结构和部分数据。

**数据库统一存储在：** `backend/app/data/ai_companion.db`

无论浏览器开发模式还是 Electron 桌面模式，同一路径，不再有两份。

**标准清库流程**：

```bash
# 1. 确保后端进程已完全停止
lsof -ti tcp:18080 | xargs kill 2>/dev/null

# 2. 删除数据库（三个文件都要删，否则 WAL 恢复旧数据）
rm -f backend/app/data/ai_companion.db*

# 3. 重启应用（自动重建空数据库）
```

**提示**：清库后前端如果还看到旧数据，`Cmd+Shift+R` 强制刷新浏览器即可。

**注意**：如果删除后看到前端仍有旧数据，先刷新浏览器（`Cmd+Shift+R`）而非重启后端。前端可能缓存了旧页面数据。

### 误删后数据恢复的检测

如果怀疑数据库未清空，直接连库验证：

```bash
cd backend && .venv/bin/python3 -c "
import sqlite3
conn = sqlite3.connect('app/data/ai_companion.db')
cur = conn.cursor()
cur.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\")
for t in cur.fetchall():
    cnt = cur.execute(f'SELECT COUNT(*) FROM [{t[0]}]').fetchone()[0]
    if cnt: print(f'{t[0]}: {cnt} rows')
conn.close()
"
```
