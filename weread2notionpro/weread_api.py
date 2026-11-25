import hashlib
import os
import re
import requests
import pendulum
from dotenv import load_dotenv

load_dotenv()
GATEWAY = "https://i.weread.qq.com/api/agent/gateway"


class WeReadApi:
    def __init__(self):
        key = (os.getenv("WEREAD_API_KEY") or "").strip()
        if not key:
            candidate = (os.getenv("WEREAD_COOKIE") or "").strip()
            if candidate.startswith("wrk-"):
                key = candidate
        if not key:
            raise RuntimeError("缺少 WEREAD_API_KEY；请在 GitHub Secrets 配置，不要写入代码或日志。")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": "Bearer " + key})

    def request(self, api_name, **params):
        try:
            response = self.session.post(GATEWAY, json={
                "api_name": api_name, "skill_version": "1.0.6", **params}, timeout=30)
        except requests.RequestException:
            raise RuntimeError("微信读书网络请求失败") from None
        if not response.ok:
            raise RuntimeError(f"微信读书 HTTP {response.status_code}: {api_name}")
        try:
            data = response.json()
        except ValueError:
            raise RuntimeError("微信读书返回非 JSON 响应") from None
        if data.get("errcode", 0):
            raise RuntimeError(f"微信读书接口失败: {api_name}, errcode={data.get('errcode')}")
        if data.get("upgrade_info"):
            print("微信读书接口提示可升级；本次使用已声明的 1.0.6 协议。")
        return data

    def get_bookshelf(self):
        return self.request("/shelf/sync")

    def get_notebooklist(self):
        books, cursor = [], None
        while True:
            params = {"count": 100}
            if cursor is not None:
                params["lastSort"] = cursor
            data = self.request("/user/notebooks", **params)
            batch = data.get("books", [])
            books.extend(batch)
            if not data.get("hasMore"):
                return sorted(books, key=lambda x: x.get("sort", 0))
            next_cursor = batch[-1].get("sort") if batch else None
            if next_cursor is None or next_cursor == cursor:
                raise RuntimeError("微信读书笔记分页停滞；未将不完整结果标为成功")
            cursor = next_cursor

    def get_bookinfo(self, bookId):
        return self.request("/book/info", bookId=bookId)

    def get_bookmark_list(self, bookId):
        data = self.request("/book/bookmarklist", bookId=bookId)
        if "updated" not in data:
            raise RuntimeError("微信读书划线响应缺少 updated")
        return data["updated"]

    def get_review_list(self, bookId):
        reviews, cursor = [], 0
        while True:
            data = self.request("/review/list/mine", bookid=bookId, synckey=cursor, count=100)
            for item in data.get("reviews", []):
                review = item["review"]
                if review.get("type") == 4:
                    review = {**review, "chapterUid": 1000000}
                reviews.append(review)
            if not data.get("hasMore"):
                return reviews
            next_cursor = data.get("synckey")
            if next_cursor is None or next_cursor == cursor:
                raise RuntimeError("微信读书想法分页停滞")
            cursor = next_cursor

    def get_chapter_info(self, bookId):
        data = self.request("/book/chapterinfo", bookId=bookId)
        if "chapters" not in data:
            raise RuntimeError("微信读书章节响应缺少 chapters")
        chapters = {x["chapterUid"]: x for x in data["chapters"]}
        chapters[1000000] = {"chapterUid": 1000000, "chapterIdx": 1000000,
                             "title": "点评", "level": 1}
        return chapters

    def get_read_info(self, bookId):
        # The public gateway documents cumulative progress, not per-book daily
        # records. Use the original endpoint only for this missing capability.
        cookie = (os.getenv("WEREAD_COOKIE") or "").strip()
        if not cookie or cookie.startswith("wrk-"):
            raise RuntimeError("逐书逐日阅读明细尚无已验证的新接口；需要有效旧 Cookie，拒绝伪造阅读记录。")
        try:
            response = requests.get("https://i.weread.qq.com/book/readinfo",
                headers={"Cookie": cookie}, params={"bookId": bookId,
                "readingDetail": 1, "finishedDate": 1}, timeout=30)
            data = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError("旧阅读明细接口不可用；尚未恢复阅读记录同步") from None
        if not response.ok or data.get("errcode", 0) or "readDetail" not in data:
            raise RuntimeError("旧阅读明细接口未返回有效明细；尚未恢复阅读记录同步")
        return data

    def get_api_data(self):
        # Annual readTimes are MONTH buckets; only dailyReadTimes are day rows.
        year = int(os.getenv("YEAR") or pendulum.now("Asia/Shanghai").year)
        start = pendulum.datetime(year, 1, 1, tz="Asia/Shanghai")
        data = self.request("/readdata/detail", mode="annually", baseTime=start.int_timestamp)
        daily = data.get("dailyReadTimes")
        if not isinstance(daily, dict):
            daily = {}
            now = pendulum.now("Asia/Shanghai")
            for month in range(1, 13):
                date = start.replace(month=month)
                if date > now:
                    break
                detail = self.request("/readdata/detail", mode="monthly", baseTime=date.int_timestamp)
                buckets = detail.get("readTimes")
                if not isinstance(buckets, dict):
                    raise RuntimeError("每日阅读统计缺失；拒绝把汇总值写成日记录")
                daily.update(buckets)
        for key in daily:
            date = pendulum.from_timestamp(int(key), tz="Asia/Shanghai")
            if date.year != year or date != date.start_of("day"):
                raise RuntimeError("阅读统计时间桶不是目标年度的日零点")
        return {"readTimes": daily}

    def transform_id(self, book_id):
        id_length = len(book_id)
        if re.match("^\\d*$", book_id):
            ary = []
            for i in range(0, id_length, 9):
                ary.append(format(int(book_id[i : min(i + 9, id_length)]), "x"))
            return "3", ary

        result = ""
        for i in range(id_length):
            result += format(ord(book_id[i]), "x")
        return "4", [result]

    def calculate_book_str_id(self, book_id):
        md5 = hashlib.md5()
        md5.update(book_id.encode("utf-8"))
        digest = md5.hexdigest()
        result = digest[0:3]
        code, transformed_ids = self.transform_id(book_id)
        result += code + "2" + digest[-2:]

        for i in range(len(transformed_ids)):
            hex_length_str = format(len(transformed_ids[i]), "x")
            if len(hex_length_str) == 1:
                hex_length_str = "0" + hex_length_str

            result += hex_length_str + transformed_ids[i]

            if i < len(transformed_ids) - 1:
                result += "g"

        if len(result) < 20:
            result += digest[0 : 20 - len(result)]

        md5 = hashlib.md5()
        md5.update(result.encode("utf-8"))
        result += md5.hexdigest()[0:3]
        return result

    def get_url(self, book_id):
        return f"https://weread.qq.com/web/reader/{self.calculate_book_str_id(book_id)}"
