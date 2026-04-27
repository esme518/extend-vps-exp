[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1l1fAyDzNSSCVOF_JBpXRp2b3SHuI5bz6?usp=sharing) Accuracy 100% CAPTCHA weight: xserver_captcha.keras [repo](https://github.com/GitHub30/captcha-cloudrun)

[![](https://github.com/user-attachments/assets/f3db034f-1b1b-4983-9f9a-06a3aeb1b64e)](https://colab.research.google.com/drive/1l1fAyDzNSSCVOF_JBpXRp2b3SHuI5bz6?usp=sharing)

マニュアル
https://motoki-design.co.jp/wordpress/xserver-vps-auto-renew/

Manual
https://motoki-design.co.jp/wordpress/xserver-vps-auto-renew/

手册
https://motoki-design.co.jp/wordpress/xserver-vps-auto-renew/

![Clipchamp7-ezgif com-video-to-gif-converter](https://github.com/user-attachments/assets/745a85ef-0d5a-4532-9774-3b7fcb2c8b52)

我制作了 Tampermonkey [Install](https://raw.githubusercontent.com/GitHub30/extend-vps-exp/refs/heads/main/renew.user.js) 然后，请访问：https://secure.xserver.ne.jp/xapanel/login/xvps/

如果不起作用，请设置 GitHub Actions 的 Secrets 环境变量。

```env
EMAIL=your@gmail.com
PASSWORD=yourpassword
AUTH_LOGIN_OTP=your_base32_totp_secret
PROXY_SERVER=http://user:password@example.com:8888
NOTICE_TG_TOKEN=telegram_bot_token
NOTICE_TG_USERID=telegram_chat_id
DEBUG=true \
```

<details><summary>安装代理服务器</summary>

```bash
apt update
apt install -y tinyproxy
echo Allow 0.0.0.0/0 >> /etc/tinyproxy/tinyproxy.conf
echo BasicAuth user password >> /etc/tinyproxy/tinyproxy.conf
systemctl restart tinyproxy
systemctl status tinyproxy
```
</details>

我想去西門町，和大家一起喝珍珠奶茶。
