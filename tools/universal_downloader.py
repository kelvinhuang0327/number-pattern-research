#!/usr/bin/env python3
"""
通用網頁檔案下載器
支援輸入網址和指定檔案格式進行下載
"""

import urllib.request
import urllib.parse
import re
import os
import sys
from pathlib import Path
from html.parser import HTMLParser

class LinkExtractor(HTMLParser):
    """HTML連結提取器"""
    
    def __init__(self, base_url, file_extensions):
        super().__init__()
        self.base_url = base_url
        self.file_extensions = [ext.lower() for ext in file_extensions]
        self.links = []
    
    def handle_starttag(self, tag, attrs):
        """處理HTML標籤"""
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href':
                    # 處理相對路徑和絕對路徑
                    full_url = urllib.parse.urljoin(self.base_url, value)
                    
                    # 檢查是否符合指定的檔案格式
                    if self.is_target_file(full_url):
                        self.links.append(full_url)
    
    def is_target_file(self, url):
        """檢查URL是否為目標檔案格式"""
        url_lower = url.lower()
        
        # 檢查副檔名
        for ext in self.file_extensions:
            if url_lower.endswith(f'.{ext}'):
                return True
            # 也檢查URL中包含檔案格式的情況
            if f'.{ext}?' in url_lower or f'.{ext}#' in url_lower:
                return True
        
        return False

class UniversalDownloader:
    """通用下載器"""
    
    def __init__(self):
        self.download_dir = Path.home() / "Downloads"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
    
    def download_file(self, url, output_path=None):
        """下載單一檔案"""
        try:
            # 如果沒有指定輸出路徑，使用URL中的檔名
            if not output_path:
                filename = self.get_filename_from_url(url)
                output_path = self.download_dir / filename
            
            print(f"正在下載: {url}")
            print(f"儲存至: {output_path}")
            
            # 發送請求
            req = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                # 檢查Content-Type
                content_type = response.headers.get('Content-Type', '')
                print(f"Content-Type: {content_type}")
                
                # 讀取內容
                content = response.read()
                
                # 儲存檔案
                with open(output_path, 'wb') as f:
                    f.write(content)
                
                file_size = len(content)
                print(f"✓ 下載成功！檔案大小: {self.format_size(file_size)}")
                
                return str(output_path)
        
        except urllib.error.HTTPError as e:
            print(f"✗ HTTP錯誤 {e.code}: {e.reason}")
            return None
        except urllib.error.URLError as e:
            print(f"✗ 網路錯誤: {e.reason}")
            return None
        except Exception as e:
            print(f"✗ 下載失敗: {str(e)}")
            return None
    
    def find_and_download_files(self, url, file_extensions, download_all=False):
        """從網頁中找出所有符合格式的檔案並下載"""
        
        print(f"正在分析網頁: {url}")
        print(f"尋找檔案格式: {', '.join(file_extensions)}")
        print("-" * 50)
        
        try:
            # 獲取網頁內容
            req = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            # 提取連結
            parser = LinkExtractor(url, file_extensions)
            parser.feed(html)
            
            links = list(set(parser.links))  # 去重
            
            if not links:
                print("✗ 未找到符合格式的檔案連結")
                return []
            
            print(f"✓ 找到 {len(links)} 個符合的檔案連結")
            print()
            
            # 顯示所有連結
            for i, link in enumerate(links, 1):
                filename = self.get_filename_from_url(link)
                print(f"{i}. {filename}")
                print(f"   {link}")
            
            print()
            
            # 詢問要下載哪些檔案
            if download_all:
                selected = list(range(len(links)))
            else:
                choice = input("請選擇要下載的檔案 (輸入編號，多個用逗號分隔，或輸入 'all' 下載全部): ").strip()
                
                if choice.lower() == 'all':
                    selected = list(range(len(links)))
                else:
                    try:
                        selected = [int(x.strip()) - 1 for x in choice.split(',')]
                        selected = [i for i in selected if 0 <= i < len(links)]
                    except:
                        print("✗ 輸入格式錯誤")
                        return []
            
            # 下載選中的檔案
            downloaded = []
            print()
            print("開始下載...")
            print("-" * 50)
            
            for idx in selected:
                link = links[idx]
                result = self.download_file(link)
                if result:
                    downloaded.append(result)
                print()
            
            return downloaded
        
        except Exception as e:
            print(f"✗ 處理網頁時發生錯誤: {str(e)}")
            return []
    
    def download_direct_url(self, url, file_format=None):
        """直接下載URL指向的檔案"""
        
        # 如果指定了格式，檢查URL是否符合
        if file_format:
            url_lower = url.lower()
            if not (url_lower.endswith(f'.{file_format}') or f'.{file_format}?' in url_lower):
                print(f"⚠️  警告: URL似乎不是 .{file_format} 格式")
                confirm = input("是否仍要下載? (y/n): ").strip().lower()
                if confirm != 'y':
                    return None
        
        return self.download_file(url)
    
    def get_filename_from_url(self, url):
        """從URL中提取檔名"""
        # 移除查詢參數
        url_path = urllib.parse.urlparse(url).path
        
        # 取得檔名
        filename = os.path.basename(url_path)
        
        # 如果沒有檔名，使用預設名稱
        if not filename or '.' not in filename:
            filename = 'downloaded_file'
        
        return filename
    
    def format_size(self, size_bytes):
        """格式化檔案大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

def main():
    """主程式"""
    
    print("=" * 60)
    print("通用網頁檔案下載器")
    print("=" * 60)
    print()
    
    downloader = UniversalDownloader()
    
    # 獲取URL
    print("請輸入網址:")
    url = input("URL: ").strip()
    
    if not url:
        print("✗ 未輸入網址")
        return
    
    # 確保URL有協議
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    print()
    
    # 選擇模式
    print("請選擇下載模式:")
    print("1. 直接下載此URL的檔案")
    print("2. 從網頁中搜尋並下載指定格式的檔案")
    print()
    
    mode = input("請選擇 (1 或 2) [預設: 2]: ").strip() or "2"
    print()
    
    if mode == "1":
        # 直接下載模式
        print("請輸入檔案格式（選填，例如: pdf, csv, xlsx）:")
        file_format = input("格式: ").strip().lower()
        
        print()
        result = downloader.download_direct_url(url, file_format if file_format else None)
        
        if result:
            print()
            print("=" * 60)
            print("✓ 下載完成！")
            print(f"檔案位置: {result}")
            print("=" * 60)
    
    else:
        # 搜尋下載模式
        print("請輸入要搜尋的檔案格式（用逗號分隔，例如: pdf, csv, xlsx）:")
        formats_input = input("格式: ").strip()
        
        if not formats_input:
            print("✗ 未輸入檔案格式")
            return
        
        file_extensions = [f.strip().lower() for f in formats_input.split(',')]
        
        print()
        print("是否自動下載所有找到的檔案？")
        auto_download = input("(y/n) [預設: n]: ").strip().lower() == 'y'
        
        print()
        downloaded = downloader.find_and_download_files(url, file_extensions, auto_download)
        
        if downloaded:
            print()
            print("=" * 60)
            print(f"✓ 成功下載 {len(downloaded)} 個檔案！")
            print()
            print("檔案位置:")
            for filepath in downloaded:
                print(f"  - {filepath}")
            print("=" * 60)
        else:
            print()
            print("=" * 60)
            print("✗ 沒有下載任何檔案")
            print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ 使用者中斷")
    except Exception as e:
        print(f"\n✗ 發生錯誤: {str(e)}")
