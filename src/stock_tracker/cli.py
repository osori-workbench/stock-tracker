from __future__ import annotations

import argparse
import os
from datetime import datetime

from stock_tracker.app import Collector, run_mode
from stock_tracker.calendar import KST
from stock_tracker.llm import DEFAULT_HERMES_MODEL, HermesCliReviewGenerator
from stock_tracker.naver import NaverClient
from stock_tracker.slack import SlackWebhookClient


VALID_MODES = ["morning", "open", "noon", "close"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Send Korean stock briefings to Slack webhook')
    parser.add_argument('mode', choices=VALID_MODES)
    parser.add_argument('--at', help='Override current time in ISO-8601 format')
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    webhook_url = os.environ['SLACK_WEBHOOK_URL']
    now = datetime.fromisoformat(args.at).astimezone(KST) if args.at else datetime.now(tz=KST)
    collector = Collector(client=NaverClient())
    slack = SlackWebhookClient(webhook_url=webhook_url)
    reviewer = HermesCliReviewGenerator(
        hermes_bin=os.environ.get('HERMES_BIN'),
        model=os.environ.get('HERMES_REVIEW_MODEL', DEFAULT_HERMES_MODEL),
    )
    sent = run_mode(args.mode, now=now, collector=collector, slack=slack, reviewer=reviewer)
    if not sent:
        print('시장 휴장일이라 브리핑을 보내지 않았습니다.')
