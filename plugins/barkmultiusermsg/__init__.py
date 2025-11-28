from typing import Any, List, Dict, Tuple, Optional
from urllib.parse import parse_qs

from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils


class BarkMultiUserMsg(_PluginBase):
    # 插件名称
    plugin_name = "Bark多用户消息通知1"
    # 插件描述
    plugin_desc = "支持使用Bark为多个用户发送消息通知，可根据用户ID精准推送。"
    # 插件图标
    plugin_icon = "Bark_A.png"
    # 插件版本
    plugin_version = "1.2"
    # 插件作者
    plugin_author = "weimh"
    # 作者主页
    author_url = "https://github.com/weiminghaoo"
    # 插件配置项ID前缀
    plugin_config_prefix = "barkmultiusermsg_"
    # 加载顺序
    plugin_order = 27
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _onlyonce = False
    _server = None
    _apikey = None
    _params = None
    _msgtypes = []
    _user_keys = {}  # 用户ID到密钥的映射

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._msgtypes = config.get("msgtypes") or []
            self._server = config.get("server")
            self._apikey = config.get("apikey")
            self._params = config.get("params")

            # 解析用户ID和密钥的映射关系
            self._user_keys = {}
            if self._apikey:
                for line in self._apikey.split():
                    if ':' in line:
                        user_id, device_key = line.split(':', 1)
                        self._user_keys[user_id.strip()] = device_key.strip()

        if self._onlyonce:
            self._onlyonce = False
            # 发送测试消息
            self._send("Bark消息测试通知", "Bark消息通知插件已启用")
            config['onlyonce'] = False
            self.update_config(config)

    def get_state(self) -> bool:
        return self._enabled and (True if self._server and self._apikey else False)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        # 编历 NotificationType 枚举，生成消息类型选项
        MsgTypeOptions = []
        for item in NotificationType:
            MsgTypeOptions.append({
                "title": item.value,
                "value": item.name
            })
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '测试插件（立即运行）',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'server',
                                            'label': '服务器',
                                            'placeholder': 'https://api.day.app',
                                        }
                                    }
                                ]
                            },
                        
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'params',
                                            'label': '附加参数',
                                            'placeholder': '',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'apikey',
                                            'label': '用户密钥',
                                            'placeholder': '每行一个配置，格式：用户名:密钥',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'model': 'msgtypes',
                                            'label': '消息类型',
                                            'items': MsgTypeOptions
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            "enabled": False,
            'msgtypes': [],
            'server': 'https://api.day.app',
            'apikey': '',
            'params': ''
        }

    def get_page(self) -> List[dict]:
        pass

    def _send(self, title: str, text: str, username: str = None) -> Optional[Tuple[bool, str]]:
        """
        发送消息
        :param title: 标题
        :param text: 内容
        :param username: 用户ID
        """
        try:
            if not self._server or not self._user_keys:
                return False, "参数未配置"

            req_body = {k: v[0] for k, v in parse_qs(self._params).items()}
            req_body.update(
                {
                    "title": title,
                    "body": text,
                }
            )

            # 打印消息信息
            logger.info(f"=== Bark消息发送 ===")
            logger.info(f"标题: {title}")
            logger.info(f"内容: {text}")
            logger.info(f"用户ID: {username}")
            logger.info(f"服务器: {self._server}")
            logger.info("===================")
            
            # 根据用户ID发送消息
            if username and username in self._user_keys:
                # 发送给指定用户
                device_key = self._user_keys[username]
                req_body.update({"device_key": device_key})
                res = RequestUtils().post_res(f"{self._server}/push", data=req_body)
                if res and res.status_code == 200:
                    ret_json = res.json()
                    code = ret_json["code"]
                    message = ret_json["message"]
                    if code == 200:
                        logger.info(f"用户 {username} Bark消息发送成功")
                    else:
                        logger.warn(f"用户 {username} Bark消息发送失败：{message}")
                elif res is not None:
                    logger.warn(
                        f"用户 {username} Bark消息发送失败，错误码：{res.status_code}，错误原因：{res.reason}"
                    )
                else:
                    logger.warn(f"用户 {username} Bark消息发送失败：未获取到返回信息")
            else:
                # 发送给所有用户
                for user_id, device_key in self._user_keys.items():
                    req_body.update({"device_key": device_key})
                    res = RequestUtils().post_res(f"{self._server}/push", data=req_body)
                    if res and res.status_code == 200:
                        ret_json = res.json()
                        code = ret_json["code"]
                        message = ret_json["message"]
                        if code == 200:
                            logger.info(f"用户 {user_id} Bark消息发送成功")
                        else:
                            logger.warn(f"用户 {user_id} Bark消息发送失败：{message}")
                    elif res is not None:
                        logger.warn(
                            f"用户 {user_id} Bark消息发送失败，错误码：{res.status_code}，错误原因：{res.reason}"
                        )
                    else:
                        logger.warn(f"用户 {user_id} Bark消息发送失败：未获取到返回信息")
        except Exception as msg_e:
            logger.error(f"Bark消息发送失败：{str(msg_e)}")

    @eventmanager.register(EventType.NoticeMessage)
    def send(self, event: Event):
        """
        消息发送事件
        """
        if not self.get_state():
            return

        if not event.event_data:
            return

        msg_body = event.event_data
        # 渠道
        channel = msg_body.get("channel")
        if channel:
            return
        # 类型
        msg_type: NotificationType = msg_body.get("type")
        # 标题
        title = msg_body.get("title")
        # 文本
        text = msg_body.get("text")
        # 用户ID
        username = msg_body.get("username")

        if not title and not text:
            logger.warn("标题和内容不能同时为空")
            return

        if (msg_type and self._msgtypes
                and msg_type.name not in self._msgtypes):
            logger.info(f"消息类型 {msg_type.value} 未开启消息发送")
            return

        return self._send(title, text, username)

    def stop_service(self):
        """
        退出插件
        """
        pass
