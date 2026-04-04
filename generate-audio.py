#!/usr/bin/env python3
"""
从 wordbook.md 动态读取同义替换组，生成 TTS 音频文件。
每次更新 wordbook.md 后运行此脚本即可同步新词音频。
语音：en-GB-RyanNeural（英式男声，接近雅思口音）
"""

import asyncio
import edge_tts
import os
import re
import json

VOICE = "en-GB-RyanNeural"
RATE  = "+0%"
BASE  = os.path.dirname(os.path.abspath(__file__))
WORDBOOK = os.path.join(BASE, "Reading", "wordbook.md")
AUDIO_DIR = os.path.join(BASE, "audio")
WORDS_JSON = os.path.join(BASE, "words.json")

def parse_wordbook():
    """解析 wordbook.md，提取同义替换组"""
    words = []
    in_table = False
    with open(WORDBOOK, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "同义替换组" in line:
                in_table = True
                continue
            if not in_table:
                continue
            if line.startswith("## ") or line == "---":
                in_table = False
                continue
            if not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p]
            if len(parts) < 2:
                continue
            zh, en = parts[0], parts[1]
            # 跳过表头行
            if "含义" in zh or "---" in zh:
                continue
            # 过滤只含中文箭头类条目（尤其是特殊备注行）
            if not re.search(r'[a-zA-Z]', en):
                continue
            # 把 = 号分割成词列表
            synonyms = [s.strip() for s in re.split(r'\s*=\s*', en) if s.strip()]
            # 去掉括号内中文注释
            synonyms = [re.sub(r'（.*?）', '', s).strip() for s in synonyms]
            synonyms = [re.sub(r'\(.*?\)', '', s).strip() for s in synonyms]
            synonyms = [s for s in synonyms if re.search(r'[a-zA-Z]', s)]
            if not synonyms:
                continue
            words.append({"zh": zh, "synonyms": synonyms})
    return words

async def gen_audio(text, path):
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(path)

async def main():
    words = parse_wordbook()
    print(f"解析到 {len(words)} 条同义替换组")

    # 为每个词和整串各生成音频
    tasks = []
    for i, w in enumerate(words):
        idx = f"{i:03d}"
        word_dir = os.path.join(AUDIO_DIR, idx)
        os.makedirs(word_dir, exist_ok=True)

        # 整串音频
        all_path = os.path.join(word_dir, "all.mp3")
        if not os.path.exists(all_path):
            text = ", ".join(w["synonyms"])
            tasks.append((f"{idx}-all", text, all_path))

        # 每个单独词的音频
        for j, syn in enumerate(w["synonyms"]):
            syn_path = os.path.join(word_dir, f"{j}.mp3")
            if not os.path.exists(syn_path):
                tasks.append((f"{idx}-{j}", syn, syn_path))

    if not tasks:
        print("所有音频已是最新，无需重新生成。")
    else:
        print(f"正在生成 {len(tasks)} 个新音频...")
        sem = asyncio.Semaphore(6)
        async def run(label, text, path):
            async with sem:
                await gen_audio(text, path)
                print(f"  ✓ {label}")
        await asyncio.gather(*[run(*t) for t in tasks])
        print("✅ 生成完成！")

    # 输出 words.json 供 HTML 读取
    with open(WORDS_JSON, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)
    print(f"✅ words.json 已更新（{len(words)} 条）")

asyncio.run(main())
