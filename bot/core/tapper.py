import asyncio
from urllib.parse import unquote, quote

import aiohttp
import json
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestWebView
from bot.core.agents import generate_random_user_agent
from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from datetime import datetime, timezone
import pytz
from random import randint


class Tapper:
    def __init__(self, tg_client: Client):
        self.session_name = tg_client.name
        self.tg_client = tg_client

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            with_tg = True

            if not self.tg_client.is_connected:
                with_tg = False
                try:
                    await self.tg_client.connect()
                    await self.tg_client.send_message('DiamoreCryptoBot', '/start 737844465')
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            while True:
                try:
                    peer = await self.tg_client.resolve_peer('DiamoreCryptoBot')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"<light-yellow>{self.session_name}</light-yellow> | FloodWait {fl}")
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Sleep {fls}s")

                    await asyncio.sleep(fls + 3)

            web_view = await self.tg_client.invoke(RequestWebView(
                peer=peer,
                bot=peer,
                platform='android',
                from_bot_menu=False,
                url="https://diamore-app.vercel.app/",
            ))

            auth_url = web_view.url
            tg_web_data = unquote(
                string=unquote(
                    string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0]))

            if with_tg is False:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Unknown error during Authorization: "
                         f"{error}")
            await asyncio.sleep(delay=3)

    async def user(self, http_client: aiohttp.ClientSession):
        try:
            await http_client.post(url='https://diamore-propd.smart-ui.pro/user/visit')
            response = await http_client.get(url='https://diamore-propd.smart-ui.pro/user')
            response.raise_for_status()
            response_text = await response.text()
            app_user_data = json.loads(response_text)
            return app_user_data
        except Exception as error:
            logger.error(f"Auth request error happened: {error}")
            return None

    async def claim_daily(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.post(url='https://diamore-propd.smart-ui.pro/user/claim-daily')
            response_text = await response.text()
            claim_daily = json.loads(response_text)
            return claim_daily
        except Exception as error:
            logger.error(f"Daily claim error happened: {error}")
            return None

    async def get_quests(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(url='https://diamore-propd.smart-ui.pro/quests')
            response_text = await response.text()
            data = json.loads(response_text)
            quests_with_timer = []
            for quest in data:
                if quest.get('checkType') == 'timer':
                    quests_with_timer.append(quest['name'])
            return quests_with_timer

        except Exception as error:
            logger.error(f"Get quests error happened: {error}")
            return None

    async def finish_quests(self, http_client: aiohttp.ClientSession, quest_name: str):
        try:
            response = await http_client.post(url='https://diamore-propd.smart-ui.pro/quests/finish',
                                              json={"questName": f'{quest_name}'})
            response_text = await response.text()
            data = json.loads(response_text)
            if data.get('message') == 'Quest marked as finished':
                return True

        except Exception as error:
            logger.error(f"Finish quests error happened: {error}")
            return None

    async def sync_clicks(self, http_client: aiohttp.ClientSession):
        try:
            await http_client.options(url='https://diamore-propd.smart-ui.pro/user')
            user_response = await http_client.get(url='https://diamore-propd.smart-ui.pro/user')
            user_response.raise_for_status()
            user_json = await user_response.json()
            #tap_bonuses = user_json['tap_bonuses']
            random_clicks = randint(settings.CLICKS[0], settings.CLICKS[1])
            #tap_bonuses += random_clicks
            response = await http_client.post(url='https://diamore-propd.smart-ui.pro/user/syncClicks',
                                              json={"tapBonuses": random_clicks})
            response_text = await response.text()
            data = json.loads(response_text)
            if data.get('message') == 'Bonuses incremented':
                return (True,
                        random_clicks)

        except Exception as error:
            logger.error(f"Sync clicks error happened: {error}")
            return None

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Proxy: {proxy} | Error: {error}")

    async def run(self, proxy: str | None) -> None:
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)

        if proxy:
            await self.check_proxy(http_client=http_client, proxy=proxy)

        tg_web_data = await self.get_tg_web_data(proxy=proxy)

        tg_web_data_parts = tg_web_data.split('&')
        query_id = tg_web_data_parts[0].split('=')[1]
        user_data = tg_web_data_parts[1].split('=')[1]
        auth_date = tg_web_data_parts[2].split('=')[1]
        hash_value = tg_web_data_parts[3].split('=')[1]

        user_data_encoded = quote(user_data)

        init_data = f"query_id={query_id}&user={user_data_encoded}&auth_date={auth_date}&hash={hash_value}"
        http_client.headers["User-Agent"] = generate_random_user_agent(device_type='android', browser_type='chrome')
        http_client.headers['Authorization'] = f'Token {init_data}'

        while True:
            try:
                user = await self.user(http_client=http_client)
                if user is None:
                    continue

                logger.info(f'<light-yellow>{self.session_name}</light-yellow> | Balance - {int(float(user["balance"]))}')

                await asyncio.sleep(1.5)

                if user['dailyBonusAvailable'] != 0:
                    claim_daily = await self.claim_daily(http_client=http_client)
                    if claim_daily.get('message') == 'ok':
                        logger.info(f'<light-yellow>{self.session_name}</light-yellow> | Claimed daily - '
                                    f'{str(user.get("dailyBonusAvailable"))}')
                else:
                    logger.info(f'<light-yellow>{self.session_name}</light-yellow> | Daily bonus not available')

                await asyncio.sleep(1.5)

                if not user['quests']:
                    quests = await self.get_quests(http_client=http_client)
                    for quest_name in quests:
                        status = await self.finish_quests(http_client=http_client, quest_name=quest_name)
                        if status is True:
                            logger.info(f'<light-yellow>{self.session_name}</light-yellow> | Starting doing '
                                        f'{quest_name} quest')
                elif user['quests']:
                    quests = await self.get_quests(http_client=http_client)
                    completed_quests = []
                    new_quests = []
                    for quest in user['quests']:
                        if quest['status'] == 'completed':
                            completed_quests.append(quest['name'])
                    for quest_name in quests:
                        if quest_name not in completed_quests:
                            new_quests.append(quest_name)
                    for quest_name in new_quests:
                        status = await self.finish_quests(http_client=http_client, quest_name=quest_name)
                        if status is True:
                            logger.info(f'<light-yellow>{self.session_name}</light-yellow> | Starting doing '
                                        f'{quest_name} quest')

                await asyncio.sleep(1.5)
                
                next_tap_delay = None
                limit_date_str = user.get("limitDate")
                if limit_date_str or limit_date_str is None:
                    if limit_date_str:
                        limit_date = datetime.fromisoformat(limit_date_str.replace("Z", "+00:00"))
                    else:
                        limit_date = datetime.min.replace(tzinfo=timezone.utc)

                    current_time_utc = datetime.now(pytz.utc)

                    if current_time_utc > limit_date:
                        status, clicks = await self.sync_clicks(http_client=http_client)
                        if status is True:
                            user = await self.user(http_client=http_client)
                            logger.info(f'<light-yellow>{self.session_name}</light-yellow> | Played game, got - '
                                        f'{clicks} diamonds, balance - {int(float(user["balance"]))}')
                    else:
                        logger.info(f'<light-yellow>{self.session_name}</light-yellow> | Game on cooldown')
                        next_tap_delay = limit_date - current_time_utc

                await asyncio.sleep(1.5)
                
                if next_tap_delay is None or next_tap_delay.seconds > 3600:
                    sleep_time = randint(3500, 3600)
                else:
                    sleep_time = next_tap_delay.seconds

                logger.info(f'<light-yellow>{self.session_name}</light-yellow> | sleep {round(sleep_time / 60, 2)} min')
                await asyncio.sleep(sleep_time)
                
            except InvalidSession as error:
                raise error

            except Exception as error:
                logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Unknown error: {error}")
                await asyncio.sleep(delay=3)


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
