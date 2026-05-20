# WeChat Cloud publisher

这是用于微信云托管的 Django 中转服务，提供：

```text
POST /api/publish
```

GitHub Actions 将日报 HTML 和封面图发送到该接口；服务在微信云托管环境内通过「开放接口服务」调用公众号接口完成图文群发，避免 GitHub Actions / self-hosted runner 的 IP 白名单问题。

## 云托管环境变量

在微信云托管服务中配置：

| 变量 | 必填 | 说明 |
|------|------|------|
| `WECHAT_CLOUD_PUBLISH_TOKEN` | 是 | 与 GitHub Secret 同值，用于保护 `/api/publish` |
| `WECHAT_CLOUD_FROM_APPID` | 否 | 资源复用时指定公众号 AppID |

## 微信云托管开放接口服务配置

在微信云托管控制台开启「开放接口服务」，并在微信令牌权限配置中加入：

```text
/cgi-bin/material/add_material
/cgi-bin/draft/add
/cgi-bin/freepublish/submit
```

开启后需要重新部署服务版本才会生效。

修改 `wechat_cloud/publisher/views.py` 后，请在微信云托管控制台**重新发布**服务，否则线上仍跑旧代码。

## 本地说明

本服务依赖微信云托管的开放接口服务，本地直接运行无法免鉴权调用公众号接口。
