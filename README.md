# ELF_RSS

重构分支，主要修改内容：

- [x] 多 Bot 实例支持
- [x] 多适配器支持：使用 `nonebot-plugin-send-anything-anywhere`
- [x] 数据存储管理：迁移到 `nonebot-plugin-orm`

功能测试情况：

- [x] 命令解析
- [x] 数据存储
- [x] 更新推送
- [x] 推送去重
- [x] 文本翻译：仅测试了 Google 翻译
- [x] 推送过滤
- [x] 媒体文件保存

运行方法：

```bash
# 安装依赖
poetry install
# 升级数据库
nb orm upgrade
# 安装适配器
nb adapter install nonebot-adapter-qq
# 复制 .env.template 到 .env.prod
cp .env.template .env.prod
# 根据适配器和插件要求编辑 .env.prod
# 配置完成后运行
nb run
```
