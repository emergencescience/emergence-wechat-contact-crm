#!/usr/bin/env python3
"""
Generic WeChat Contacts Structuring Engine (Zero PII, Fully Configurable)
Transforms unstructured contact remark lines into structured CRM entities and an interactive HTML Dashboard.

Supported generic schema:
  [Name / Nickname] + [Role / Title / Org] + [Venue / City / Event] + [Time / Date]
"""
import os
import re
import sys
import json
import csv
import argparse
from typing import List, Dict, Any, Set
from collections import Counter

# Standard generic city dictionary (Top-level administrative regions & global hubs only)
DEFAULT_CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "武汉", "苏州", "西安", "重庆", "天津",
    "青岛", "厦门", "香港", "澳门", "台北", "新加坡", "东京", "伦敦", "纽约", "旧金山"
]

# Standard generic professional titles / roles
DEFAULT_ROLES = [
    "合伙人", "创始人", "CEO", "CTO", "COO", "VP", "总监", "经理", "助理", "顾问", "架构师",
    "工程师", "开发者", "分析师", "研究员", "教授", "讲师", "律师", "法务", "医生", "设计师", "主理人", "店长", "店员", "实习生"
]

# Broad industry classification keyword mapping (Generic)
DEFAULT_INDUSTRIES = {
    "金融/投资": ["金融", "银行", "投行", "证券", "券商", "基金", "VC", "PE", "投资", "保险", "信托", "资本"],
    "科技/互联网/AI": ["AI", "算法", "大数据", "云计算", "软件", "硬件", "开发", "工程师", "产品经理", "架构师", "互联网", "芯片", "半导体"],
    "法律/法务/咨询": ["律所", "律师", "法务", "咨询", "审计", "会计", "合规"],
    "高校/科研/教育": ["大学", "学院", "高校", "研究所", "博士", "硕士", "教授", "研究员", "学者", "科研", "教育", "校友"],
    "医疗/健康/生物": ["医疗", "医药", "医院", "医生", "生物", "健康", "器械", "临床"],
    "文化/传媒/消费": ["媒体", "公关", "广告", "消费", "零售", "电商", "文娱", "艺术", "设计", "摄影", "时尚", "体育", "健身"]
}

def parse_contact_remark(
    raw: str,
    custom_cities: Set[str] = None,
    custom_roles: Set[str] = None,
    custom_venues: Set[str] = None,
    custom_orgs: Set[str] = None
) -> Dict[str, Any]:
    """
    Parse a single remark string using generic tokenization and pattern matching.
    """
    text = raw.strip()
    cities = custom_cities if custom_cities is not None else set(DEFAULT_CITIES)
    roles = custom_roles if custom_roles is not None else set(DEFAULT_ROLES)
    venues = custom_venues if custom_venues is not None else set()
    orgs = custom_orgs if custom_orgs is not None else set()
    
    # 1. Extract Time / Year (8-digit YYYYMMDD date or 4-digit year)
    time_str = ""
    date_match = re.search(r'(201[5-9]\d{4}|202[0-9]\d{4})', text)
    if date_match:
        time_str = date_match.group(1)
    else:
        year_match = re.search(r'(201[5-9]|202[0-9])', text)
        if year_match:
            time_str = year_match.group(1)
            
    # 2. Extract Venue / Event / Community tag (from custom or generic list)
    venue = ""
    for v in venues:
        if v.lower() in text.lower():
            venue = v
            break
            
    # 3. Extract City / Geo
    city = ""
    for c in cities:
        if c in text:
            city = c
            break
            
    # 4. Extract Role / Title
    role = ""
    for ro in roles:
        if ro.lower() in text.lower():
            role = ro
            break
            
    # 5. Extract Org / Company / School
    org = ""
    for o in orgs:
        if o.lower() in text.lower():
            org = o
            break
            
    # 6. Infer Industry
    industry = "其他/综合"
    for ind_name, keywords in DEFAULT_INDUSTRIES.items():
        if any(kw.lower() in text.lower() for kw in keywords):
            industry = ind_name
            break
            
    # 7. Extract Core Name (by removing extracted tokens)
    name_working = text
    if time_str:
        name_working = name_working.replace(time_str, " ")
    if venue:
        name_working = re.sub(re.escape(venue), " ", name_working, flags=re.IGNORECASE)
    if city:
        name_working = re.sub(re.escape(city), " ", name_working, flags=re.IGNORECASE)
    if role:
        name_working = re.sub(re.escape(role), " ", name_working, flags=re.IGNORECASE)
    if org:
        name_working = re.sub(re.escape(org), " ", name_working, flags=re.IGNORECASE)
        
    for ind_kws in DEFAULT_INDUSTRIES.values():
        for kw in ind_kws:
            name_working = re.sub(re.escape(kw), " ", name_working, flags=re.IGNORECASE)
            
    tokens = [t for t in re.split(r'[\s_@\-—·\[\]()（）/]+', name_working) if t]
    name = tokens[0] if tokens else text[:4]
    
    # Strip common leading prefix index like "A " or "A-"
    if len(name) > 2 and (name.startswith("A ") or name.startswith("A-")):
        name = name[2:].strip()

    return {
        "raw": raw,
        "name": name,
        "role_title": role,
        "org_school": org,
        "industry": industry,
        "venue_event": venue,
        "city": city,
        "time_met": time_str
    }

def generate_crm_dashboard(data: List[Dict[str, Any]], output_path: str):
    total = len(data)
    industries = Counter(d["industry"] for d in data if d["industry"])
    cities = Counter(d["city"] for d in data if d["city"])
    venues = Counter(d["venue_event"] for d in data if d["venue_event"])
    times = Counter(d["time_met"][:4] for d in data if d["time_met"])
    
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>微信人脉智能 CRM 资产大看板</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        .glass {{ background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(14px); border: 1px solid rgba(255, 255, 255, 0.08); }}
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-6">
    <div class="max-w-7xl mx-auto space-y-6">
        <!-- Header -->
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-4 border-b border-slate-800">
            <div>
                <h1 class="text-3xl font-bold bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent">
                    微信人脉资产智能 CRM 看板
                </h1>
                <p class="text-slate-400 text-sm mt-1">通用抽取范式：微信名 + 职位/头衔/机构 + 场景/场地 + 时间</p>
            </div>
            <div class="flex gap-3">
                <span class="px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-semibold text-sm">
                    已分析联系人: {total} 位
                </span>
            </div>
        </div>

        <!-- Metric Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div class="glass p-5 rounded-2xl">
                <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">总解析人脉</div>
                <div class="text-3xl font-bold text-white mt-2">{total}</div>
                <div class="text-xs text-emerald-400 mt-1">视频帧高精度提取</div>
            </div>
            <div class="glass p-5 rounded-2xl">
                <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">场地 / 场景标签</div>
                <div class="text-3xl font-bold text-cyan-400 mt-2">{len(venues)}</div>
                <div class="text-xs text-slate-400 mt-1">已识别场景数</div>
            </div>
            <div class="glass p-5 rounded-2xl">
                <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">主要行业 / 领域</div>
                <div class="text-3xl font-bold text-teal-400 mt-2">{len(industries)}</div>
                <div class="text-xs text-slate-400 mt-1">多维产业覆盖</div>
            </div>
            <div class="glass p-5 rounded-2xl">
                <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">时序分布 (年份标注)</div>
                <div class="text-3xl font-bold text-indigo-400 mt-2">{sum(times.values())}</div>
                <div class="text-xs text-slate-400 mt-1">时间跨度: {min(times.keys()) if times else '-'} ~ {max(times.keys()) if times else '-'}</div>
            </div>
        </div>

        <!-- Search & Filter Bar -->
        <div class="glass p-4 rounded-2xl flex flex-col md:flex-row gap-4">
            <input type="text" id="searchInput" placeholder="🔍 即时搜索姓名、职位、机构、场地/圈子、城市或原始备注..." 
                   class="flex-1 bg-slate-900/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500">
            <select id="industryFilter" class="bg-slate-900 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-300">
                <option value="">所有行业</option>
                {''.join(f'<option value="{k}">{k} ({v})</option>' for k, v in industries.most_common())}
            </select>
            <select id="cityFilter" class="bg-slate-900 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-300">
                <option value="">所有城市</option>
                {''.join(f'<option value="{k}">{k} ({v})</option>' for k, v in cities.most_common())}
            </select>
        </div>

        <!-- Contacts Table -->
        <div class="glass rounded-2xl overflow-hidden">
            <div class="overflow-x-auto max-h-[620px]">
                <table class="w-full text-left text-sm text-slate-300">
                    <thead class="bg-slate-900/90 text-xs uppercase text-slate-400 sticky top-0 backdrop-blur z-10">
                        <tr>
                            <th class="px-5 py-3.5">姓名 / 称谓</th>
                            <th class="px-5 py-3.5">职位 / 头衔 / 机构</th>
                            <th class="px-5 py-3.5">行业属性</th>
                            <th class="px-5 py-3.5">认识场地 / 场景</th>
                            <th class="px-5 py-3.5">城市</th>
                            <th class="px-5 py-3.5">时间</th>
                            <th class="px-5 py-3.5">原始微信备注</th>
                        </tr>
                    </thead>
                    <tbody id="contactTableBody" class="divide-y divide-slate-800">
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const contacts = {json.dumps(data, ensure_ascii=False)};
        
        function renderTable(list) {{
            const tbody = document.getElementById('contactTableBody');
            tbody.innerHTML = list.map(c => `
                <tr class="hover:bg-slate-800/50 transition">
                    <td class="px-5 py-3 font-semibold text-emerald-400">${{c.name || '-'}}</td>
                    <td class="px-5 py-3">
                        ${{c.role_title ? '<span class="px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20 text-xs mr-1">' + c.role_title + '</span>' : ''}}
                        ${{c.org_school ? '<span class="px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 text-xs">' + c.org_school + '</span>' : ''}}
                        ${{!c.role_title && !c.org_school ? '-' : ''}}
                    </td>
                    <td class="px-5 py-3"><span class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-xs">${{c.industry || '-'}}</span></td>
                    <td class="px-5 py-3 text-cyan-300 text-xs font-medium">${{c.venue_event ? '📍 ' + c.venue_event : '-'}}</td>
                    <td class="px-5 py-3 text-slate-300">${{c.city || '-'}}</td>
                    <td class="px-5 py-3 font-mono text-indigo-300 text-xs font-medium">${{c.time_met || '-'}}</td>
                    <td class="px-5 py-3 text-slate-400 text-xs font-mono truncate max-w-xs" title="${{c.raw}}">${{c.raw}}</td>
                </tr>
            `).join('');
        }}

        function filterContacts() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const ind = document.getElementById('industryFilter').value;
            const city = document.getElementById('cityFilter').value;
            
            const filtered = contacts.filter(c => {{
                const matchQuery = !query || c.raw.toLowerCase().includes(query) || (c.name && c.name.toLowerCase().includes(query)) || (c.org_school && c.org_school.toLowerCase().includes(query)) || (c.venue_event && c.venue_event.toLowerCase().includes(query));
                const matchInd = !ind || c.industry === ind;
                const matchCity = !city || c.city === city;
                return matchQuery && matchInd && matchCity;
            }});
            renderTable(filtered);
        }}

        document.getElementById('searchInput').addEventListener('input', filterContacts);
        document.getElementById('industryFilter').addEventListener('change', filterContacts);
        document.getElementById('cityFilter').addEventListener('change', filterContacts);

        // Initial render
        renderTable(contacts);
    </script>
</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"📊 已生成现代化 CRM 资产看板: {output_path}")

def load_custom_config(config_path: str) -> Dict[str, Set[str]]:
    """Optionally load user-defined custom venues, orgs, cities from JSON."""
    if not config_path or not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return {
                "cities": set(cfg.get("cities", [])),
                "roles": set(cfg.get("roles", [])),
                "venues": set(cfg.get("venues", [])),
                "orgs": set(cfg.get("orgs", []))
            }
    except Exception as e:
        print(f"Warning: Failed to load config file: {e}")
        return {}

def process_file(input_file: str, output_json: str, output_csv: str, output_html: str, config_file: str = ""):
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        return
        
    cfg = load_custom_config(config_file)
    custom_cities = cfg.get("cities") or None
    custom_roles = cfg.get("roles") or None
    custom_venues = cfg.get("venues") or None
    custom_orgs = cfg.get("orgs") or None
    
    with open(input_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        
    print(f"⚙️ 正在解析 {len(lines)} 位联系人备注...")
    structured_data = [
        parse_contact_remark(line, custom_cities, custom_roles, custom_venues, custom_orgs)
        for line in lines
    ]
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(structured_data, f, ensure_ascii=False, indent=2)
    print(f"💾 JSON 数据已保存: {output_json}")
    
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["raw", "name", "role_title", "org_school", "industry", "venue_event", "city", "time_met"])
        writer.writeheader()
        writer.writerows(structured_data)
    print(f"📈 CSV (Excel可用) 已保存: {output_csv}")
    
    generate_crm_dashboard(structured_data, output_html)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Structure WeChat Raw Contacts to CSV/JSON/HTML (Generic & Clean)")
    parser.add_argument("input_file", type=str, help="Path to raw contacts txt")
    parser.add_argument("--json", type=str, default="data/wechat_contacts_structured.json")
    parser.add_argument("--csv", type=str, default="data/wechat_contacts_structured.csv")
    parser.add_argument("--html", type=str, default="data/wechat_contacts_crm.html")
    parser.add_argument("--config", type=str, default="", help="Optional path to custom entities config.json")
    
    args = parser.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
    process_file(args.input_file, args.json, args.csv, args.html, args.config)
