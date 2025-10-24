# ESP32 MQTT继电器控制系统

基于ESP32和MicroPython的四路继电器控制系统，支持通过MQTT服务器远程控制继电器开关。

## 功能特性

- ✅ 四路继电器控制（GPIO23, GPIO5, GPIO4, GPIO13）
- ✅ WiFi配网功能（Web配网界面）
- ✅ 重置配网功能（GPIO12按钮）
- ✅ MQTT自动重连保持连接
- ✅ 实时状态监控和反馈
- ✅ 支持JSON格式控制命令

## 硬件连接

### 继电器连接
| 继电器 | GPIO引脚 | 功能描述 |
|--------|----------|----------|
| 继电器1 | GPIO23   | 第一路继电器 |
| 继电器2 | GPIO5    | 第二路继电器 |
| 继电器3 | GPIO4    | 第三路继电器 |
| 继电器4 | GPIO13   | 第四路继电器 |

### 控制引脚
| 功能 | GPIO引脚 | 说明 |
|------|----------|------|
| 重置配网 | GPIO12   | 低电平触发重置配网 |

## 软件安装

### 1. 烧录MicroPython固件
```bash
# 使用esptool烧录MicroPython固件到ESP32
esptool.py --chip esp32 --port COM3 write_flash -z 0x1000 micropython-esp32-20231005-v1.21.0.bin
```

### 2. 安装依赖库
```python
# 在MicroPython REPL中执行
import upip
upip.install('umqtt.simple')
```

### 3. 上传程序文件
将以下文件上传到ESP32：
- `main.py` - 主程序
- `config.py` - 配置文件

## 使用方法

### 1. 首次配网
1. 将ESP32上电
2. 如果没有WiFi配置，系统会自动进入配网模式
3. 连接WiFi热点：`ESP32_Config`，密码：`12345678`
4. 访问：`http://192.168.4.1`
5. 输入WiFi账号密码并保存

### 2. 重置配网
1. 按住GPIO12按钮（低电平）
2. 系统会删除WiFi配置并重新进入配网模式

### 3. MQTT控制命令

#### 控制继电器
```json
{
    "action": "control",
    "relay": "relay1",
    "state": "on"
}
```

#### 查询状态
```json
{
    "action": "status"
}
```

### 4. MQTT主题
- **控制主题**: `relay/control`
- **状态主题**: `relay/status`

## 配置参数

### MQTT服务器
- 地址：`39.101.179.153`
- 端口：`1883`
- 客户端ID：`ESP32_Relay_Controller`

### 继电器配置
```python
RELAY_PINS = {
    "relay1": 23,  # GPIO23
    "relay2": 5,   # GPIO5
    "relay3": 4,   # GPIO4
    "relay4": 13   # GPIO13
}
```

## 状态监控

系统会定期发送状态信息到MQTT主题：

### 继电器状态
```json
{
    "relay": "relay1",
    "state": "on",
    "timestamp": 1699123456.789
}
```

### 系统状态
```json
{
    "system": "online",
    "wifi": "connected",
    "mqtt": "connected",
    "timestamp": 1699123456.789
}
```

## 故障排除

### 1. WiFi连接失败
- 检查WiFi账号密码是否正确
- 检查信号强度
- 重置配网重新配置

### 2. MQTT连接失败
- 检查网络连接
- 检查MQTT服务器地址和端口
- 检查防火墙设置

### 3. 继电器不响应
- 检查GPIO连接
- 检查继电器模块电源
- 查看串口调试信息

## 开发说明

### 程序结构
- `main.py` - 主程序，包含所有功能
- `config.py` - 配置文件，系统参数
- `requirements.txt` - 依赖库列表

### 主要类和方法
- `RelayController` - 主控制类
- `connect_wifi()` - WiFi连接
- `connect_mqtt()` - MQTT连接
- `process_relay_command()` - 处理继电器命令
- `check_connections()` - 连接状态检查

### 扩展功能
- 可添加更多继电器
- 可添加传感器读取
- 可添加定时任务
- 可添加OTA更新

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 技术支持

如有问题，请查看：
1. 串口调试信息
2. MQTT服务器日志
3. 硬件连接检查
4. 网络连接测试
