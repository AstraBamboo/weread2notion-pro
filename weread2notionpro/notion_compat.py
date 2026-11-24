"""Adapt legacy callers to data sources without changing database schemas."""
from notion_client import Client


class DatabaseAdapter:
    def __init__(self, client):
        self.client = client
        self.cache = {}

    def resolve(self, database_id):
        if database_id not in self.cache:
            database = self.client.databases.retrieve(database_id=database_id)
            sources = database.get('data_sources', [])
            if len(sources) != 1:
                raise RuntimeError('数据库必须唯一对应一个数据源；拒绝猜测写入目标。')
            self.cache[database_id] = sources[0]['id']
        return self.cache[database_id]

    def query(self, database_id, **kwargs):
        return self.client.data_sources.query(data_source_id=self.resolve(database_id), **kwargs)

    def retrieve(self, database_id):
        return self.client.data_sources.retrieve(data_source_id=self.resolve(database_id))


class PageAdapter:
    def __init__(self, client, databases):
        self.client, self.databases = client, databases

    def create(self, parent, **kwargs):
        if 'database_id' in parent:
            parent = {'type': 'data_source_id', 'data_source_id': self.databases.resolve(parent['database_id'])}
        result = self.client.pages.create(parent=parent, **kwargs)
        self.verify(result['id'], kwargs.get('properties', {}))
        return result

    def update(self, page_id, **kwargs):
        if kwargs.get('archived') or kwargs.get('in_trash'):
            raise RuntimeError('禁止归档已有内容')
        result = self.client.pages.update(page_id=page_id, **kwargs)
        self.verify(page_id, kwargs.get('properties', {}))
        return result

    def verify(self, page_id, properties):
        if '时长' not in properties:
            return
        expected = properties['时长']['number']
        actual = self.client.pages.retrieve(page_id=page_id)['properties']['时长']['number']
        if actual != expected:
            raise RuntimeError('Notion 时长写入回读不一致')
        print('Notion duration write verified')


class CompatibleClient:
    def __init__(self, **kwargs):
        client = Client(notion_version='2025-09-03', **kwargs)
        self.databases = DatabaseAdapter(client)
        self.pages = PageAdapter(client, self.databases)
        self.blocks = client.blocks
