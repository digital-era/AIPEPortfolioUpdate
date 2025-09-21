# File: api/update-portfolio.py
# 已改造为与 trigger.py 相同的 BaseHTTPRequestHandler 模式

import os
import json
import base64
from github import Github, GithubException
from datetime import datetime
from http.server import BaseHTTPRequestHandler

# 从环境变量获取配置
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://digital-era.github.io")

class handler(BaseHTTPRequestHandler):

    def _send_response(self, status_code, data=None):
        """统一发送响应的辅助函数"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        # --- 添加 CORS 头部 ---
        self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        if data:
            self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(204) # 204 No Content for preflight
        self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        """处理 POST 请求"""
        try:
            # 1. 解析请求体
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_response(400, {"error": "请求体为空"})
                return

            post_data_raw = self.rfile.read(content_length)
            body = json.loads(post_data_raw)
            
            if "portfolioData" not in body:
                self._send_response(400, {"error": "请求体中缺少 'portfolioData'"})
                return

            excel_b64_string = body["portfolioData"]
            excel_content = base64.b64decode(excel_b64_string)

            # 2. 配置 GitHub 访问
            github_token = os.environ.get("GITHUB_TOKEN")
            repo_owner = os.environ.get("GITHUB_REPO_OWNER")
            repo_pro = os.environ.get("GITHUB_REPO_NAME")

            if not all([github_token, repo_owner, repo_pro]):
                self._send_response(500, {"error": "服务器配置不完整。缺少必需的 GitHub 环境变量。"})
                return

            repo_name = f"{repo_owner}/{repo_pro}"
            g = Github(github_token)
            repo = g.get_repo(repo_name)

            # 3. 提交文件到 GitHub
            file_path = "data/AIPEPortfolio_new.xlsx"
            commit_message = f"chore: 通过 Web UI 更新投资组合数据于 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            try:
                contents = repo.get_contents(file_path, ref="main")
                repo.update_file(
                    path=contents.path,
                    message=commit_message,
                    content=excel_content,
                    sha=contents.sha,
                    branch="main"
                )
                action = "更新"
            except GithubException as e:
                if e.status == 404: # 文件不存在
                    repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=excel_content,
                        branch="main"
                    )
                    action = "创建"
                else:
                    raise e # 重新抛出其他 GitHub 异常
            
            # 4. 发送成功响应
            success_message = {
                "message": f"成功在主分支上{action}了 '{file_path}'。CI/CD 将现在开始处理。"
            }
            self._send_response(200, success_message)

        except json.JSONDecodeError:
            self._send_response(400, {"error": "请求体不是有效的 JSON 格式"})
        except Exception as e:
            error_message = {"error": f"发生了意外的服务器错误: {str(e)}"}
            self._send_response(500, error_message)

    def do_GET(self):
        """处理不被允许的 GET 请求"""
        self._send_response(405, {"error": "Method Not Allowed"})
