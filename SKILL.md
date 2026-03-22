---
name: radar-daily-report
description: 毫米波雷达技术日报自动生成。每日 09:00 搜集全网行业动态、学术论文、专利信息，AI 总结生成技术日报。
license: MIT
---

# Radar Daily Report - 毫米波雷达技术日报

自动生成毫米波雷达技术领域日报。

---

## 🎯 功能特性

- ✅ **自动搜集** - 每日 09:00 自动执行
- ✅ **全网搜索** - 新闻/论文/专利/产品
- ✅ **AI 总结** - 智能提炼关键信息
- ✅ **格式统一** - 标准化报告格式

---

## 🚀 快速开始

### 安装依赖

```bash
pip3 install requests beautifulsoup4
```

### 配置 Cron

```bash
# 每日 09:00 执行
0 9 * * * /usr/bin/python3 /root/.openclaw/workspace/skills/radar-daily-report/generate-report.py >> /var/log/radar-daily-report.log 2>&1
```

### 手动执行

```bash
python3 generate-report.py
```

---

## 📊 报告内容

### 行业动态
- 公司新闻
- 技术发布
- 市场动态
- 合作并购

### 学术论文
- arXiv 预印本
- IEEE 期刊
- 会议论文
- 研究进展

### 专利信息
- 新申请专利
- 授权专利
- 技术方向

### 新产品
- 芯片发布
- 模块更新
- 系统方案

### 技术趋势
- 技术热点
- 发展方向
- 市场分析

---

## 📁 输出位置

**默认目录：** `/root/.openclaw/workspace/radar-reports/`

**文件名：** `radar-daily-YYYY-MM-DD.md`

---

## 🔧 配置选项

### 环境变量

```bash
# 输出目录
export OUTPUT_DIR="/path/to/reports"

# 搜索关键词
export RADAR_KEYWORDS="毫米波雷达，mmWave,77GHz"
```

### 自定义关键词

编辑 `generate-report.py`:

```python
KEYWORDS = [
    "毫米波雷达 2026",
    "mmWave radar technology",
    # 添加自定义关键词
]
```

---

## 📤 提交方式

### 自动推送

**配置 Git 自动提交：**

```bash
#!/bin/bash
# auto-commit.sh
cd /root/.openclaw/workspace/radar-reports
git add .
git commit -m "Add radar daily report $(date +%Y-%m-%d)"
git push origin main
```

### 邮件发送

**配置邮件通知：**

```python
import smtplib
from email.mime.text import MIMEText

def send_email(report, recipients):
    # 实现邮件发送
    pass
```

---

## 📈 示例报告

```markdown
# 毫米波雷达技术日报 - 2026-03-12

**生成时间：** 2026-03-12 09:00:00
**数据来源：** 全网搜集 + AI 总结

---

## 📰 行业动态

- TI 发布新一代 77GHz 雷达芯片 - TI News
- 大陆集团投资 4D 成像雷达 - Automotive News

---

## 📚 学术论文

- 4D MIMO Radar Target Detection - IEEE T-AES
- Deep Learning for Radar Signal Processing - arXiv

---

## 💡 专利信息

- 一种毫米波雷达天线设计 - CN202610001
- 雷达信号处理方法 - US20260001

---

## 🛒 新产品

- AWR2944 评估模块 - Texas Instruments
- 77GHz 雷达模块 - NXP

---

## 📈 技术趋势

- 4D 成像雷达成为热点
- AI/ML 与雷达融合加速
- 车载雷达向高分辨率发展

---

**报告生成：** 小马 🐴
**下次更新：** 明日 09:00
```

---

## 🛠️ 故障排查

### 问题 1：搜索失败

**检查：**
```bash
# 测试网络连接
curl https://www.google.com

# 检查 SearXNG 状态
curl http://localhost:8081/health
```

---

### 问题 2：报告未生成

**检查：**
```bash
# 查看日志
tail -f /var/log/radar-daily-report.log

# 手动执行测试
python3 generate-report.py
```

---

### 问题 3：Cron 未执行

**检查：**
```bash
# 查看 Cron 状态
systemctl status cron

# 查看 Cron 日志
grep CRON /var/log/syslog
```

---

**维护者：** 小马 🐴  
**版本：** v1.0.1  
**最后更新：** 2026-03-12  
**下次更新：** 2026-03-13（每日迭代）
