#!/usr/bin/env python3
"""
Process WeChat Contact List Screen Recording Video into deduplicated raw contacts list.
Utilizes ffmpeg for high-FPS frame extraction and native Apple Vision OCR.
"""
import os
import sys
import json
import subprocess
import time
import argparse
from typing import List, Dict, Set, Tuple

def extract_frames(video_path: str, output_dir: str, fps: float = 40.0) -> List[str]:
    """Extract frames from video using ffmpeg at target fps."""
    os.makedirs(output_dir, exist_ok=True)
    for f in os.listdir(output_dir):
        if f.endswith('.png') or f.endswith('.jpg'):
            os.remove(os.path.join(output_dir, f))
            
    print(f"🎬 正在从视频提取关键帧: {video_path} (采样率: {fps} FPS)...")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        os.path.join(output_dir, "frame_%04d.jpg")
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    frames = sorted([os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")])
    print(f"✅ 成功提取 {len(frames)} 张画面帧！")
    return frames

def clean_contact_text(t: str) -> str:
    """Clean contact remarks by removing UI noise, section headers, and counters."""
    t = t.strip()
    if not t or t.lower() in ["contacts", "通讯录", "新的朋友", "群聊", "标签", "公众号"] or t.isdigit():
        return ""
    if len(t) == 1 and t.isalpha(): # A-Z header
        return ""
    return t

def process_video_pipeline(video_path: str, output_raw: str, fps: float = 40.0, temp_frames_dir: str = "cache/wechat_frames"):
    if not os.path.exists(video_path):
        print(f"Error: Video not found at {video_path}")
        sys.exit(1)
        
    frames = extract_frames(video_path, temp_frames_dir, fps=fps)
    if not frames:
        print("Error: No frames extracted from video.")
        sys.exit(1)
        
    # Compile OCR tool if not present
    script_dir = os.path.dirname(os.path.abspath(__file__))
    swift_src = os.path.join(script_dir, "mac_ocr_fast.swift")
    ocr_bin = os.path.join(script_dir, "mac_ocr_fast")
    
    if not os.path.exists(ocr_bin) and os.path.exists(swift_src):
        print("🔨 编译高并发 Apple Vision OCR 引擎 (8 线程)...")
        subprocess.run(["swiftc", "-O", "-whole-module-optimization", swift_src, "-o", ocr_bin], check=True)
        
    print(f"\n🔍 正在通过 Apple Vision 引擎进行高精 OCR 与多帧去重分析...")
    t0 = time.time()
    
    # Process in batches
    chunk_size = 80
    results_by_frame: Dict[str, List[str]] = {}
    
    for i in range(0, len(frames), chunk_size):
        chunk = frames[i:i+chunk_size]
        proc = subprocess.run([ocr_bin] + chunk, capture_output=True, text=True, check=True)
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                results_by_frame[data["file"]] = data["contacts"]
            except Exception:
                pass
                
    elapsed = time.time() - t0
    
    all_contacts: List[str] = []
    seen: Set[str] = set()
    
    prev_frame_contacts: List[str] = []
    overlap_counts: List[int] = []
    total_in_frame_counts: List[int] = []
    zero_overlap_count = 0
    
    # Iterate in temporal order
    for idx, frame_path in enumerate(frames, 1):
        fname = os.path.basename(frame_path)
        raw_items = results_by_frame.get(fname, [])
        cleaned_items = [clean_contact_text(c) for c in raw_items if clean_contact_text(c)]
        total_in_frame_counts.append(len(cleaned_items))
        
        if prev_frame_contacts and cleaned_items:
            overlap = len(set(cleaned_items) & set(prev_frame_contacts))
            overlap_counts.append(overlap)
            if overlap == 0:
                zero_overlap_count += 1
                
        for c in cleaned_items:
            if c not in seen:
                seen.add(c)
                all_contacts.append(c)
                
        prev_frame_contacts = cleaned_items

    # Save deduplicated raw contacts
    os.makedirs(os.path.dirname(os.path.abspath(output_raw)), exist_ok=True)
    with open(output_raw, "w", encoding="utf-8") as f:
        for c in all_contacts:
            f.write(c + "\n")
            
    avg_per_frame = sum(total_in_frame_counts) / max(1, len(total_in_frame_counts))
    avg_overlap = sum(overlap_counts) / max(1, len(overlap_counts)) if overlap_counts else 0
    min_overlap = min(overlap_counts) if overlap_counts else 0
    max_overlap = max(overlap_counts) if overlap_counts else 0
    overlap_ratio = (avg_overlap / avg_per_frame * 100) if avg_per_frame > 0 else 0
    
    print("\n" + "=" * 65)
    print(f"🎉 视频解析完毕！OCR 总耗时: {elapsed:.2f} 秒")
    print(f"📊 帧率与重复率 (Overlap) 统计：")
    print(f"   • 分析画面总帧数: {len(frames)} 帧 (@{fps} FPS)")
    print(f"   • 单帧平均可见联系人: {avg_per_frame:.1f} 人/帧")
    print(f"   • 相邻两帧平均重叠人数: {avg_overlap:.1f} 人 (重叠率: {overlap_ratio:.1f}%)")
    print(f"   • 重叠区间范围: 最小 {min_overlap} 人，最大 {max_overlap} 人")
    print(f"   • 跳帧 (重叠数=0) 次数: {zero_overlap_count} 次")
    print(f"   • 最终捕获唯一有效联系人: {len(all_contacts)} 位")
    print(f"   • 原始文本已保存至: {output_raw}")
    print("=" * 65)
    
    return all_contacts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process WeChat Contacts Video to Raw Text List")
    parser.add_argument("video_path", type=str, help="Path to screen recording .mov / .mp4")
    parser.add_argument("--output", type=str, default="data/wechat_contacts_raw.txt", help="Output raw text file path")
    parser.add_argument("--fps", type=float, default=40.0, help="Sampling FPS for frame extraction")
    parser.add_argument("--cache-dir", type=str, default="cache/wechat_frames", help="Directory for temporary frame images")
    
    args = parser.parse_args()
    process_video_pipeline(args.video_path, args.output, fps=args.fps, temp_frames_dir=args.cache_dir)
