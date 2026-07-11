import openai
import re
import threading
from .config import LLMConfig
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from rl_pipeline.common import prompts


# 全局 token 统计追踪器
class TokenTracker:
    """全局 token 使用统计追踪器"""
    _instance = None
    _instance_lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.stats = {
                        "total_prompt_tokens": 0,
                        "total_completion_tokens": 0,
                        "total_tokens": 0,
                        "call_count": 0
                    }
                    cls._instance._stats_lock = threading.Lock()
        return cls._instance
    
    def record(self, prompt_tokens: int, completion_tokens: int, total_tokens: int):
        """记录一次 API 调用的 token 使用情况"""
        with self._stats_lock:
            self.stats["total_prompt_tokens"] += prompt_tokens
            self.stats["total_completion_tokens"] += completion_tokens
            self.stats["total_tokens"] += total_tokens
            self.stats["call_count"] += 1
    
    def get_stats(self) -> Dict:
        """获取当前统计信息"""
        with self._stats_lock:
            return self.stats.copy()
    
    def reset(self):
        """重置统计信息"""
        with self._stats_lock:
            self.stats = {
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "call_count": 0
            }


# 全局 token 追踪器实例
_token_tracker = TokenTracker()


def get_token_stats() -> Dict:
    """获取全局 token 使用统计信息"""
    return _token_tracker.get_stats()


def reset_token_stats():
    """重置全局 token 使用统计信息"""
    _token_tracker.reset()



# 抽象基类，定义了统一的接口
class BaseChatModel(ABC):
    def __init__(self, config: LLMConfig):
        self.config = config
        self.system_message = {"role": "system", "content": prompts.system_prompt()}

    @abstractmethod
    def generate_response(self, user_input: str) -> str:
        """
        根据用户Input生成响应。
        子类必须实现此方法。
        """
        pass

    def _process_response_think_tags(self, response_text: str) -> str:
        """Drop hidden reasoning blocks and unwrap an optional code block."""
        if not response_text:
            return ""
        # The invariant parser consumes only the visible final answer.
        text = re.sub(r'<\s*think\s*>[\s\S]*?<\s*/\s*think\s*>', '', response_text, flags=re.IGNORECASE)
        text = re.sub(r'<\s*reasoning\s*>[\s\S]*?<\s*/\s*reasoning\s*>', '', text, flags=re.IGNORECASE)
        # Strip <code> wrapper, keep inner content.
        text = re.sub(r'<\s*code\s*>\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*<\s*/\s*code\s*>', '', text, flags=re.IGNORECASE)
        return text.strip()


# 使用 OpenAI 兼容 API 的 LLM 类（云端模式）
class OpenAILLM(BaseChatModel):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.model_name = config.api_model
        self.client = openai.OpenAI(base_url=config.base_url, api_key=config.api_key)
        self.temperature = self.config.api_temperature
        self.top_p = self.config.api_top_p
        self.max_tokens = max(1, int(getattr(self.config, "api_max_tokens", 256)))

    @staticmethod
    def _coerce_message_content_to_text(content) -> str:
        """Normalize OpenAI message.content (string/list/None) into plain text."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    if item:
                        parts.append(item)
                    continue
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        txt = item.get("text", "")
                        if isinstance(txt, str) and txt:
                            parts.append(txt)
                    continue
                item_type = getattr(item, "type", "")
                if item_type == "text":
                    txt = getattr(item, "text", "")
                    if isinstance(txt, str) and txt:
                        parts.append(txt)
            return "\n".join(parts).strip()
        return str(content)

    def generate_response(self, user_input: str) -> str:
        try:
            # Every rollout/refine call is stateless by contract.
            messages = [self.system_message, {"role": "user", "content": user_input}]

            def _call_chat(max_tokens: int):
                return self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=max_tokens,
                )

            # 调用 OpenAI API（并在“空内容+length”时自动重试一次）
            response = _call_chat(self.max_tokens)
            choice = response.choices[0]
            msg = choice.message

            raw_content = msg.content
            assistant_response = self._coerce_message_content_to_text(raw_content)
            if not assistant_response:
                fallback_refusal = getattr(msg, "refusal", None)
                if isinstance(fallback_refusal, str) and fallback_refusal.strip():
                    assistant_response = fallback_refusal.strip()
            if (
                not assistant_response
                and getattr(choice, "finish_reason", None) == "length"
                and self.max_tokens < 8192
            ):
                retry_max_tokens = min(8192, max(self.max_tokens * 4, 1024))
                response = _call_chat(retry_max_tokens)
                choice = response.choices[0]
                msg = choice.message
                raw_content = msg.content
                assistant_response = self._coerce_message_content_to_text(raw_content)
                if not assistant_response:
                    fallback_refusal = getattr(msg, "refusal", None)
                    if isinstance(fallback_refusal, str) and fallback_refusal.strip():
                        assistant_response = fallback_refusal.strip()

            # 记录 token 使用情况
            if response.usage:
                _token_tracker.record(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )
            
            # 处理模型可能返回的推理标签
            processed_response = self._process_response_think_tags(assistant_response)
            return processed_response

        except Exception as e:
            print(f"OpenAI API 调用失败: {e}")
            return f"生成响应失败: {e}"

# ==============================================================================
# Transformers 本地推理（单卡 / CPU）
# ==============================================================================

_hf_instance: Optional["TransformersClient"] = None
_hf_lock = threading.Lock()


class TransformersClient:
    """
    封装 HuggingFace Transformers 推理。进程内单例，模型只加载一次。
    适合单卡或 CPU 场景。
    """

    def __init__(self, model_path: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not model_path:
            raise ValueError("local_model_path is required when use_local=True")
        print(f"[TransformersClient] 正在加载模型: {model_path} ...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
            trust_remote_code=True,
        )
        self.model.eval()
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model.config.pad_token_id = self.tokenizer.pad_token_id
        print("[TransformersClient] 模型加载完毕。")

    def chat_messages(
        self,
        messages: List[Dict],
        temperature: float = 1.0,
        top_p: float = 1.0,
        max_new_tokens: int = 8192,
        enable_thinking: bool = True,
    ) -> Tuple[str, int, int]:
        """
        以 OpenAI messages 格式调用，返回 (生成文本, prompt_tokens, completion_tokens)。
        """
        import torch

        try:
            # Some chat templates (e.g. Qwen family) support enable_thinking at prompt-build stage.
            try:
                prompt_text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=bool(enable_thinking),
                )
            except TypeError:
                prompt_text = self.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
        except Exception:
            prompt_text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

        inputs = self.tokenizer(
            prompt_text,
            return_tensors="pt",
            truncation=True,
            max_length=8192,
            padding=False,
        )
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        prompt_tokens = int(inputs["input_ids"].shape[-1])

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max(1, max_new_tokens),
                temperature=max(0.0, float(temperature)),
                top_p=max(0.0, min(1.0, float(top_p))),
                do_sample=float(temperature) > 0.0,
                pad_token_id=self.tokenizer.pad_token_id,
            )

        new_tokens = output_ids[0][prompt_tokens:]
        text = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        completion_tokens = int(new_tokens.shape[-1])
        return text, prompt_tokens, completion_tokens


def _get_hf_client(config: LLMConfig) -> TransformersClient:
    """返回进程级 TransformersClient 单例。"""
    global _hf_instance
    with _hf_lock:
        if _hf_instance is None:
            _hf_instance = TransformersClient(model_path=config.local_model_path)
    return _hf_instance


class TransformersLLMImpl(BaseChatModel):
    """使用 HuggingFace Transformers 的本地 LLM 实现，接口与其他实现完全一致。"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = _get_hf_client(config)
        self._temperature = float(config.api_temperature)
        self._top_p = float(config.api_top_p)
        self._max_tokens = max(1, int(config.api_max_tokens))

    def generate_response(self, user_input: str) -> str:
        messages = [self.system_message, {"role": "user", "content": user_input}]
        try:
            text, prompt_tokens, completion_tokens = self._client.chat_messages(
                messages,
                temperature=self._temperature,
                top_p=self._top_p,
                max_new_tokens=self._max_tokens,
                enable_thinking=False,
            )
            _token_tracker.record(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )
            processed = self._process_response_think_tags(text)
            return processed
        except Exception as e:
            print(f"Transformers 推理失败: {e}")
            return f"生成响应失败: {e}"


# ==============================================================================
# 主控制类：根据配置自动选择后端
#   use_local=False → OpenAILLM   (云端 API)
#   use_local=True  → TransformersLLMImpl (本地 Transformers)
# ==============================================================================
class Chatbot:
    def __init__(self, config: LLMConfig):
        if getattr(config, "use_local", False):
            self.llm_instance = TransformersLLMImpl(config)
        else:
            self.llm_instance = OpenAILLM(config)

    def chat(self, user_input: str) -> str:
        return self.llm_instance.generate_response(user_input)


 
