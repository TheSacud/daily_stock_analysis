# DingTalk Enterprise Bot Configuration

## DingTalk Bot

DingTalk bots receive messages through the enterprise bot capability.

Reference: https://open.dingtalk.com/document/dingstart/configure-the-robot-application

Message receiving supports `HTTP mode`, which requires a public callback address, and `Stream mode`. `Stream mode` is recommended.

Create an application: https://open.dingtalk.com/document/dingstart/create-application

Path in the console: App Development > Enterprise Internal Apps > DingTalk App > Create App > Add App Capability > Bot.

### Add The Bot

![img.png](add-dingding-bot.png)

### Configure Stream Mode

![configbot.png](configbot.png)

### Get Application Credentials

![img.png](appkey.png)

### Configure DingTalk Credentials

Add the DingTalk application credentials to the project configuration.

![img.png](envconfig.png)

### Publish The Application

![img.png](img.png)

![img.png](group.png)

![img.png](add-group-bot.png)

### Find The Added Enterprise Bot

Scroll down until the newly added enterprise bot appears.

![img_1.png](img_1.png)

### Test Bot Commands

![img_3.png](img_3.png)