"""Read-only checks. No credentials or raw responses are printed."""
import sys
from weread2notionpro.weread_api import WeReadApi
from weread2notionpro.notion_helper import NotionHelper


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'book'
    api = WeReadApi()
    notion = NotionHelper()
    for database_id in set(notion.database_id_dict.values()):
        notion.client.databases.retrieve(database_id=database_id)
    print('Existing Notion databases and data sources readable; no schema changes made.')
    if mode == 'daily':
        api.get_api_data()
        print('Daily reading statistics available.')
    else:
        shelf = api.get_bookshelf()
        books = shelf.get('books', [])
        if not books:
            raise RuntimeError('书架没有可用于验证明细的书籍；未完成验收')
        api.get_read_info(books[0]['bookId'])
        api.get_notebooklist()
        print('Book reading detail and notebook APIs available.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not expose SDK response bodies, request headers, or credentials.
        print('Preflight failed:', type(error).__name__)
        if isinstance(error, RuntimeError):
            print(str(error))
        raise SystemExit(1)
