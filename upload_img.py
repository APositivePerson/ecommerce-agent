#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信小店图片上传模块
"""
import os
import requests
import logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class WechatImageUploader:
    """微信小店图片上传器"""
    
    def __init__(self, access_token: str, upload_url: str = None):
        self.access_token = access_token
        self.upload_url = upload_url or "https://api.weixin.qq.com/channels/ec/basics/img/upload"
    
    def _get_mime_type(self, img_path: str) -> str:
        """根据文件内容判断MIME类型"""
        try:
            with open(img_path, 'rb') as f:
                header = f.read(8)
                # JPEG: FF D8 FF
                if header[:3] == b'\xff\xd8\xff':
                    return 'image/jpeg'
                # PNG: 89 50 4E 47
                elif header[:4] == b'\x89PNG':
                    return 'image/png'
                # WebP: 52 49 46 46 ... 57 45 42 50
                elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
                    return 'image/webp'
                # GIF: 47 49 46 38
                elif header[:4] == b'GIF8':
                    return 'image/gif'
        except:
            pass
        
        # 默认返回jpeg
        return 'image/jpeg'
    
    def upload_image(self, img_path: str) -> Optional[str]:
        """
        上传单张图片到微信小店
        
        Args:
            img_path: 图片文件路径
            
        Returns:
            图片URL，上传失败返回None
        """
        if not os.path.exists(img_path):
            logger.error(f"图片文件不存在: {img_path}")
            return None
        
        url = f"{self.upload_url}?access_token={self.access_token}"
        
        try:
            # 获取文件名
            filename = os.path.basename(img_path)
            # 如果没有扩展名，添加.jpg
            if '.' not in filename:
                filename += '.jpg'
            
            # 获取MIME类型
            mime_type = self._get_mime_type(img_path)
            
            with open(img_path, 'rb') as f:
                files = {'media': (filename, f, mime_type)}
                response = requests.post(url, files=files, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                
                if result.get('errcode') == 0:
                    img_url = result.get('data', {}).get('img_url')
                    logger.info(f"图片上传成功: {os.path.basename(img_path)} -> {img_url}")
                    return img_url
                else:
                    logger.error(f"图片上传失败: {result.get('errmsg')} (errcode: {result.get('errcode')})")
                    return None
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"上传请求异常: {e}")
            return None
        except Exception as e:
            logger.error(f"上传图片时发生错误: {e}")
            return None
    
    def upload_images(self, img_paths: List[str]) -> List[str]:
        """
        批量上传图片
        
        Args:
            img_paths: 图片文件路径列表
            
        Returns:
            成功上传的图片URL列表
        """
        urls = []
        for img_path in img_paths:
            url = self.upload_image(img_path)
            if url:
                urls.append(url)
        return urls


def find_image_files(base_path: str, filename: str, extensions: List[str]) -> List[str]:
    """
    查找图片文件
    
    Args:
        base_path: 基础目录
        filename: 文件名（不含扩展名）
        extensions: 扩展名列表
        
    Returns:
        找到的图片文件路径列表
    """
    found_files = []
    
    for ext in extensions:
        full_path = os.path.join(base_path, f"{filename}{ext}")
        if os.path.exists(full_path):
            found_files.append(full_path)
            break
    
    return found_files


def find_detail_images(base_path: str, prefix: str, extensions: List[str]) -> List[str]:
    """
    查找详情图文件（支持详情图1, 详情图2...命名）
    
    Args:
        base_path: 基础目录
        prefix: 文件名前缀
        extensions: 扩展名列表
        
    Returns:
        找到的图片文件路径列表（按编号排序）
    """
    found_files = []
    
    # 遍历目录中的所有文件
    if not os.path.exists(base_path):
        return found_files
    
    for filename in os.listdir(base_path):
        # 检查是否匹配前缀
        if filename.startswith(prefix):
            # 提取编号
            remaining = filename[len(prefix):]
            # 去掉扩展名
            for ext in extensions:
                if remaining.endswith(ext):
                    remaining = remaining[:-len(ext)] if ext else remaining
                    break
            
            # 尝试解析编号
            try:
                num = int(remaining)
                full_path = os.path.join(base_path, filename)
                found_files.append((num, full_path))
            except ValueError:
                continue
    
    # 按编号排序
    found_files.sort(key=lambda x: x[0])
    return [f[1] for f in found_files]


def find_main_images(base_path: str, config: dict) -> List[str]:
    """
    查找主图文件
    
    Args:
        base_path: 基础目录
        config: 主图配置
        
    Returns:
        找到的主图文件路径列表
    """
    filename = config.get('filename', '主图')
    extensions = config.get('extensions', ['', '.jpg', '.jpeg', '.png', '.webp'])
    
    found_files = []
    
    # 首先查找精确匹配的文件（包括无扩展名的情况）
    for ext in extensions:
        full_path = os.path.join(base_path, f"{filename}{ext}")
        if os.path.exists(full_path):
            found_files.append(full_path)
            break
    
    # 如果没有找到，尝试查找 主图1, 主图2... 格式
    if not found_files:
        found_files = find_detail_images(base_path, filename, extensions)
    
    return found_files


def get_all_images_in_folder(base_path: str) -> Dict[str, List[str]]:
    """
    获取文件夹中所有图片，自动分类为主图和详情图
    支持命名格式: 主图、主图1、主图2... 详情图1、详情图2...
    
    Args:
        base_path: 图片文件夹路径
        
    Returns:
        包含主图和详情图路径的字典
    """
    main_imgs = []
    detail_imgs = []
    
    if not os.path.exists(base_path):
        return {'main': [], 'detail': []}
    
    for filename in os.listdir(base_path):
        filepath = os.path.join(base_path, filename)
        if not os.path.isfile(filepath):
            continue
        
        # 检查是否是图片文件（通过扩展名或文件头）
        is_image = False
        lower_name = filename.lower()
        
        # 通过扩展名判断
        image_exts = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
        for ext in image_exts:
            if lower_name.endswith(ext):
                is_image = True
                break
        
        # 如果没有扩展名，尝试读取文件头
        if not is_image and '.' not in filename:
            try:
                with open(filepath, 'rb') as f:
                    header = f.read(8)
                    # JPEG: FF D8 FF
                    # PNG: 89 50 4E 47
                    # WebP: 52 49 46 46 ... 57 45 42 50
                    if header[:3] == b'\xff\xd8\xff' or header[:4] == b'\x89PNG' or (header[:4] == b'RIFF' and header[8:12] == b'WEBP'):
                        is_image = True
            except:
                pass
        
        if is_image:
            # 分类为主图或详情图
            if filename == '主图' or filename.startswith('主图') or filename.lower().startswith('main'):
                # 提取编号用于排序
                try:
                    num = int(''.join(filter(str.isdigit, filename))) if any(c.isdigit() for c in filename) else 0
                    main_imgs.append((num, filepath))
                except:
                    main_imgs.append((0, filepath))
            elif filename.startswith('详情图') or filename.lower().startswith('detail'):
                # 提取编号
                try:
                    prefix = '详情图'
                    if filename.startswith(prefix):
                        num_str = filename[len(prefix):]
                        # 去掉可能的扩展名
                        for ext in image_exts:
                            if num_str.lower().endswith(ext):
                                num_str = num_str[:-len(ext)]
                                break
                        num = int(num_str)
                        detail_imgs.append((num, filepath))
                    else:
                        # 对于 detailX 格式
                        num = int(''.join(filter(str.isdigit, filename)))
                        detail_imgs.append((num, filepath))
                except:
                    detail_imgs.append((0, filepath))
    
    # 主图和详情图都按编号排序
    main_imgs.sort(key=lambda x: x[0])
    detail_imgs.sort(key=lambda x: x[0])
    
    return {
        'main': [f[1] for f in main_imgs],
        'detail': [f[1] for f in detail_imgs]
    }
