#!/usr/bin/env python3

import os
import re
import sys
import yaml
import argparse
import dateutil
import feedparser

from bs4 import BeautifulSoup
from mastodon import Mastodon
from datetime import datetime, timezone, MINYEAR

print(f"Current directory: {os.getcwd()}")

# DEFAULT_CONFIG_FILE = os.path.join("~", "apps", "workspace", "config_file")
DEFAULT_CONFIG_FILE = "config_file"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help=("perform a trial run with no changes made: "
                              "don't toot, don't save config"))
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="be verbose")
    parser.add_argument("-c", "--config",
                        help="config file to use",
                        default=os.path.expanduser(DEFAULT_CONFIG_FILE))

    args = parser.parse_args()
    config_file = args.config

    if args.verbose:
        print("using config file", config_file)

    config = read_config(config_file)

    masto = Mastodon(
        api_base_url=os.environ['URL'],
        client_id=os.environ['client_key'],
        client_secret=os.environ['client_secret'],
        access_token=os.environ['access_token']
    )

    newest_post = config['updated']
    for feed in config['feeds']:
        if args.verbose:
            print(f"fetching {feed['url']} entries since {config['updated']}")
        for entry in get_feed(feed['url'], config['updated']):
            newest_post = max(newest_post, entry['updated'])
            if args.verbose:
                print(entry)
            if args.dry_run:
                print("trial run, not tooting ", entry["title"][:50])
                continue
            masto.status_post(feed['template'].format(**entry)[:499])

    if not args.dry_run:
        config['updated'] = newest_post.isoformat()
        save_config(config, config_file)

def get_feed(feed_url, last_update):
    feed = feedparser.parse(feed_url)
    if last_update:
        entries = [e for e in feed.entries
                   if dateutil.parser.parse(e['updated']) > last_update]
    else:
        entries = feed.entries
    entries.sort(key=lambda e: e.updated_parsed)
    for entry in entries:
        yield get_entry(entry)

def get_entry(entry):
    hashtags = []
    for tag in entry.get('tags', []):
        t = tag['term'].replace(' ', '_').replace('.', '').replace('-', '')
        hashtags.append('#{}'.format(t))
    summary = entry.get('summary', '')
    content = entry.get('content', '') or ''
    if content:
        content = cleanup(content[0].get('value', ''))
    url = entry.id
    return {
        'url': url,
        'link': entry.link,
        'title': cleanup(entry.title),
        'summary': cleanup(summary),
        'content': content,
        'hashtags': ' '.join(hashtags),
        'updated': dateutil.parser.parse(entry['updated'])
    }

def cleanup(text):
    html = BeautifulSoup(text, 'html.parser')
    text = html.get_text()
    text = re.sub('\xa0+', ' ', text)
    text = re.sub('  +', ' ', text)
    text = re.sub(' +\n', '\n', text)
    text = re.sub('\n\n\n+', '\n\n', text, flags=re.M)
    return text.strip()

def find_urls(html):
    if not html:
        return
    urls = []
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all(["a", "img"]):
        if tag.name == "a":
            url = tag.get("href")
        elif tag.name == "img":
            url = tag.get("src")
        if url and url not in urls:
            urls.append(url)
    return urls

def save_config(config, config_file):
    copy = dict(config)
    with open(config_file, 'w') as fh:
        fh.write(yaml.dump(copy, default_flow_style=False))

def read_config(config_file):
    config = {
        'updated': datetime(MINYEAR, 1, 1, 0, 0, 0, 0, timezone.utc)
    }
    with open(config_file) as fh:
        cfg = yaml.load(fh, yaml.SafeLoader)
        if 'updated' in cfg:
            cfg['updated'] = dateutil.parser.parse(cfg['updated'])
    config.update(cfg)
    return config

if __name__ == "__main__":
    main()
