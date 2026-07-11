# import argparse
# import subprocess
# import logging
# from syntax_checker import SyntaxChecker
# import re

# class OutputVerifier:
#     def __init__(self, logger: logging.Logger = None, output: bool = False):
#         self.logger = logger or logging.getLogger(__name__)
#         self.output = output
#         self.syntax_error = ''
#         self.syntax_correct = False  # Initialize syntax_correct
#         self.valid_error_list = []
#         self.verify_error_list = []
#         self.verify_result = []
#         self.validate_result = []
        

#     def print_errors(self, error_list):
#         for error in error_list:
#             print(error[0].splitlines()[0])  # Print error description
#             print(error[1])  # Print error file location
#             print(error[2])  # Print error line content
#             print()
    

#     def extract_semantic_error(self, error_message):
#         # Use regular expression to extract filename and line number
#         pattern = r'file\s+([\w\/\.\-]+),\s+line\s+(\d+)'
#         match = re.search(pattern, error_message)
        
#         if match:
#             file_path = match.group(1)
#             line_number = int(match.group(2))  # Convert to integer

#             try:
#                 with open(file_path, 'r') as file:
#                     # Read all lines of the file
#                     lines = file.readlines()
#                     # Check if line number is within file range
#                     if 1 <= line_number <= len(lines):
#                         error_line = lines[line_number - 1].strip()  # Extract error line content
#                     else:
#                         error_line = None  # Line number out of range
                    
#             except FileNotFoundError:
#                 print(f"Error: File '{file_path}' not found.")
#                 return None, None

#             # Construct error location information and error line content information
#             error_location_msg = f"Error found in file: {file_path} at line: {line_number}"
#             error_content_msg = f"Error line content: {error_line}" if error_line else "Error line content: Line number out of range or file could not be read."

#             return error_location_msg, error_content_msg
        
#         else:
#             return None, None
    

#     def check_valid_pairs(self, filter_invs):
#         results = []
#         # Group by adjacent identical elements
#         for i in range(0, len(filter_invs), 2):
#             if i + 1 < len(filter_invs):
#                 if "Valid" in str(filter_invs[i]) and "Valid" in str(filter_invs[i+1]):
#                     results.append(True)
#                 else:
#                     results.append(False)
#         return results

#     def check_verify_target(self, filter_contents):
#         results = []
#         for content in filter_contents:
#             if 'Valid' in content:
#                 results.append(True)
#             else:
#                 results.append(False)
#         return results

#     def filter_goal_assertion(self, contents):
#         return [line for line in contents if line.strip().startswith("Goal Assertion (")]

#     def filter_invariant(self, contents):
#         return [line for line in contents if line.strip().startswith("Goal Establishment of Invariant") or line.strip().startswith("Goal Preservation of Invariant")]

#     def parse_args(self):
#         parser = argparse.ArgumentParser(description="Run Frama-C WP on a C file.")
#         parser.add_argument('file_name', help="Path to the C file to analyze")
#         return parser.parse_args()
    
#     def run(self, file_name=None):
#         if file_name is None:
#             args = self.parse_args()
#             file_path = args.file_name
#         else:
#             file_path = file_name

#         checker = SyntaxChecker()
#         checker.run(file_path)
#         syntax_msg = checker.syntax_msg

#         if self.logger and self.output:
#             self.logger.info(syntax_msg)

#         if syntax_msg != 'syntax Correct':
#             self.syntax_error = syntax_msg
#             self.syntax_correct = False
#         else:
#             self.syntax_correct = True
#             frama_c_command = "frama-c"
#             wp_command = [frama_c_command, "-wp", "-wp-print", "-wp-timeout", "10", "-wp-prover", "z3", "-wp-model", "Typed", file_path]
#             try:
#                 result = subprocess.run(wp_command, capture_output=True, text=True, check=True)
#                 spliter = '------------------------------------------------------------'
#                 content = result.stdout
#                 contents = content.split(spliter)

#                 filter_invs = self.filter_invariant(contents)
#                 self.validate_result = self.check_valid_pairs(filter_invs)

#                 for item in filter_invs:
#                     if 'Valid' not in item:
#                         valid_error_msg = item
#                         error_location_msg, error_content_msg = self.extract_semantic_error(valid_error_msg)
#                         self.valid_error_list.append((valid_error_msg.strip(), error_location_msg, error_content_msg))

#                 if self.logger and self.output:
#                     self.logger.info('Validate:')
#                     self.logger.info(self.validate_result)
#                     self.logger.info('')
#                     self.print_errors(self.valid_error_list)

#                 filter_contents = self.filter_goal_assertion(contents)
#                 self.verify_result = self.check_verify_target(filter_contents)

#                 for item in filter_contents:
#                     if 'Valid' not in item:
#                         verify_error_msg = item
#                         error_location_msg, error_content_msg = self.extract_semantic_error(verify_error_msg)
#                         self.verify_error_list.append((verify_error_msg.strip(), error_location_msg, error_content_msg))
#                 if self.logger and self.output:
#                     self.logger.info('Verify:')
#                     self.logger.info(self.verify_result)
#                     self.logger.info('')
#                     self.print_errors(self.verify_error_list)
#             except subprocess.CalledProcessError as e:
#                 self.syntax_error = f"Frama-C execution error: {e.stdout}"
#                 self.logger.error(self.syntax_error)
    

# if __name__ == "__main__":
#     import logging
#     logging.basicConfig(level=logging.INFO)
#     verifier = OutputVerifier(logger=logging.getLogger())
#     verifier.run()

import argparse
import subprocess
import logging
from syntax_checker import SyntaxChecker
import re

class OutputVerifier:
    def __init__(self, logger: logging.Logger = None, output: bool = False):
        self.logger = logger or logging.getLogger(__name__)
        self.output = output
        self.syntax_error = ''
        self.syntax_correct = False
        self.valid_error_list = []
        self.verify_error_list = []
        self.verify_result = []
        self.validate_result = []
        self.validate_result_by_line = {}
        # line -> {'Establishment': bool, 'Preservation': bool}（check_valid_pairs 填充）
        self.goal_status_by_line = {}

    def print_errors(self, error_list):
        for error in error_list:
            print(error[0].splitlines()[0])
            if error[1]:
                print(error[1])
            if error[2]:
                print(error[2])
            print()

    def extract_semantic_error(self, error_message):
        pattern = r'file\s+([\w\/\.\-]+),\s+line\s+(\d+)'
        match = re.search(pattern, error_message)

        if not match:
            # 无法从错误信息中解析出文件和行号，回退到原始错误描述
            desc = error_message.strip().splitlines()[0] if error_message.strip() else "Unknown error"
            return f"Location: {desc}", "Error line content: (unable to parse file/line from Frama-C output)"

        file_path = match.group(1)
        line_number = int(match.group(2))
        error_location_msg = f"Error found in file: {file_path} at line: {line_number}"

        try:
            with open(file_path, 'r') as file:
                lines = file.readlines()
                if 1 <= line_number <= len(lines):
                    error_line = lines[line_number - 1].strip()
                    return error_location_msg, f"Error line content: {error_line}"
                else:
                    return error_location_msg, "Error line content: Line number out of range."
        except FileNotFoundError:
            # 文件可能已被清理（如 batch_pipeline 临时目录），从错误描述中提取 proof obligation 信息
            proof_detail = self._extract_proof_obligation(error_message)
            content_msg = f"Error line content: (file not found) {proof_detail}" if proof_detail else "Error line content: (file not found)"
            return error_location_msg, content_msg

    def _extract_proof_obligation(self, error_message):
        """从 Frama-C 输出中提取 proof obligation 的具体内容（Prove/Goal 行）"""
        lines = error_message.strip().splitlines()
        for line in lines:
            stripped = line.strip()
            # Frama-C WP 输出中 "Prove:" 行包含需要证明的具体条件
            if stripped.startswith("Prove:"):
                return stripped
            # "Goal" 行包含 proof obligation 的描述
            if stripped.startswith("Goal") and ("Establishment" in stripped or "Preservation" in stripped or "Assertion" in stripped):
                return stripped
        return ""

    def _parse_goal_info(self, content):
        """
        从 Frama-C 输出块中解析行号和 Goal 类型。
        返回: (line_number, type_str) 或 (None, None)
        """
        # 匹配 Goal Establishment of Invariant (file ..., line 12)
        match = re.search(r'Goal\s+(Establishment|Preservation)\s+of\s+Invariant\s+\(file\s+.*,\s+line\s+(\d+)\)', content)
        if match:
            return int(match.group(2)), match.group(1)
        # Fallback: tolerate minor Frama-C output format drift.
        match = re.search(r'Goal\s+(Establishment|Preservation)\s+of\s+Invariant[\s\S]*?line\s+(\d+)', content)
        if match:
            return int(match.group(2)), match.group(1)
        return None, None

    def _is_content_valid(self, content):
        """检查内容是否验证通过"""
        # 必须包含 Valid，且不能包含 Unknown, Timeout, Failed
        # 有时 Frama-C 可能会在 Failed 的解释中包含单词 "Valid"，所以要反向检查
        if 'Valid' not in content:
            return False
        if any(bad in content for bad in ['Unknown', 'Timeout', 'Failed']):
            return False
        return True

    def check_valid_pairs(self, filter_invs):
        """
        更精准的成对检查：按行号聚合 Establishment 和 Preservation。
        只有两者都存在且都 Valid，才返回 True。
        """
        # 1. 按行号分组状态
        # 结构: { line_num: {'Establishment': False, 'Preservation': False} }
        inv_status = {}
        original_order = []  # 保持出现顺序

        for item in filter_invs:
            line, g_type = self._parse_goal_info(item)
            if line is None:
                continue

            if line not in inv_status:
                inv_status[line] = {'Establishment': False, 'Preservation': False}
                original_order.append(line)
            
            # 更新该行号对应类型的状态
            if self._is_content_valid(item):
                inv_status[line][g_type] = True
            else:
                inv_status[line][g_type] = False

        # 2. 生成结果列表 + 按行号映射
        results = []
        line_results = {}
        for line in original_order:
            status = inv_status[line]
            # 严格成对检查：必须 Establishment 和 Preservation 都是 True
            ok = bool(status['Establishment'] and status['Preservation'])
            results.append(ok)
            line_results[line] = ok

        # 暴露逐行的 Establishment/Preservation 细节（供反馈生成区分
        # "入口不成立" vs "迭代不保持"）
        self.goal_status_by_line = inv_status

        return results, line_results

    def check_verify_target(self, filter_contents):
        results = []
        for content in filter_contents:
            if self._is_content_valid(content):
                results.append(True)
            else:
                results.append(False)
        return results

    def filter_goal_assertion(self, contents):
        return [line for line in contents if line.strip().startswith("Goal Assertion (")]

    def filter_invariant(self, contents):
        return [line for line in contents if line.strip().startswith("Goal Establishment of Invariant") or line.strip().startswith("Goal Preservation of Invariant")]

    def parse_args(self):
        parser = argparse.ArgumentParser(description="Run Frama-C WP on a C file.")
        parser.add_argument('file_name', help="Path to the C file to analyze")
        return parser.parse_args()
    
    def run(self, file_name=None):
        if file_name is None:
            args = self.parse_args()
            file_path = args.file_name
        else:
            file_path = file_name
        
        # 将相对路径转换为绝对路径，确保 Frama-C 能找到文件
        import os
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        checker = SyntaxChecker()
        checker.run(file_path)
        syntax_msg = checker.syntax_msg

        if self.logger and self.output:
            self.logger.info(syntax_msg)

        if syntax_msg != 'syntax Correct':
            self.syntax_error = syntax_msg
            self.syntax_correct = False
            # 尝试从文件中提取不变量数量，以便 validate_result 长度匹配
            try:
                with open(file_path, 'r') as f:
                    code_content = f.read()
                # 使用简单的正则提取不变量数量
                inv_matches = re.findall(r'loop\s+invariant\s+[^;]+;', code_content)
                num_invariants = len(inv_matches)
                # 根据不变量数量设置 validate_result
                self.validate_result = [False] * num_invariants if num_invariants > 0 else [False]
                self.validate_result_by_line = {}
                self.goal_status_by_line = {}
            except:
                # 如果提取失败，使用默认值
                self.validate_result = [False]
                self.validate_result_by_line = {}
                self.goal_status_by_line = {}
        else:
            self.syntax_correct = True
            frama_c_command = "frama-c"
            # 确保使用绝对路径
            abs_file_path = os.path.abspath(file_path) if not os.path.isabs(file_path) else file_path
            # Use a longer timeout to reduce false negatives on nonlinear VCs.
            wp_command = [frama_c_command, "-wp", "-wp-print", "-wp-timeout", "30", "-wp-par", "8", "-wp-prover", "z3", "-wp-model", "Typed", abs_file_path]
            try:
                result = subprocess.run(wp_command, capture_output=True, text=True, check=True)
                spliter = '------------------------------------------------------------'
                content = result.stdout
                contents = content.split(spliter)

                # --- 1. Validate Invariants ---
                filter_invs = self.filter_invariant(contents)
                
                # 使用新的精准配对逻辑
                self.validate_result, self.validate_result_by_line = self.check_valid_pairs(filter_invs)

                self.valid_error_list = []
                for item in filter_invs:
                    # 依然收集所有 Invalid 的 item 作为错误详情
                    if not self._is_content_valid(item):
                        valid_error_msg = item
                        error_location_msg, error_content_msg = self.extract_semantic_error(valid_error_msg)
                        self.valid_error_list.append((valid_error_msg.strip(), error_location_msg, error_content_msg))

                if self.logger and self.output:
                    self.logger.info('Validate:')
                    self.logger.info(self.validate_result)
                    self.logger.info('')
                    self.print_errors(self.valid_error_list)

                # --- 2. Verify Assertions ---
                filter_contents = self.filter_goal_assertion(contents)
                self.verify_result = self.check_verify_target(filter_contents)
                
                self.verify_error_list = []
                for item in filter_contents:
                    if not self._is_content_valid(item):
                        verify_error_msg = item
                        error_location_msg, error_content_msg = self.extract_semantic_error(verify_error_msg)
                        self.verify_error_list.append((verify_error_msg.strip(), error_location_msg, error_content_msg))
                
                if self.logger and self.output:
                    self.logger.info('Verify:')
                    self.logger.info(self.verify_result)
                    self.logger.info('')
                    self.print_errors(self.verify_error_list)
                    
            except subprocess.CalledProcessError as e:
                self.syntax_error = f"Frama-C execution error: {e.stdout}"
                self.logger.error(self.syntax_error)
                self.validate_result = [False]
                self.validate_result_by_line = {}
                self.goal_status_by_line = {}
                self.verify_result = [False]

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    verifier = OutputVerifier(logger=logging.getLogger(), output=True)
    verifier.run("/home/yangfp/SAM2INV/loop_factory/generated/test/annotated/48.c")
