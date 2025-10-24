"""
ESP32继电器控制系统配置文件
"""

# MQTT服务器配置
MQTT_CONFIG = {
    "server": "39.101.179.153",
    "port": 1883,
    "client_id": "ESP32_Relay_Controller",
    "keepalive": 60,
    "reconnect_delay": 5
}

# 继电器引脚配置
RELAY_CONFIG = {
    "relay1": {
        "pin": 23,
        "name": "继电器1",
        "description": "GPIO23"
    },
    "relay2": {
        "pin": 5,
        "name": "继电器2", 
        "description": "GPIO5"
    },
    "relay3": {
        "pin": 4,
        "name": "继电器3",
        "description": "GPIO4"
    },
    "relay4": {
        "pin": 13,
        "name": "继电器4",
        "description": "GPIO13"
    }
}

# 系统配置
SYSTEM_CONFIG = {
    "reset_pin": 12,
    "status_check_interval": 5000,  # 毫秒
    "wifi_timeout": 20,  # 秒
    "mqtt_timeout": 10,  # 秒
    "config_ap_ssid": "ESP32_Config",
    "config_ap_password": "12345678",
    "config_ap_ip": "192.168.4.1"
}

# MQTT主题配置
MQTT_TOPICS = {
    "control": "relay/control",
    "status": "relay/status",
    "system": "relay/system"
}

# 继电器状态
RELAY_STATES = {
    "ON": 1,
    "OFF": 0
}

# 系统状态
SYSTEM_STATES = {
    "ONLINE": "online",
    "OFFLINE": "offline",
    "CONFIG": "config"
}
