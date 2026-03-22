#!/usr/bin/env python3
"""
Millimeter Wave Radar Daily Report Generator v2.3
Automatically collect global data and generate technical daily reports
Author: pengong101
License: MIT

Changelog v2.3:
- Optimized keywords for automotive radar focus
- Added content quality scoring system
- Filter out 5G/telecom irrelevant content
- Added title blacklist filter
- Positive keywords: 车载，汽车，automotive, 77GHz, ADAS, etc.
- Negative keywords: 5G, 通信，telecom, 基站，WiFi, etc.
- Title blacklist: printf, 机场，如何评价，etc.

Changelog v2.2:
- Added multi-strategy date parsing (API/URL/content)
- Added date-based filtering (MIN_YEAR, MAX_AGE_DAYS)
- Results sorted by recency
- Better date extraction from Chinese content

Changelog v2.1:
- Removed Brave engine (no API subscription)
- Added exact match quotes for keywords
- Excluded low-quality content (百度知道)
- Added time range filter (last 7 days)
- Optimized engine selection (baidu, bing, google)
"""

import requests
import json
from datetime import datetime, timedelta
import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib
import time

# Configuration
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/root/.openclaw/workspace/radar-reports")
# 使用容器网络访问（SearXNG 和 OpenClaw 在同一网络）
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng:8080")
# 搜索引擎配置：排除 brave（无 API），优先专业引擎
SEARCH_ENGINES = ["baidu", "bing", "google"]  # 国内 + 国际引擎组合
SEARCH_PARAMS = {"engines": ",".join(SEARCH_ENGINES)}
CACHE_DIR = os.environ.get("CACHE_DIR", "/tmp/radar-cache")
CACHE_EXPIRY = int(os.environ.get("CACHE_EXPIRY", "3600"))  # 1 hour default
# 搜索优化配置
SEARCH_TIME_RANGE = "week"  # 只搜索最近 7 天的内容 (SearXNG 格式：day/week/month/year)
EXCLUDE_SITES = ["百度知道"]  # 排除低质量内容
# 日期过滤配置
MIN_YEAR = 2025  # 只保留 2025 年及以后的内容
PREFER_DAYS = 30  # 优先保留最近 30 天的内容
MAX_AGE_DAYS = 365  # 最大允许年龄（超过则过滤）

# 内容质量评分配置
POSITIVE_KEYWORDS = [
    '车载', '汽车', 'automotive', 'vehicle', '77GHz', '24GHz',
    '智能驾驶', '自动驾驶', 'ADAS', 'AEB', '盲区监测',
    '传感器', 'sensor', '雷达模块', 'radar module',
    '造车', '车企', 'Tesla', '华为', '小鹏', '理想', '蔚来',
    '毫米波', 'mmWave', 'radar', '雷达', '探测', 'detection',
    '4D 成像', '4D imaging', 'MIMO', '波束成形', 'beamforming'
]
NEGATIVE_KEYWORDS = [
    '5G', '通信', 'telecom', '基站', 'base station',
    '手机', 'mobile phone', 'WiFi', '无线传输',
    '路由器', 'network', 'coverage', 'spectrum',
    '机场', 'airport', '小红书', '评价', '如何评价'
]
QUALITY_THRESHOLD = -1  # 质量分低于此值则过滤

# 标题过滤黑名单（直接排除）
TITLE_BLACKLIST = [
    'printf', 'c 语言', '编程', 'code', 'programming',
    '机场等级', '4D 机场', '4C 机场', '4E 机场', '4F 机场',
    '如何评价', '怎么样', '好不好', '小红书',
    '%4d', '%d', 'format', '格式化',
    '4DX 电影', '3D 电影', 'movie', 'film'
]

@dataclass
class SearchResult:
    """Search result data structure"""
    title: str
    url: str
    content: str
    source: str
    published_date: Optional[str] = None
    score: float = 0.0

@dataclass
class DailyReport:
    """Daily report structure"""
    date: str
    title: str
    sections: Dict[str, List[SearchResult]]
    summary: str
    generated_at: str
    total_items: int

class RadarReportGenerator:
    """Millimeter wave radar daily report generator v2.0"""
    
    def __init__(self, searxng_url: str = SEARXNG_URL, cache_enabled: bool = True):
        """
        Initialize report generator
        
        Args:
            searxng_url: SearXNG search engine URL
            cache_enabled: Enable result caching
        """
        self.searxng_url = searxng_url
        self.cache_enabled = cache_enabled
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; RadarReportBot/2.0; +https://github.com/pengong101/radar-daily-report)'
        })
        
        # Search keywords by category (使用精确匹配 + 排除低质内容 + 聚焦车载/传感应用)
        self.keywords = {
            'industry': [
                '"毫米波雷达" 车载 2026 -百度知道 -5G',
                '"77GHz radar" automotive -百度知道 -5G',
                '"4D imaging radar" 汽车 量产 -百度知道',
                '"毫米波雷达" 智能驾驶 2026 -百度知道',
                '"automotive radar" market 2026 -百度知道 -5G'
            ],
            'academic': [
                '"毫米波雷达" 信号处理 -百度知道 -5G',
                '"mmWave radar" signal processing automotive -百度知道',
                '"MIMO radar" 车载 -百度知道',
                '"4D radar" point cloud automotive -百度知道',
                '"radar target detection" algorithm automotive -百度知道'
            ],
            'patents': [
                '"毫米波雷达" 专利 车载 -百度知道',
                '"mmWave radar" patent automotive -百度知道',
                '"radar antenna" 汽车 专利 -百度知道',
                '"77GHz" 雷达 专利 -百度知道 -5G'
            ],
            'products': [
                '"毫米波雷达" 模块 车载 2026 -百度知道',
                '"77GHz radar" sensor automotive -百度知道',
                '"automotive radar" supplier 2026 -百度知道',
                '"radar chip" 车规级 -百度知道 -5G'
            ]
        }
    
    def search(self, query: str, engines: List[str] = None, max_results: int = 10, time_range: str = None) -> List[SearchResult]:
        """
        Search using SearXNG
        
        Args:
            query: Search query
            engines: List of search engines to use
            max_results: Maximum results to return
            time_range: Time range filter (default: SEARCH_TIME_RANGE)
                        SearXNG format: 'day', 'week', 'month', 'year'
            
        Returns:
            List of SearchResult objects
        """
        if time_range is None:
            time_range = SEARCH_TIME_RANGE
        
        # Check cache first
        cache_key = hashlib.md5(f"{query}:{json.dumps(engines)}:{time_range}".encode()).hexdigest()
        if self.cache_enabled:
            cached = self._get_cache(cache_key)
            if cached:
                return cached
        
        # Perform search with time filter
        params = {
            'q': query,
            'format': 'json',
            'pageno': 1,
            'time_range': time_range  # SearXNG format: day/week/month/year
        }
        if engines:
            params['engines'] = ','.join(engines)
        
        try:
            response = self.session.get(f"{self.searxng_url}/search", params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get('results', [])[:max_results * 2]:  # 获取更多内容用于过滤
                # 过滤掉百度知道的低质量内容
                title = item.get('title', '')
                url = item.get('url', '')
                if '百度知道' in title or 'zhidao.baidu.com' in url:
                    continue
                
                result = SearchResult(
                    title=title,
                    url=url,
                    content=item.get('content', '')[:200],
                    source=item.get('engine', 'unknown'),
                    published_date=item.get('publishedDate', None),
                    score=item.get('score', 0.0)
                )
                results.append(result)
                
                if len(results) >= max_results:
                    break
            
            # Cache results
            if self.cache_enabled:
                self._set_cache(cache_key, results)
            
            return results
            
        except Exception as e:
            print(f"Search error for '{query}': {e}")
            return []
    
    def generate_report(self, date: str = None) -> DailyReport:
        """
        Generate daily report
        
        Args:
            date: Report date (YYYY-MM-DD), default today
            
        Returns:
            DailyReport object
        """
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"🔍 Generating radar daily report for {date}...")
        
        sections = {}
        total_items = 0
        
        # Search each category
        for category, keywords in self.keywords.items():
            print(f"  Searching {category}...")
            results = []
            
            for keyword in keywords[:3]:  # Top 3 keywords per category
                search_results = self.search(keyword, engines=SEARCH_ENGINES, max_results=8, time_range=SEARCH_TIME_RANGE)
                results.extend(search_results)
                time.sleep(0.5)  # Rate limiting
            
            # Remove duplicates
            unique_results = self._deduplicate(results)
            
            # Filter by date (remove old content)
            date_filtered = self._filter_by_date(unique_results)
            
            # Filter by quality (remove irrelevant content like 5G telecom)
            quality_filtered = self._filter_by_quality(date_filtered)
            
            # Take top 10 (sorted by quality, then by date)
            sections[category] = quality_filtered[:10]
            total_items += len(sections[category])
            
            print(f"    Found {len(results)} → {len(unique_results)} unique → {len(date_filtered)} date OK → {len(quality_filtered)} quality OK")
        
        # Generate summary
        summary = self._generate_summary(sections, date)
        
        report = DailyReport(
            date=date,
            title=f"Millimeter Wave Radar Daily Report - {date}",
            sections=sections,
            summary=summary,
            generated_at=datetime.now().isoformat(),
            total_items=total_items
        )
        
        return report
    
    def save_report(self, report: DailyReport, output_dir: str = OUTPUT_DIR) -> str:
        """
        Save report to file
        
        Args:
            report: DailyReport object
            output_dir: Output directory
            
        Returns:
            Output file path
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Save as Markdown
        output_file = os.path.join(output_dir, f"radar-daily-{report.date}.md")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# {report.title}\n\n")
            f.write(f"**Generated:** {report.generated_at}\n")
            f.write(f"**Total Items:** {report.total_items}\n\n")
            f.write(f"## Summary\n\n{report.summary}\n\n")
            f.write("---\n\n")
            
            for category, results in report.sections.items():
                f.write(f"## {category.title()}\n\n")
                for i, result in enumerate(results, 1):
                    f.write(f"### {i}. {result.title}\n\n")
                    f.write(f"**Source:** {result.source}  \n")
                    if result.published_date:
                        f.write(f"**Date:** {result.published_date}  \n")
                    f.write(f"**URL:** [{result.url}]({result.url})\n\n")
                    f.write(f"{result.content}...\n\n")
                f.write("---\n\n")
        
        print(f"✅ Report saved to: {output_file}")
        return output_file
    
    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results by URL"""
        seen_urls = set()
        unique = []
        for result in results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique.append(result)
        return unique
    
    def _calculate_quality_score(self, result: SearchResult) -> int:
        """
        Calculate content quality score based on keywords
        
        Args:
            result: SearchResult object
            
        Returns:
            Quality score (higher = more relevant to automotive radar)
        """
        text = f"{result.title} {result.content} {result.url}".lower()
        score = 0
        
        # Count positive keywords
        for keyword in POSITIVE_KEYWORDS:
            if keyword.lower() in text:
                score += 1
        
        # Count negative keywords
        for keyword in NEGATIVE_KEYWORDS:
            if keyword.lower() in text:
                score -= 2  # Heavier penalty for negative keywords
        
        return score
    
    def _filter_by_quality(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Filter and sort results by quality score
        
        Args:
            results: List of SearchResult objects
            
        Returns:
            Filtered and sorted list
        """
        # Calculate scores
        for result in results:
            result._quality_score = self._calculate_quality_score(result)
        
        # Filter out low-quality results
        filtered = [r for r in results if r._quality_score >= QUALITY_THRESHOLD]
        
        # Additional filter: remove obvious non-automotive content by title blacklist
        further_filtered = []
        for result in filtered:
            title_lower = result.title.lower()
            # Skip if title matches blacklist
            if any(skip.lower() in title_lower for skip in TITLE_BLACKLIST):
                continue
            further_filtered.append(result)
        
        # Sort by quality score (descending), then by date (recent first)
        further_filtered.sort(key=lambda x: (getattr(x, '_quality_score', 0), -getattr(x, '_age_days', 0)), reverse=True)
        
        return further_filtered
    
    def _parse_date(self, result: SearchResult) -> Optional[datetime]:
        """
        Parse date from search result (multiple strategies)
        
        Args:
            result: SearchResult object
            
        Returns:
            datetime object or None
        """
        # Strategy 1: Use publishedDate from API
        if result.published_date:
            try:
                # Handle various date formats
                date_str = result.published_date[:10]  # Extract YYYY-MM-DD
                return datetime.strptime(date_str, '%Y-%m-%d')
            except:
                pass
        
        # Strategy 2: Extract year from URL
        year_match = re.search(r'(20\d{2})', result.url)
        if year_match:
            year = int(year_match.group(1))
            if year >= MIN_YEAR:
                # Try to extract month/day from URL
                date_match = re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})', result.url)
                if date_match:
                    try:
                        return datetime.strptime(f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}", '%Y-%m-%d')
                    except:
                        pass
                # Fallback to Jan 1 of that year
                return datetime(year, 1, 1)
        
        # Strategy 3: Extract date from content
        content = result.content + result.title
        date_patterns = [
            r'(20\d{2}) 年 (\d{1,2}) 月 (\d{1,2}) 日',  # Chinese format
            r'(\d{4})-(\d{2})-(\d{2})',  # ISO format
            r'(\d{1,2})/(\d{1,2})/(20\d{2})',  # US format
        ]
        for pattern in date_patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    groups = match.groups()
                    if '年' in pattern:  # Chinese format
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                    elif '/' in pattern:  # US format
                        return datetime(int(groups[2]), int(groups[0]), int(groups[1]))
                    else:  # ISO format
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                except:
                    pass
        
        return None
    
    def _filter_by_date(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Filter results by date
        
        Args:
            results: List of SearchResult objects
            
        Returns:
            Filtered list (recent items first)
        """
        now = datetime.now()
        filtered = []
        
        for result in results:
            pub_date = self._parse_date(result)
            
            if pub_date is None:
                # No date found - keep but mark as old
                result._age_days = 9999
                if MIN_YEAR <= 2025:  # If MIN_YEAR is set, still keep undated
                    filtered.append(result)
                continue
            
            age_days = (now - pub_date).days
            result._age_days = age_days  # Store for sorting
            result._parsed_date = pub_date
            
            # Filter out too old content
            if age_days > MAX_AGE_DAYS:
                continue
            
            # Filter out content before MIN_YEAR
            if pub_date.year < MIN_YEAR:
                continue
            
            filtered.append(result)
        
        # Sort by date (recent first)
        filtered.sort(key=lambda x: getattr(x, '_age_days', 9999))
        
        return filtered
    
    def _generate_summary(self, sections: Dict[str, List[SearchResult]], date: str) -> str:
        """Generate report summary"""
        total = sum(len(results) for results in sections.values())
        
        summary = f"This report covers {total} items across {len(sections)} categories for {date}. "
        
        # Highlight top items
        for category, results in sections.items():
            if results:
                summary += f"Key {category} topics include: {results[0].title[:50]}... "
        
        return summary
    
    def _get_cache(self, key: str) -> Optional[List[SearchResult]]:
        """Get cached results"""
        cache_file = os.path.join(CACHE_DIR, f"{key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    return [SearchResult(**item) for item in data]
            except:
                pass
        return None
    
    def _set_cache(self, key: str, results: List[SearchResult]):
        """Cache search results"""
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(CACHE_DIR, f"{key}.json")
        try:
            with open(cache_file, 'w') as f:
                json.dump([asdict(r) for r in results], f)
        except:
            pass


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate millimeter wave radar daily report')
    parser.add_argument('--date', type=str, help='Report date (YYYY-MM-DD), default today')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR, help='Output directory')
    parser.add_argument('--no-cache', action='store_true', help='Disable caching')
    args = parser.parse_args()
    
    # Generate report
    generator = RadarReportGenerator(cache_enabled=not args.no_cache)
    report = generator.generate_report(args.date)
    
    # Save report
    output_file = generator.save_report(report, args.output_dir)
    
    # Print summary
    print(f"\n📊 Report Summary:")
    print(f"  Date: {report.date}")
    print(f"  Total Items: {report.total_items}")
    print(f"  Categories: {len(report.sections)}")
    print(f"  Output: {output_file}")


if __name__ == '__main__':
    main()
