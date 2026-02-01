# 构建可执行文件

## 快速打包

```bash
# 1. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 2. 安装依赖（只装用的到的）
pip install --upgrade pip
pip install streamlit bibtexparser requests pyinstaller

# 3. 验证运行正常
streamlit run app.py

# 4. 打包
pyinstaller build_exe.spec --clean
```

## 手动打包命令

```bash
# 单文件模式（推荐）
pyinstaller --onefile --windowed --name PaperRefHub --clean app.py

# 或使用 spec 文件
pyinstaller build_exe.spec --clean
```

## 输出文件

- 位置：`dist/PaperRefHub.exe`
- 大小：约 80-120MB（取决于系统环境）

## 使用方式

1. 复制 `dist/PaperRefHub.exe` 到项目根目录
2. 确保 `cache/` 目录存在
3. 运行 `PaperRefHub.exe`

## 故障排除

**首次启动慢？**
首次启动需解压（约 1-2 分钟），之后正常。

**提示缺少模块？**
确保在虚拟环境中打包：
```bash
venv\Scripts\activate
pip install streamlit bibtexparser requests
pyinstaller build_exe.spec --clean
```
