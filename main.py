"""
ESP32 MQTT继电器控制系统
支持四路继电器控制，WiFi配网，MQTT保持连接
继电器引脚：GPIO23, GPIO5, GPIO4, GPIO13
重置配网引脚：GPIO12
"""

import network
import time
import json
from machine import Pin, Timer
import ubinascii
from umqtt.simple import MQTTClient
import gc

# 配置参数
MQTT_SERVER = "39.101.179.153"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "ESP32_Relay_Controller"
MQTT_TOPIC = "relay/control"
MQTT_STATUS_TOPIC = "relay/status"
MQTT_HEARTBEAT_TOPIC = "relay/heartbeat"

# 继电器引脚配置
RELAY_PINS = {
    "relay1": 23,  # GPIO23
    "relay2": 5,   # GPIO5
    "relay3": 4,   # GPIO4
    "relay4": 13   # GPIO13
}

# 继电器触发方式配置（True=高电平触发，False=低电平触发）
RELAY_TRIGGER_MODE = False  # 根据实际继电器模块调整

# 重置配网引脚
RESET_PIN = 12

# WiFi配置
WIFI_SSID = ""
WIFI_PASSWORD = ""

class RelayController:
    def __init__(self):
        self.relays = {}
        self.mqtt_client = None
        self.wifi_connected = False
        self.mqtt_connected = False
        self.reset_pin = Pin(RESET_PIN, Pin.IN, Pin.PULL_UP)
        self.heartbeat_counter = 0  # 心跳计数器
        
        # 初始化继电器引脚
        for name, pin_num in RELAY_PINS.items():
            self.relays[name] = Pin(pin_num, Pin.OUT)
            # 根据触发模式设置初始状态
            if RELAY_TRIGGER_MODE:
                self.relays[name].off()  # 高电平触发：初始为低电平（关闭）
                print(f"继电器 {name} (GPIO{pin_num}) 初始化为关闭状态 [高电平触发]")
            else:
                self.relays[name].on()   # 低电平触发：初始为高电平（关闭）
                print(f"继电器 {name} (GPIO{pin_num}) 初始化为关闭状态 [低电平触发]")
        
        # 初始化定时器用于状态检查（减少频率，避免干扰）
        self.status_timer = Timer(0)
        self.status_timer.init(period=10000, mode=Timer.PERIODIC, callback=self.check_connections)
        
        print("继电器控制器初始化完成")
        print(f"继电器引脚: {RELAY_PINS}")
        print(f"重置引脚: GPIO{RESET_PIN}")
    
    def check_reset_button(self):
        """检查重置按钮是否被按下"""
        if self.reset_pin.value() == 0:  # 低电平表示按下
            print("检测到重置按钮按下，开始防抖检查...")
            # 防抖处理：连续检查100ms
            debounce_count = 0
            for _ in range(10):  # 10次检查，每次10ms
                time.sleep(0.01)
                if self.reset_pin.value() == 0:
                    debounce_count += 1
            
            if debounce_count >= 8:  # 80%以上时间都是低电平
                print("重置按钮确认按下，开始重置配网...")
                self.reset_wifi_config()
                return True
        return False
    
    def reset_wifi_config(self):
        """重置WiFi配置"""
        try:
            # 删除WiFi配置文件
            import os
            if "wifi_config.json" in os.listdir():
                os.remove("wifi_config.json")
            print("WiFi配置已重置")
        except:
            print("重置WiFi配置失败")
        
        # 断开所有连接
        self.disconnect_all()
        
        # 启动配网模式
        self.start_config_mode()
    
    def start_config_mode(self):
        """启动配网模式"""
        print("进入配网模式...")
        print("请通过以下方式配网：")
        print("1. 连接WiFi热点: ESP32_Config")
        print("2. 访问: http://192.168.4.1")
        print("3. 或发送AT命令进行配网")
        
        # 创建配网热点
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.config(essid="ESP32_Config", password="12345678")
        
        # 启动Web配网服务器
        self.start_web_config()
    
    def start_web_config(self):
        """启动Web配网服务器"""
        import socket
        
        # 创建简单的Web服务器
        addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        s = socket.socket()
        s.bind(addr)
        s.listen(1)
        
        print("配网服务器启动，访问 http://192.168.4.1")
        
        while True:
            try:
                cl, addr = s.accept()
                request = cl.recv(1024).decode()
                
                if "GET /" in request:
                    # 返回配网页面
                    response = self.get_config_page()
                    cl.send(response)
                elif "POST /config" in request:
                    # 处理配网数据
                    data = request.split('\r\n\r\n')[1]
                    if self.process_config_data(data):
                        cl.send(b"HTTP/1.1 200 OK\r\n\r\nConfig saved!")
                        cl.close()
                        break
                    else:
                        cl.send(b"HTTP/1.1 400 Bad Request\r\n\r\nConfig failed!")
                
                cl.close()
            except Exception as e:
                print(f"Web服务器错误: {e}")
                break
        
        s.close()
        ap = network.WLAN(network.AP_IF)
        ap.active(False)
    
    def get_config_page(self):
        """获取配网页面HTML"""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>ESP32 WiFi配置</title>
    <meta charset="UTF-8">
</head>
<body>
    <h1>ESP32 WiFi配置</h1>
    <form method="POST" action="/config">
        <p>WiFi SSID: <input type="text" name="ssid" required></p>
        <p>WiFi密码: <input type="password" name="password"></p>
        <p><input type="submit" value="保存配置"></p>
    </form>
</body>
</html>"""
        
        return f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n{html}"
    
    def process_config_data(self, data):
        """处理配网数据"""
        try:
            # 解析表单数据
            params = {}
            for item in data.split('&'):
                key, value = item.split('=')
                params[key] = value.replace('+', ' ')
            
            global WIFI_SSID, WIFI_PASSWORD
            WIFI_SSID = params.get('ssid', '')
            WIFI_PASSWORD = params.get('password', '')
            
            # 保存配置
            config = {
                "ssid": WIFI_SSID,
                "password": WIFI_PASSWORD
            }
            
            with open("wifi_config.json", "w") as f:
                f.write(json.dumps(config))
            
            print(f"WiFi配置已保存: {WIFI_SSID}")
            return True
            
        except Exception as e:
            print(f"处理配网数据失败: {e}")
            return False
    
    def load_wifi_config(self):
        """加载WiFi配置"""
        try:
            with open("wifi_config.json", "r") as f:
                config = json.loads(f.read())
                global WIFI_SSID, WIFI_PASSWORD
                WIFI_SSID = config.get("ssid", "")
                WIFI_PASSWORD = config.get("password", "")
                print(f"加载WiFi配置: {WIFI_SSID}")
                return True
        except:
            print("未找到WiFi配置文件")
            return False
    
    def connect_wifi(self):
        """连接WiFi"""
        if not WIFI_SSID:
            print("未配置WiFi，启动配网模式")
            self.start_config_mode()
            return False
        
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        
        if not wlan.isconnected():
            print(f"正在连接WiFi: {WIFI_SSID}")
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
            
            # 等待连接
            timeout = 20
            while not wlan.isconnected() and timeout > 0:
                time.sleep(1)
                timeout -= 1
                print(".", end="")
            
            if wlan.isconnected():
                print(f"\nWiFi连接成功!")
                print(f"IP地址: {wlan.ifconfig()[0]}")
                self.wifi_connected = True
                return True
            else:
                print(f"\nWiFi连接失败!")
                self.wifi_connected = False
                return False
        else:
            print("WiFi已连接")
            self.wifi_connected = True
            return True
    
    def connect_mqtt(self):
        """连接MQTT服务器"""
        try:
            # 如果已有连接，先断开
            if self.mqtt_client:
                try:
                    self.mqtt_client.disconnect()
                except:
                    pass
                self.mqtt_client = None
            
            # 创建新的MQTT客户端
            self.mqtt_client = MQTTClient(MQTT_CLIENT_ID, MQTT_SERVER, MQTT_PORT, keepalive=60)
            self.mqtt_client.set_callback(self.mqtt_callback)
            self.mqtt_client.connect()
            self.mqtt_client.subscribe(MQTT_TOPIC)
            self.mqtt_client.subscribe(MQTT_STATUS_TOPIC)  # 订阅状态主题
            self.mqtt_client.subscribe(MQTT_HEARTBEAT_TOPIC)  # 订阅心跳主题
            self.mqtt_connected = True
            print(f"MQTT连接成功: {MQTT_SERVER}")
            print(f"已订阅主题: {MQTT_TOPIC}, {MQTT_STATUS_TOPIC}, {MQTT_HEARTBEAT_TOPIC}")
            
            # 发送在线状态
            self.publish_status("online")
            return True
            
        except Exception as e:
            print(f"MQTT连接失败: {e}")
            self.mqtt_connected = False
            return False
    
    def mqtt_callback(self, topic, msg):
        """MQTT消息回调"""
        try:
            topic_str = topic.decode('utf-8')
            msg_str = msg.decode('utf-8')
            
            print(f"收到MQTT消息: {topic_str} -> {msg_str}")
            
            if topic_str == MQTT_TOPIC:
                print("处理继电器控制命令...")
                self.process_relay_command(msg_str)
            elif topic_str == MQTT_STATUS_TOPIC:
                print("处理状态主题消息...")
                self.process_status_message(msg_str)
            elif topic_str == MQTT_HEARTBEAT_TOPIC:
                print("处理心跳主题消息...")
                self.process_heartbeat_message(msg_str)
            else:
                print(f"未知主题: {topic_str}")
                
        except Exception as e:
            print(f"处理MQTT消息失败: {e}")
            import sys
            sys.print_exception(e)
    
    def process_status_message(self, message):
        """处理状态主题消息"""
        try:
            print(f"处理状态消息: {message}")
            # 可以在这里处理来自服务器的状态查询或心跳响应
            # 目前主要是接收，不需要特殊处理
            print("✅ 状态消息处理完成")
        except Exception as e:
            print(f"❌ 处理状态消息失败: {e}")
    
    def process_heartbeat_message(self, message):
        """处理心跳主题消息"""
        try:
            print(f"处理心跳消息: {message}")
            # 可以在这里处理来自服务器的心跳响应
            # 目前主要是接收，不需要特殊处理
            print("✅ 心跳消息处理完成")
        except Exception as e:
            print(f"❌ 处理心跳消息失败: {e}")
    
    def process_relay_command(self, command):
        """处理继电器控制命令"""
        try:
            print(f"解析命令: {command}")
            cmd = json.loads(command)
            action = cmd.get("action")
            relay = cmd.get("relay")
            state = cmd.get("state")
            
            print(f"命令参数: action={action}, relay={relay}, state={state}")
            
            if action == "control" and relay in self.relays:
                print(f"控制继电器: {relay} -> {state}")
                if state == "on":
                    if RELAY_TRIGGER_MODE:
                        self.relays[relay].on()   # 高电平触发：开启
                    else:
                        self.relays[relay].off()  # 低电平触发：开启
                    print(f"✅ 继电器 {relay} 开启")
                elif state == "off":
                    if RELAY_TRIGGER_MODE:
                        self.relays[relay].off()  # 高电平触发：关闭
                    else:
                        self.relays[relay].on()   # 低电平触发：关闭
                    print(f"✅ 继电器 {relay} 关闭")
                else:
                    print(f"❌ 无效状态: {state}")
                
                # 发送状态更新
                self.publish_relay_status(relay, state)
                
            elif action == "status":
                print("查询所有继电器状态")
                # 发送所有继电器状态
                self.publish_all_status()
            else:
                print(f"❌ 无效命令: action={action}, relay={relay}")
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
        except Exception as e:
            print(f"❌ 处理继电器命令失败: {e}")
            import sys
            sys.print_exception(e)
    
    def publish_relay_status(self, relay, state):
        """发布单个继电器状态"""
        if self.mqtt_connected:
            status = {
                "relay": relay,
                "state": state,
                "timestamp": time.time()
            }
            self.mqtt_client.publish(MQTT_STATUS_TOPIC, json.dumps(status))
    
    def publish_all_status(self):
        """发布所有继电器状态"""
        if self.mqtt_connected:
            status = {
                "action": "status",
                "relays": {},
                "timestamp": time.time()
            }
            
            for relay_name, relay_pin in self.relays.items():
                # 根据触发模式判断实际状态
                if RELAY_TRIGGER_MODE:
                    # 高电平触发：高电平=开启，低电平=关闭
                    status["relays"][relay_name] = "on" if relay_pin.value() else "off"
                else:
                    # 低电平触发：低电平=开启，高电平=关闭
                    status["relays"][relay_name] = "off" if relay_pin.value() else "on"
            
            self.mqtt_client.publish(MQTT_STATUS_TOPIC, json.dumps(status))
    
    def publish_status(self, status):
        """发布系统状态"""
        if self.mqtt_connected:
            msg = {
                "system": status,
                "wifi": "connected" if self.wifi_connected else "disconnected",
                "mqtt": "connected" if self.mqtt_connected else "disconnected",
                "timestamp": time.time()
            }
            self.mqtt_client.publish(MQTT_STATUS_TOPIC, json.dumps(msg))
    
    def send_heartbeat(self):
        """发送心跳"""
        if self.mqtt_connected:
            heartbeat_msg = {
                "type": "heartbeat",
                "client_id": MQTT_CLIENT_ID,
                "status": "alive",
                "wifi": "connected" if self.wifi_connected else "disconnected",
                "mqtt": "connected" if self.mqtt_connected else "disconnected",
                "uptime": time.time(),
                "timestamp": time.time()
            }
            try:
                self.mqtt_client.publish(MQTT_HEARTBEAT_TOPIC, json.dumps(heartbeat_msg))
                print("💓 心跳发送成功")
            except Exception as e:
                print(f"❌ 心跳发送失败: {e}")
                self.mqtt_connected = False
    
    def check_connections(self, timer):
        """检查连接状态"""
        # 检查重置按钮
        if self.check_reset_button():
            return
        
        # 检查WiFi连接
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected() and self.wifi_connected:
            print("WiFi连接丢失，尝试重连...")
            self.wifi_connected = False
            self.mqtt_connected = False
        
        # 检查MQTT连接
        if self.wifi_connected and not self.mqtt_connected:
            print("尝试重连MQTT...")
            self.connect_mqtt()
        elif self.mqtt_connected:
            try:
                self.mqtt_client.check_msg()
            except:
                print("MQTT连接异常，尝试重连...")
                self.mqtt_connected = False
    
    def disconnect_all(self):
        """断开所有连接"""
        if self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
            except:
                pass
            self.mqtt_client = None
        
        wlan = network.WLAN(network.STA_IF)
        wlan.active(False)
        
        self.wifi_connected = False
        self.mqtt_connected = False
    
    def run(self):
        """主运行循环"""
        print("ESP32继电器控制系统启动")
        
        # 加载WiFi配置
        self.load_wifi_config()
        
        # 连接WiFi
        if not self.connect_wifi():
            return
        
        # 连接MQTT
        if not self.connect_mqtt():
            return
        
        print("系统启动完成，等待MQTT命令...")
        print("支持的命令格式:")
        print('{"action": "control", "relay": "relay1", "state": "on"}')
        print('{"action": "control", "relay": "relay1", "state": "off"}')
        print('{"action": "status"}')
        print("=" * 50)
        
        # 发送初始状态
        self.publish_all_status()
        
        # 主循环
        while True:
            try:
                # 检查MQTT消息
                if self.mqtt_connected and self.mqtt_client:
                    try:
                        self.mqtt_client.check_msg()
                    except Exception as e:
                        print(f"MQTT消息检查错误: {e}")
                        self.mqtt_connected = False
                
                # 检查重置按钮（在主循环中也检查）
                self.check_reset_button()
                
                # 心跳机制：每30秒发送一次心跳
                self.heartbeat_counter += 1
                if self.heartbeat_counter >= 300:  # 300 * 0.1s = 30s
                    self.send_heartbeat()
                    self.heartbeat_counter = 0
                
                time.sleep(0.1)
                gc.collect()  # 垃圾回收
                
            except KeyboardInterrupt:
                print("程序被中断")
                break
            except Exception as e:
                print(f"运行错误: {e}")
                time.sleep(1)

# 启动程序
if __name__ == "__main__":
    controller = RelayController()
    controller.run()
