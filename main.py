from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.provider.entities import ProviderRequest, LLMResponse

TAG_REPLY = "[REPLY]"
TAG_PASS = "[PASS]"

DEFAULT_HINT = (
    "你可以自主决定是否回复这条消息。\n"
    f"如果你想回复，请在回复内容的最开头加上 {TAG_REPLY} 标记，然后紧跟你的回复内容。\n"
    "如果你认为不需要回复（比如别人之间在对话、消息跟你无关、或者你没什么想说的），"
    f"请只回复 {TAG_PASS}，不要输出任何其他内容。\n"
    f"你必须以 {TAG_REPLY} 或 {TAG_PASS} 开头，不要输出任何思考过程。\n"
    "示例：\n"
    f"- 想回复：{TAG_REPLY}你好啊\n"
    f"- 不回复：{TAG_PASS}"
)


@register(
    "astrbot_plugin_mute",
    "小纳",
    "让大模型自主决定是否回复 - 注入判断提示，LLM可选择沉默",
    "1.0.0",
)
class SmartReplyPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}

        self.skip_at = self.config.get("skip_at", False)
        self.skip_private = self.config.get("skip_private", True)
        self.custom_hint = self.config.get("custom_hint", "")
        self.fallback_reply = self.config.get("fallback_reply", True)
        self._bot_self_id: str = ""

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        is_private = event.is_private_chat()
        is_at = event.is_at_or_wake_command

        if self.skip_private and is_private:
            return
        if self.skip_at:
            if not is_at and not is_private:
                is_at = self._detect_at_bot(event)
            if is_at:
                return

        hint = self.custom_hint or DEFAULT_HINT
        req.system_prompt = (req.system_prompt or "") + "\n\n" + hint
        event.set_extra("smart_reply_active", True)

    @filter.on_llm_response()
    async def on_llm_response(self, event: AstrMessageEvent, resp: LLMResponse):
        if not event.get_extra("smart_reply_active"):
            return

        text = (resp.completion_text or "").strip()
        upper = text.upper()

        # 情况1：以 [REPLY] 开头 → 提取实际回复内容
        if upper.startswith(TAG_REPLY):
            reply_content = text[len(TAG_REPLY):].strip()
            if reply_content:
                resp.completion_text = reply_content
                return
            # [REPLY] 后面是空的，当作不回复
            resp.completion_text = ""
            event.set_extra("smart_reply_passed", True)
            logger.warning("[smart_reply] LLM 输出 [REPLY] 但内容为空，已拦截")
            return

        # 情况2：以 [PASS] 开头 → 不回复
        if upper.startswith(TAG_PASS):
            resp.completion_text = ""
            event.set_extra("smart_reply_passed", True)
            logger.info("[smart_reply] LLM 选择不回复，已拦截")
            return

        # 情况3：无标记 → 根据 fallback_reply 配置决定
        if self.fallback_reply:
            logger.info(f"[smart_reply] LLM 未输出标记，放行原文: {text[:100]}")
            return
        logger.warning(f"[smart_reply] LLM 未输出标记，丢弃: {text[:100]}")
        resp.completion_text = ""
        event.set_extra("smart_reply_passed", True)

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        if event.get_extra("smart_reply_passed"):
            result = event.get_result()
            if result:
                result.chain = []

    def _detect_at_bot(self, event: AstrMessageEvent) -> bool:
        """后备 @ 检测：手动检查消息组件中是否包含 @机器人。"""
        if not self._bot_self_id:
            try:
                self._bot_self_id = str(event.get_self_id() or "")
            except (AttributeError, TypeError) as e:
                logger.debug(f"[smart_reply] 获取 bot self_id 失败: {e}")
        if not self._bot_self_id:
            return False
        try:
            msg = event.message_obj
            if not hasattr(msg, "message"):
                return False
            chain = msg.message
            components = (
                chain.chain if hasattr(chain, "chain")
                else chain if isinstance(chain, list)
                else []
            )
            for comp in components:
                comp_type = getattr(comp, "type", None) or type(comp).__name__
                if comp_type in ("At", "at"):
                    target = str(getattr(comp, "qq", "") or getattr(comp, "target", "") or "")
                    if target == self._bot_self_id:
                        return True
            return False
        except (AttributeError, TypeError, ValueError) as e:
            logger.debug(f"[smart_reply] @检测异常: {e}")
            return False
