#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从本地文件夹上传商品图片并上架到微信小店
"""
import os
import sys
sys.path.insert(0, '/home/wangziyi/.openclaw/workspace/ecommerce_agent')

from wechat_uploader import SmartWechatUploader


def find_images_in_folder(folder_path):
    """查找文件夹中的主图和详情图"""
    main_images = []
    detail_images = []
    
    if not os.path.exists(folder_path):
        print(f"错误: 文件夹不存在: {folder_path}")
        return [], []
    
    # 遍历文件夹
    for filename in os.listdir(folder_path):
        filepath = os.path.join(folder_path, filename)
        if not os.path.isfile(filepath):
            continue
        
        # 检查是否是图片（通过文件头）
        try:
            with open(filepath, 'rb') as f:
                header = f.read(8)
                is_image = False
                # JPEG: FF D8 FF
                if header[:3] == b'\xff\xd8\xff':
                    is_image = True
                # PNG: 89 50 4E 47
                elif header[:4] == b'\x89PNG':
                    is_image = True
                # WebP
                elif header[:4] == b'RIFF':
                    is_image = True
                
                if is_image:
                    # 分类
                    if filename == '主图' or filename.startswith('主图') or filename.lower().startswith('main'):
                        # 提取编号用于排序
                        try:
                            num = int(''.join(filter(str.isdigit, filename))) if any(c.isdigit() for c in filename) else 0
                            main_images.append((num, filepath))
                        except:
                            main_images.append((0, filepath))
                    elif filename.startswith('详情图') or filename.lower().startswith('detail'):
                        # 提取编号
                        try:
                            num = int(''.join(filter(str.isdigit, filename)))
                            detail_images.append((num, filepath))
                        except:
                            detail_images.append((0, filepath))
        except:
            continue
    
    # 主图和详情图都按编号排序
    main_images.sort(key=lambda x: x[0])
    detail_images.sort(key=lambda x: x[0])
    
    return [f[1] for f in main_images], [f[1] for f in detail_images]


def upload_images_from_folder(folder_path, product_name, price, stock=100):
    """
    从文件夹上传图片并创建商品
    
    Args:
        folder_path: 图片文件夹路径
        product_name: 商品名称
        price: 售价（元）
        stock: 库存数量
    """
    print(f"正在处理文件夹: {folder_path}")
    print("-" * 50)
    
    # 1. 查找图片
    main_paths, detail_paths = find_images_in_folder(folder_path)
    
    print(f"找到主图: {len(main_paths)} 张")
    for p in main_paths:
        print(f"  - {os.path.basename(p)}")
    
    print(f"找到详情图: {len(detail_paths)} 张")
    for i, p in enumerate(detail_paths[:5], 1):
        print(f"  {i}. {os.path.basename(p)}")
    if len(detail_paths) > 5:
        print(f"  ... 还有 {len(detail_paths) - 5} 张")
    
    print("-" * 50)
    
    # 检查图片数量
    if len(main_paths) < 1:
        print("❌ 错误: 至少需要1张主图")
        return None
    
    if len(detail_paths) < 1:
        print("❌ 错误: 至少需要1张详情图")
        return None
    
    # 2. 初始化上传器
    uploader = SmartWechatUploader()
    
    # 3. 尝试上传图片（如果失败则使用模板图片）
    print("\n正在上传主图...")
    main_urls = []
    upload_failed = False
    for path in main_paths:
        try:
            print(f"  上传: {os.path.basename(path)} ...", end=" ")
            url = uploader.upload_image(path)
            main_urls.append(url)
            print("✓")
        except Exception as e:
            print(f"✗ 失败: {e}")
            upload_failed = True
            break
    
    print(f"主图上传完成: {len(main_urls)}/{len(main_paths)}")
    
    # 如果上传失败，使用模板图片
    if upload_failed or len(main_urls) == 0:
        print("\n⚠️ 图片上传失败，使用模板图片...")
        try:
            config = uploader.get_template_config()
            main_urls = config.get('head_imgs', [])[:4]
            detail_urls = config.get('desc_info_imgs', [])[:10]
            print(f"  使用模板主图: {len(main_urls)} 张")
            print(f"  使用模板详情图: {len(detail_urls)} 张")
        except Exception as e:
            print(f"  获取模板失败: {e}")
            return None
    else:
        # 4. 上传详情图
        print("\n正在上传详情图...")
        detail_urls = []
        for path in detail_paths:
            try:
                print(f"  上传: {os.path.basename(path)} ...", end=" ")
                url = uploader.upload_image(path)
                detail_urls.append(url)
                print("✓")
            except Exception as e:
                print(f"✗ 失败: {e}")
                break
        
        # 如果详情图上传也失败了，使用模板
        if len(detail_urls) == 0:
            print("\n⚠️ 详情图上传失败，使用模板详情图...")
            try:
                config = uploader.get_template_config()
                detail_urls = config.get('desc_info_imgs', [])[:10]
                print(f"  使用模板详情图: {len(detail_urls)} 张")
            except:
                pass
    
    print(f"详情图上传完成: {len(detail_urls)}/{len(detail_paths)}")
    
    # 5. 创建商品
    print("\n正在创建商品...")
    product_info = {
        "name": product_name,
        "price": price,
        "stock": stock,
        "main_images": main_urls,
        "detail_images": detail_urls
    }
    
    result = uploader.smart_create_and_list(product_info)
    
    return result


def main():
    """主函数"""
    # 图片文件夹路径
    img_folder = '/home/wangziyi/桌面/上架商品图'
    
    print("=" * 60)
    print("微信小店商品上架工具")
    print("=" * 60)
    print(f"图片文件夹: {img_folder}")
    print()
    
    # 输入商品信息
    product_name = input("请输入商品名称: ").strip()
    if not product_name:
        print("错误: 商品名称不能为空")
        return
    
    try:
        price = float(input("请输入售价（元）: ").strip())
    except ValueError:
        print("错误: 价格格式不正确")
        return
    
    try:
        stock = int(input("请输入库存数量（默认100）: ").strip() or "100")
    except ValueError:
        stock = 100
    
    print()
    print("=" * 60)
    
    # 执行上架
    result = upload_images_from_folder(img_folder, product_name, price, stock)
    
    print()
    print("=" * 60)
    if result and result.get("success"):
        print("✅ 商品上架成功！")
        print(f"商品ID: {result.get('product_id')}")
        print(f"类目: {result.get('category')}")
        print(f"消息: {result.get('message')}")
    else:
        print("❌ 商品上架失败")
        if result:
            print(f"错误: {result.get('message')}")
            print(f"详情: {result.get('details')}")
    print("=" * 60)


if __name__ == '__main__':
    main()
