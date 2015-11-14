from __future__ import print_function
from plone import api
from zope.component.hooks import setSite  # noqa
from DateTime import DateTime  # noqa
from plone.app.textfield.value import RichTextValue
import MySQLdb as mdb
import transaction

# requires MySQL-python
# run this on ipzope shell before using plone.api
# > setSite(portal)  # noqa


def query(sql):
    con = mdb.connect('localhost', 'root', 'admin', 'rosa',
                      cursorclass=mdb.cursors.DictCursor)
    with con:
        cur = con.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return rows


def migrate_users(exclude):
    print('Migrating users...')
    rows = query('select id, name, username, email from j25_users')
    rows = [row for row in rows if row['username'] not in exclude]
    users = {}
    for row in rows:
        properties = {'fullname': row['fullname'].decode('latin-1')}
        user = api.user.create(username=row['username'],
                               email=row['email'],
                               properties=properties)
        users[row['id']] = user
    transaction.commit()
    print('%s users migrated' % len(rows))
    return users


def migrate_folders(portal):
    rows = query('''SELECT id, title from j25_assets
                 where name like 'com_content.category.%'
                 and parent_id = 35''')
    folders = {}
    for row in rows:
        title = row['title'].decode('latin-1')
        print('Creating folder %s' % title)
        folder = api.content.create(
            type='Folder', title=row['title'], container=portal)
        folders[row['id']] = folder
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
    pass


def migrate(portal):
    setSite(portal)
    users = migrate_users(exclude=['mliell', 'rosa', 'teste'])

    folders = migrate_folders(portal)
    api.content.rename(folders[27], new_id='artigos-publicados')
    transaction.commit()
    migrate_articles(portal, users, folders)
