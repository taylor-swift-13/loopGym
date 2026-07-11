"""
独立的 Houdini 剪枝模块
不依赖 LLM，可用于所有生成模式

Houdini 是一种经典的不变量推断算法，通过迭代删除无法验证的不变量
"""
import re
import logging
from typing import Optional, List, Tuple
from unified_filter import validate_code_structure
from config import HOUDINI_CONFIG


class HoudiniPruner:
    """Houdini 风格的不变量剪枝器，不依赖 LLM"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化 Houdini 剪枝器
        
        Args:
            logger: 日志记录器，如果为 None 则使用默认 logger
        """
        self.logger = logger or logging.getLogger(__name__)
    
    @staticmethod
    def _extract_line_from_location(location: str) -> Optional[int]:
        if not location:
            return None
        m = re.search(r'line[:\s]+(\d+)', location)
        if m:
            return int(m.group(1))
        return None

    def _build_line_map_from_errors(self, verifier) -> dict:
        """
        Build fallback line->bool map from verifier.valid_error_list.
        Failed lines are set to False; other lines are left unspecified.
        """
        line_map = {}
        errors = getattr(verifier, "valid_error_list", []) or []
        for _desc, location, _content in errors:
            line_no = self._extract_line_from_location(location or "")
            if line_no is not None:
                line_map[line_no] = False
        return line_map

    def hudini_annotations(
        self,
        validate_result: List[bool],
        annotations: str,
        validate_result_by_line: Optional[dict] = None,
    ) -> str:
        """
        根据验证结果删除失败的不变量 (Houdini-style pruning)
        
        Args:
            validate_result: 布尔值列表，表示每个不变量是否通过验证（必须与不变量数量匹配）
            annotations: 带有 ACSL 注解的 C 代码
            
        Returns:
            删除失败不变量后的代码。如果所有不变量都被删除，则整个 /*@ */ 块也会被删除。
        """
        # 构建匹配 loop invariant 语句的正则表达式
        # 改进版本：正确处理复杂不变量（包含 &&、括号等）
        pattern = re.compile(
            r'^(\s*)loop\s+invariant\s+([^;]+?);', 
            flags=re.MULTILINE
        )
        
        # 找到所有不变量
        matches = list(pattern.finditer(annotations))
        
        # If no line-based results are available, fall back to positional mapping.
        has_line_map = isinstance(validate_result_by_line, dict) and len(validate_result_by_line) > 0
        positional_results = list(validate_result)
        if (not has_line_map) and len(validate_result) != len(matches):
            self.logger.warning(
                f"validate_result count ({len(validate_result)}) doesn't match invariants count ({len(matches)}); "
                "using conservative positional fallback"
            )
            # Conservative fallback: only trust overlap region; keep extra invariants.
            n = min(len(validate_result), len(matches))
            positional_results = list(validate_result[:n]) + [True] * (len(matches) - n)
        
        # 使用索引跟踪当前匹配项
        current_index = [0]  # 使用列表以便在闭包中修改值
        
        # 替换处理函数
        def replacer(match):
            idx = current_index[0]
            current_index[0] += 1

            # Prefer line-based mapping to avoid ordering mismatch between
            # Frama-C goals and source invariant order.
            if has_line_map:
                line_no = annotations.count('\n', 0, match.start()) + 1
                should_keep = validate_result_by_line.get(line_no, True)
            else:
                should_keep = positional_results[idx]

            # 返回空字符串删除 False 项，保留 True 项
            return '' if not should_keep else match.group(0)
        
        # 执行全局替换
        result = pattern.sub(replacer, annotations)
        
        # 检查是否所有不变量都被删除
        remaining_invariants = self._extract_invariants_from_code(result)
        if len(remaining_invariants) == 0:
            # 如果所有不变量都被删除，删除整个 /*@ */ 块
            acsl_block_pattern = re.compile(r'/\*@\s*[\s\S]*?\*/\s*', re.MULTILINE)
            result = acsl_block_pattern.sub('', result)
            self.logger.warning("All invariants were removed, deleted entire /*@ */ block")
        
        return result
    
    def hudini(self, code: str, verifier, c_file_path: str, **kwargs) -> Tuple[Optional[str], bool]:
        """
        Houdini 风格的迭代剪枝：重复删除失败的不变量直到全部通过或删空

        算法保证终止：每次迭代至少移除一个不变量，所以最多迭代次数等于不变量数量。

        Args:
            code: 初始代码（必须是完整的函数定义）
            verifier: 验证器实例（需要有 run() 方法和 validate_result 属性）
            c_file_path: 临时 C 文件路径

        Returns:
            剪枝后的代码和验证状态元组 (code, is_valid)，如果所有不变量都被删除则返回 (None, False)

        kwargs:
            record: 可选 dict。传入时逐轮追加 record['rounds'] = [{'invariants': [...],
                    'validate_result': [...]}]（位置一一对应）。第 0 轮的 False 项是
                    "铁拒"——以全集为归纳假设仍失败；之后轮次的 False 多为陪葬者。
        """
        record = kwargs.get('record')
        # 验证输入代码是完整的函数
        if not code or not code.strip():
            self.logger.error("Houdini received empty code")
            return None, False

        # 检查是否包含函数定义
        if not re.search(r'\b(?:void|int|char|long|short|double|float)\s+\w+\s*\(', code):
            self.logger.error("Houdini received incomplete code (no function definition)")
            self.logger.error(f"First 500 chars of received code:\n{code[:500]}")
            return None, False

        current_code = code
        valid = False
        iteration = 0
        no_progress_count = 0
        max_iterations = HOUDINI_CONFIG.get('max_iterations', 500)
        patience = HOUDINI_CONFIG.get('patience', 2)

        while True:
            # 在写入文件前验证代码结构
            code_violations = validate_code_structure(current_code)
            if code_violations:
                self.logger.error(f"Code structure validation failed before writing to file:")
                for violation in code_violations:
                    self.logger.error(f"  - {violation.type.value}: {violation.message}")
                return None, False

            # 写入文件并验证
            with open(c_file_path, 'w') as f:
                f.write(current_code)

            # 调试：打印写入文件的前几行，确保是完整函数
            if iteration == 0:
                lines = current_code.split('\n')
                self.logger.info(f"DEBUG: First 10 lines of code written to file:")
                for i, line in enumerate(lines[:10], 1):
                    self.logger.info(f"  {i}: {line}")
                self.logger.info(f"DEBUG: Total lines: {len(lines)}")

            # 每次剪枝迭代后重新验证
            verifier.run(c_file_path)

            # 获取验证结果
            validate_result = verifier.validate_result

            if record is not None:
                record.setdefault('rounds', []).append({
                    'invariants': self._extract_invariants_from_code(current_code),
                    'validate_result': list(validate_result or []),
                })

            if not validate_result:
                break

            # 检查是否所有不变量都有效
            valid = bool(validate_result) and all(validate_result)

            if valid:
                self.logger.info(f"Houdini iteration {iteration + 1}: All invariants are valid")
                break

            # 使用 Houdini 删除失败的不变量（按位置匹配，避免行号映射失效）
            before_invariants = self._extract_invariants_from_code(current_code)
            prev_code = current_code
            current_code = self.hudini_annotations(
                validate_result,
                current_code,
                validate_result_by_line=None,
            )
            after_invariants = self._extract_invariants_from_code(current_code)

            failed_count = sum(1 for v in validate_result if not v)
            self.logger.info(f"Houdini iteration {iteration + 1}: Removed {failed_count} failed invariants")
            self.logger.info(f"  Before: {len(before_invariants)} invariants")
            self.logger.info(f"  After: {len(after_invariants)} invariants")

            if current_code == prev_code:
                no_progress_count += 1
                self.logger.warning(
                    f"Houdini: code unchanged after annotation removal "
                    f"(no-progress {no_progress_count}/{patience})."
                )
                if no_progress_count >= patience:
                    self.logger.warning("Houdini: patience exhausted; stopping.")
                    break
                continue

            # 检查是否所有不变量都被删除
            if len(after_invariants) == 0:
                self.logger.error("All invariants were removed by Houdini")
                return None, False

            if after_invariants:
                self.logger.info("  Remaining invariants:")
                for i, inv in enumerate(after_invariants, 1):
                    self.logger.info(f"    [{i}] {inv}")

            iteration += 1
            if iteration >= max_iterations:
                self.logger.error(
                    f"Houdini: reached maximum iteration limit ({max_iterations}). "
                    "Aborting to prevent infinite loop."
                )
                return None, False

        return current_code, valid
    
    def _extract_invariants_from_code(self, code: str) -> List[str]:
        """
        从代码中提取所有不变量表达式
        
        Args:
            code: C 代码字符串
            
        Returns:
            不变量表达式列表
        """
        # 匹配所有 loop invariant 语句
        inv_pattern = re.compile(r'loop\s+invariant\s+([^;]+);', re.DOTALL)
        matches = inv_pattern.findall(code)
        
        # 清理不变量（去除多余空白）
        invariants = [inv.strip() for inv in matches]
        return invariants
