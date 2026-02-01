# PaperRef Hub

一个基于 Web 的文献管理平台，支持 BibTeX 文件管理、云端同步、冲突解决和批量操作。

## 功能特性

### 📚 文献管理
- 导入本地 BibTeX 文件（支持多个文件批量导入）
- 自动检测重复文献，智能合并（保留字段更多的版本）
- 手动冲突解决界面，相似文献可对比选择

### ☁️ 云端同步
- 支持 WebDAV 协议（坚果云、NextCloud 等）
- 一键 Pull/Push 云端文献库
- 本地缓存历史版本

### 🔍 搜索与筛选
- 全文搜索（标题、作者、年份、关键词）
- 实时过滤显示

### 📋 批量操作
- 多选文献，批量复制 BibTeX
- 单篇文献快速复制

### 📤 分享功能
- 生成本地分享副本，带时间戳

## 快速开始

### 本地运行

1. 克隆或下载项目：
```bash
git clone https://github.com/你的用户名/my_paper_hub.git
cd my_paper_hub
```

2. 安装依赖：
```bash
pip install streamlit bibtexparser requests
```

3. 启动应用：
```bash
streamlit run app.py
```

4. 浏览器访问 http://localhost:8501

### 云端部署（Streamlit Community Cloud）

1. **推送代码到 GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
# 创建 GitHub 仓库后
git remote add origin https://github.com/你的用户名/my_paper_hub.git
git push -u origin main
```

2. **部署**
   - 访问 [share.streamlit.io](https://share.streamlit.io)
   - 用 GitHub 登录
   - 选择你的仓库和分支
   - Main file path 填 `app.py`
   - 点击 Deploy

部署完成后会获得一个公开 URL（如 `https://你的用户名-paperref-hub.streamlit.app`）。

## 使用指南

### 1. 导入文献

**方式一：本地文件**
- 点击侧边栏「Local Files」
- 上传一个或多个 `.bib` 文件
- 点击「Import Files」

**方式二：WebDAV 云端**
- 先配置云端参数（见下方）
- 选择「WebDAV」导入方式
- 点击「Import from WebDAV」

### 2. 云端同步配置

在侧边栏「Cloud Settings」中配置：

| 参数 | 说明 | 示例 |
|------|------|------|
| URL | WebDAV 地址 | `https://dav.jianguoyun.com/dav/` |
| Username/Email | 用户名或邮箱 | 坚果云注册邮箱 |
| App Password | 应用密码 | 坚果云应用密码 |
| Filename | 云端文件名 | `my_library.bib` |

**坚果云配置示例：**
1. 登录坚果云网页版
2. 右上角「账户」→「安全」→「添加应用密码」
3. 应用名称填 `PaperRef Hub`，生成密码
4. 在应用中填写：
   - URL: `https://dav.jianguoyun.com/dav/`
   - Username: 你的坚果云账号邮箱
   - App Password: 刚才生成的应用密码

### 3. 搜索文献

在顶部搜索框输入关键词，支持：
- 论文标题
- 作者姓名
- 年份
- 期刊名称
- 任意关键词

### 4. 批量操作

1. 勾选文献左侧的复选框
2. 点击顶部「Batch Copy BibTeX」
3. 复制生成的批量 BibTeX 代码

### 5. 编辑文献

点击文献卡片右下角的「Edit Details」展开编辑表单，可修改：
- 标题
- 作者
- 引用键（Citation Key/ID）

### 6. 分享文献库

1. 先保存文献库（点击「Save Library」）
2. 点击「Share Library」
3. 选择要分享的库文件
4. 点击「Create Share Copy」
5. 生成的带时间戳的 `.bib` 文件位于 `share/` 目录

## 项目结构

```
my_paper_hub/
├── app.py              # 主应用代码
├── requirements.txt    # Python 依赖
├── README.md           # 说明文档
├── cache/              # 本地缓存目录（自动生成）
│   ├── webdav_config.json    # WebDAV 配置
│   └── libraries/            # 缓存的文献库
└── share/              # 分享文件目录（自动生成）
```

## 依赖

```
streamlit>=1.28.0
bibtexparser>=2.0.0
requests>=2.31.0
```

## 自定义修改

### 修改默认文件名

在 `app.py` 中找到并修改：
```python
wd_file = st.text_input("Filename", 
                       value="my_library.bib")  # 改为你想要的名字
```

### 修改页面标题

```python
st.set_page_config(page_title="你的文献库名称", ...)
```

## 常见问题

**Q: 导入时提示"Library is empty"？**
A: 请先导入一些文献，再进行 Push 操作。

**Q: WebDAV 连接失败？**
A: 检查：
1. URL 是否以 `/dav/` 结尾
2. 应用密码是否正确（不是登录密码）
3. 网络是否能访问该域名

**Q: 如何迁移到新设备？**
A:
1. 在旧设备上导出文献库（Save Library）
2. 在新设备上运行应用
3. 导入本地 `.bib` 文件，或配置相同的 WebDAV 参数后 Pull

**Q: 冲突解决时如何选择？**
A: 系统会显示相似文献的所有字段，对比后选择信息更完整或更准确的你需要保留的版本。

## 许可证

MIT License

## 致谢

- [Streamlit](https://streamlit.io/) - Web 应用框架
- [bibtexparser](https://bibtexparser.readthedocs.io/) - BibTeX 解析库
