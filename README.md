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

使用说明：

- 订阅：`sub abc /example/abc`
- 退订：`unsub abc`
- 编辑：`edit abc tr 1`
- 查看：`show abc`

编辑与查看可以使用 `all` 进行批量操作，例如 `edit all tr 1`，`show all`

可编辑参数列表

    url: 订阅链接
    time: 订阅更新时间
    stop: 是否停止订阅
    proxy: 是否使用代理
    op: 仅发送图片
    ot: 仅发送标题
    cp: 仅包含图片
    dp: 下载图片
    tr: 是否开启翻译
    ck: cookie
    wk: 白名单关键词
    bk: 黑名单关键词
    ft: 过滤器
    cr: 内容过滤
    mi: 最大图片数量
    confirm: 确认批量修改
