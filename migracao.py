from __future__ import print_function
from plone import api
from zope.component.hooks import setSite  # noqa
from DateTime import DateTime  # noqa
from plone.app.textfield.value import RichTextValue
from MySQLdb import connect
from MySQLdb.cursors import DictCursor
import transaction
from bunch import Bunch

# requires MySQL-python
# run this on ipzope shell before using plone.api
# > setSite(portal)  # noqa


def decode(entry, *keys):
    for key in keys:
        entry[key] = entry[key].decode('latin-1')


def query(sql):
    con = connect('localhost', 'root', 'admin', 'rosa',
                  cursorclass=DictCursor)
    with con:
        cur = con.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return [Bunch(r) for r in rows]


def migrate_users(exclude):
    print('Migrating users...')
    rows = query('select id, name, username, email from j25_users')
    rows = [row for row in rows if row.username not in exclude]
    users = {}
    for row in rows:
        decode(row, 'fullname')
        properties = {'fullname': row.fullname}
        user = api.user.create(username=row.username,
                               email=row.email,
                               properties=properties)
        users[row.id] = user
    transaction.commit()
    print('%s users migrated' % len(rows))
    return users


def migrate_folders(portal):
    rows = query('''SELECT id, title from j25_assets
                 where name like 'com_content.category.%'
                 and parent_id = 35''')
    folders = {}
    for row in rows:
        decode(row, 'title')
        print('Creating folder %s' % row.title)
        folder = api.content.create(
            type='Folder', title=row.title, container=portal)
        folders[row.id] = folder
        api.content.transition(obj=folder, transition='publish')
    transaction.commit()
    return folders


def create_article(folder, title, text, date, creator):
    with api.env.adopt_user(username=creator):
        text = RichTextValue(text, 'text/html', 'text/html')
        instance = api.content.create(
            type='Document', title='A', text=text, container=folder)
        # creation date
        instance.creation_date = date
        instance.setModificationDate(date)
        instance.reindexObject(idxs=['created', 'modified'])


def migrate_articles(portal, users, folders):
    rows = query('''
    SELECT c.id, c.title, c.alias, c.introtext description, c.fulltext text,
        c.created creation_date, c.modified modification_date,
        c.created_by user_id, a.parent_id folder_id,
        c.hits
        FROM j25_content c, j25_assets a
        where c.asset_id = a.id
        and c.state <> -2 -- exclude marked for deletion
        ''')
    for row in rows:
        decode(row, 'title')
        print(row.title)
    return rows


def migrate(portal):
    setSite(portal)
    users = migrate_users(exclude=['mliell', 'rosa', 'teste'])

    folders = migrate_folders(portal)
    api.content.rename(folders[27], new_id='artigos-publicados')
    transaction.commit()
    migrate_articles(portal, users, folders)
