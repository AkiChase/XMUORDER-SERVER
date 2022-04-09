# XMU智能点餐服务端
## 1. API部分

不同的路由模块对应不同的url路径

### 1.1 短信模块

#### routers/sms.py


接口列表：

1. `sendCanteenNotice`

   给指定餐厅绑定的所有手机发送短信提醒

2. `phoneVerificationCode`

   给指定手机号发送验证码

3. `removeCanteenBindPhone`

   从指定餐厅绑定手机号移除指定手机号

4. `getCanteenBindPhone`

   获取指定餐厅绑定的所有手机号

5. `bindCanteen`

   绑定指定手机号到指定餐厅

### 1.2 XMU模块

#### routers/xmu.py


接口列表：

1. `bind`

   通过账号密码爬取用户基本信息，储存至mysql数据库

2. `login`

   读取mysql数据库，返回用户基本信息

### 1.3 统计模块

#### routers/statistics.py


接口列表：

1. `shopInfo`

   通过微信数据库，统计指定餐厅，指定日期范围内的营业额、销量等信息

2. `riderInfo`

   通过微信数据库，统计骑手的配送费信息

### 1.4 打印机模块

#### routers/printer.py


接口列表：

1. `addPrinter`

   添加指定云打印机，并绑定到指定餐厅

2. `getPrinterState`

   获取指定餐厅绑定的所有云打印机的状态信息

3. `printAcceptOrder`

   调用指定餐厅绑定的所有云打印机，打印指定订单的接单小票

4. `printOrderNotice`

   调用指定餐厅绑定的所有云打印机，打印指定语音提醒（新订单、取消订单、申请退款）

#### `class Printer`


对云打印机各种功能的封装

1. 飞鹅云打印机api接口封装
2. 根据纸张大小格式化打印内容（`class LineFormat`）



## 2. 微信部分

#### weixin/weixin.py

1. 本地缓存微信**access_token**的维护(调用时若已过期则自动更新)

#### weixin/database.py


1. 微信数据库相关操作封装

1. 根据微信数据库，更新mysql数据库中部分内容（用于定时任务模块）

   

## 3. 其他部分

#### common.py

封装了常用的自定义数据类型，自定义异常

#### config.py

1. .env配置文件的读取
2. 通过`@classmethod`，实现配置信息全局化(`class GlobalSettings`)

#### database.py

1. mysql数据库连接池封装
2. mysql数据库`execute`封装，通过sql语句**预编译**避免sql注入问题

#### dependencies.py

`fastapi`依赖注入

1. 简单验证请求是否合法
2. 通过AES验证请求是否合法

#### logger.py

`loguru`二次封装，实现不同名称的`logger`对应不同的消息前缀

不同模块使用不同名称的`logger`，方便日志输出，增强日志的可读性

#### scheduler.py

`apscheduler`二次封装，封装了添加定时任务和移除定时任务

使用`logger`，为不同定时任务添加前缀，增强可读性

#### security.py

**AES**加密解密封装（CBC模式）
