# File: api/update-portfolio.py
# This is a Vercel Serverless Function with CORRECT CORS handling

from http.server import BaseHTTPRequestHandler
import json
import base64
from github import Github, GithubException
import os
from datetime import datetime

class handler(BaseHTTPRequestHandler):

    def _set_headers(self, status_code=200):
        """
        A centralized method to set all required response headers, including CORS.
        """
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        
        # --- CORS Headers ---
        # It's crucial to handle the Origin header dynamically and securely.
        # This setup allows requests from your specified frontend origins.
        allowed_origins = os.environ.get(
            'ALLOWED_ORIGIN', 
            "https://digital-era.github.io,http://127.0.0.1:5500,http://localhost:5500"
        ).split(',')
        
        origin = self.headers.get('Origin')
        if origin in allowed_origins:
            self.send_header('Access-Control-Allow-Origin', origin)
        
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        """
        Handles CORS preflight requests sent by the browser before a POST request.
        """
        self._set_headers(204) # 204 No Content is the standard response for preflight requests.

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data)

            if 'portfolioData' not in body:
                raise ValueError("Missing 'portfolioData' in request body")
            
            excel_b64_string = body['portfolioData']
            excel_content = base64.b64decode(excel_b64_string)

            github_token = os.environ.get('GITHUB_TOKEN')
            repo_owner = os.environ.get('GITHUB_REPO_OWNER')
            repo_pro = os.environ.get('GITHUB_REPO_NAME')
            repo_name = f"{repo_owner}/{repo_pro}"
            
            if not github_token:
                raise ConnectionError("GITHUB_TOKEN environment variable is not set.")

            g = Github(github_token)
            repo = g.get_repo(repo_name)
            
            file_path = 'data/AIPEPortfolio_new.xlsx'
            commit_message = f"chore: Update portfolio data via web UI on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            try:
                contents = repo.get_contents(file_path, ref="main")
                repo.update_file(
                    path=contents.path,
                    message=commit_message,
                    content=excel_content,
                    sha=contents.sha,
                    branch="main"
                )
                action = "updated"
            except GithubException as e:
                if e.status == 404:
                    repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=excel_content,
                        branch="main"
                    )
                    action = "created"
                else:
                    raise e

            # Use the centralized header setter for the final response
            self._set_headers(200)
            response_body = {"message": f"Successfully {action} '{file_path}' on the main branch. CI/CD will now take over."}
            self.wfile.write(json.dumps(response_body).encode('utf-8'))

        except (ValueError, KeyError, ConnectionError) as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": f"An unexpected server error occurred: {str(e)}"}).encode('utf-8'))
