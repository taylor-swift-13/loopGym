import subprocess
import argparse
from run_dirs import resolve_verified_output_path

class SyntaxChecker:
    def __init__(self):
        self.syntax_msg = ""  # Used to store all output content

    def parse_args(self):
        """Set up command line argument parser"""
        parser = argparse.ArgumentParser(description="Run Frama-C WP on a C file.")
        parser.add_argument('file_name', help="Path to the C file to analyze")
        return parser.parse_args()

    def _save_verified_file(self, file_path):
        """保存 Frama-C 验证的文件到 output 目录"""
        try:
            # 读取文件内容
            with open(file_path, 'r') as f:
                file_content = f.read()
            
            # 统一保存路径（避免回落到 output 根目录）
            output_path = resolve_verified_output_path(file_path)
            
            # 保存文件
            with open(output_path, 'w') as f:
                f.write(file_content)
            
        except Exception as e:
            print(f"[DEBUG] Failed to save verified file: {e}")

    def run(self, file_name=None):
        """Run Frama-C WP command and process output"""
        if file_name is None:
            # If no file_name passed, get from command line arguments
            args = self.parse_args()
            file_path = args.file_name
        else:
            # If file_name passed, use it directly
            file_path = file_name

        # 保存文件到 output 目录（无论成功或失败）
        self._save_verified_file(file_path)

        # Parse-only syntax check delegated to Frama-C's OWN front-end (no heuristic
        # string matching): `-print` parses the C + ACSL and exits non-zero if it
        # cannot.  `-kernel-warn-key annot-error=abort` promotes a malformed ACSL
        # annotation from a warning to a hard (non-zero) error, so the exit code is
        # the sole, authoritative syntax verdict.
        wp_command = [
            "frama-c",
            "-kernel-warn-key", "annot-error=abort",
            "-print",
            file_path,
        ]

        try:
            result = subprocess.run(wp_command, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                self.syntax_msg = "syntax Correct"
            else:
                self.syntax_msg = "syntax Error\n" + (result.stdout + result.stderr)[:1000]
        except Exception as e:
            self.syntax_msg = "syntax Error\n" + str(e)


if __name__ == "__main__":
    checker = SyntaxChecker()
    checker.run()
