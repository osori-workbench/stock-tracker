from __future__ import annotations

import argparse
import os
from datetime import datetime

from stock_tracker.app import Collector, run_mode
from stock_tracker.calendar import KST
from stock_tracker.llm import DEFAULT_CODEX_MODEL, CodexCliReviewGenerator
from stock_tracker.naver import NaverClient
from stock_tracker.slack import SlackWebhookClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Send Korean stock briefings to Slack webhook')
    parser.add_argument('mode', choices=['open', 'noon', 'close'])
    parser.add_argument('--at', help='Override current time in ISO-8601 format')
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    webhook_url = os.environ['SLACK_WEBHOOK_URL']
    now = datetime.fromisoformat(args.at).astimezone(KST) if args.at else datetime.now(tz=KST)
    collector = Collector(client=NaverClient())
    slack = SlackWebhookClient(webhook_url=webhook_url)
    reviewer = CodexCliReviewGenerator(
        codex_bin=os.environ.get('CODEX_BIN'),
        model=os.environ.get('CODEX_MODEL', DEFAULT_CODEX_MODEL),
    )
    sent = run_mode(args.mode, now=now, collector=collector, slack=slack, reviewer=reviewer)
    if not sent:
        print('시장 휴장일이라 브리핑을 보내지 않았습니다.')
