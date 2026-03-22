#!/usr/bin/env python3
"""
Millimeter Wave Radar Daily Report Generator v2.1
Automatically collect global data and generate technical daily reports
Author: pengong101
License: MIT

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
from typing import Dict, List, Optional
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
        
        # Search keywords by category (使用精确匹配 + 排除低质内容)
        self.keywords = {
            'industry': [
                '"毫米波雷达" 2026 -百度知道',
                '"mmWave radar" market 2026 -百度知道',
                '"77GHz radar" automotive -百度知道',
                '"4D imaging radar" mass production -百度知道',
                '"radar sensor" technology -百度知道'
            ],
            'academic': [
                '"mmWave radar" signal processing -百度知道',
                '"MIMO radar" beamforming -百度知道',
                '"radar target detection" algorithm -百度知道',
                '"4D radar" point cloud -百度知道',
                '"radar neural network" -百度知道'
            ],
            'patents': [
                '"毫米波雷达" 专利 -百度知道',
                '"mmWave radar" patent -百度知道',
                '"radar antenna" design patent -百度知道',
                '"radar signal processing" patent -百度知道'
            ],
            'products': [
                '"mmWave radar" module 2026 -百度知道',
                '"77GHz radar" sensor new product -百度知道',
                '"automotive radar" supplier -百度知道',
                '"radar chip" manufacturer -百度知道'
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
                search_results = self.search(keyword, engines=SEARCH_ENGINES, max_results=5, time_range=SEARCH_TIME_RANGE)
                results.extend(search_results)
                time.sleep(0.5)  # Rate limiting
            
            # Remove duplicates
            unique_results = self._deduplicate(results)
            sections[category] = unique_results[:10]  # Top 10 per category
            total_items += len(sections[category])
        
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
