import os, json, datetime, glob
from workflow.gpt.summary import request_gpt
import workflow.article.rss as rss
import workflow.article.blog as blog


def execute(rss_resource="workflow/resources"):
    # 缓存判断
    cache_folder, cache_file = find_valid_file()
    rss_list = parse_daily_rss_article(rss_resource, cache_file)
    if cache_folder:
        save_article(rss_list, cache_folder)
    articles = find_favorite_article(rss_list)
    blog.make_daily_markdown_with(articles, rss_list)


def parse_daily_rss_article(rss_resource, cache_file=None):
    """获取rss信息"""
    if cache_file:
        return decode_article(cache_file)
    rss_items = rss.load_rss_configs(rss_resource)

    daily_rss = []
    for item in rss_items:
        rss_list = rss.parse_rss_item(item)
        for rss_item in rss_list:
            daily_rss.append(rss_item)
            print(f"date: {rss_item.date}, link: {rss_item.link}")
    return daily_rss


def find_favorite_article(rss_articles):
    """获取评分最高的文章"""
    evaluate_list = []
    # 因gemini限流，文章最多分析20篇
    max_analyze_nums = 20
    rss_articles = rss_articles[:max_analyze_nums]
    # 默认输出结果10
    max_article_nums = int(os.environ.get("MAX_ARTICLE_NUMS", "12"))

    # 一个rss源对应一个总结，多条内容，合并处理
    # {"resource_type": "", "items": []}
    rss_resource = {}
    for article in rss_articles:
        if not article.summary:
            continue
        if article.info["title"] in rss_resource.keys():
            rss_resource[article.info["title"]].append(article.summary)
        else:
            rss_resource[article.info["title"]] = [article]

    for item in rss_resource:
        evaluate = evaluate_article(item)
        if not evaluate:
            continue
        article.evaluate = evaluate
        evaluate_list.append(article)

    evaluate_list.sort(key=lambda x: x.evaluate["score"], reverse=True)
    evaluate_list = evaluate_list[:max_article_nums]
    return evaluate_list


def evaluate_article(content):
    text = request_gpt(content)
    if not text:
        return None
    # 去掉首尾两行就是完整json内容
    text = text.removeprefix("```json")
    text = text.removesuffix("```")
    # 有时输出格式可能不完全符合json
    try:
        json_obj = json.loads(text)
        # 关键信息校验
        if json_obj.get("score"):
            return json_obj
        return None
    except:
        return None


def find_valid_file():
    """是否为有效rss缓存"""
    if os.environ.get("RSS_CACHE_ENABLE") != "true":
        return None, None

    current_directory = os.path.dirname(os.path.abspath(__file__))

    cache_folder = f"{current_directory}/draft"
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    cache_files = glob.glob(f"{cache_folder}/*{today_str}.json")
    cache_file = cache_files[-1] if cache_files else None
    return cache_folder, cache_file


def save_article(articles, draft_folder):
    """存储解析的文章"""
    data = []
    path = f"{draft_folder}/article_cache_{datetime.date.today().strftime('%Y-%m-%d')}.json"
    for article in articles:
        data.append(article.__dict__)

    with open(path, "w") as fp:
        fp.write(json.dumps(data, indent=4))


def decode_article(path):
    """根据文件解析"""
    rss_list = []
    with open(path, "r") as fp:
        object_list = json.loads(fp.read())
        for item in object_list:
            rss_item = rss.RSS()
            for key, value in item.items():
                setattr(rss_item, key, value)
            rss_list.append(rss_item)
    return rss_list
