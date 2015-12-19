from __future__ import print_function
from plone import api
from zope.component.hooks import setSite  # noqa
from DateTime import DateTime  # noqa
from plone.app.textfield.value import RichTextValue
from MySQLdb import connect
from MySQLdb.cursors import DictCursor
import transaction
from bunch import Bunch
from datetime import datetime
import lxml.html
import lxml.html.clean
from os.path import relpath
from plone.namedfile.file import NamedBlobImage
import imghdr
import os.path
from bs4 import BeautifulSoup
import requests
from requests.exceptions import ConnectionError
import urllib

# requires MySQL-python
# run this on ipzope shell before using plone.api
# > setSite(portal)  # noqa


def convert_types(row):
    for key, value in row.iteritems():
        if type(value) == str:
            row[key] = value.decode('latin-1')
        elif type(value) == datetime:
            row[key] = DateTime(value)
    return row


def query(sql):
    con = connect(host='localhost', user='root', db='rosa',
                  cursorclass=DictCursor)
    with con:
        cur = con.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return [Bunch(convert_types(r)) for r in rows]


def migrate_users(exclude=[]):
    print('Migrating users...')
    rows = query('select id, name, username, email from j25_users')
    rows = [row for row in rows if row.username not in exclude]
    users = {}
    for row in rows:
        properties = {'fullname': row.name}
        user = api.user.create(username=str(row.username),
                               email=str(row.email),
                               properties=properties)
        api.user.grant_roles(user=user,
                             roles=['Contributor', 'Editor', 'Reviewer'],)
        users[row.id] = user
    transaction.commit()
    print('%s users migrated' % len(rows))
    return users


def migrate_folders(portal):
    rows = query('''SELECT id, title from j25_assets
                 where name like 'com_content.category.%'
                 and parent_id = 35''')
    rows.append(Bunch(id=1, title='Perdidos'))  # for articles in root
    folders = {}
    for row in rows:
        print('Creating folder %s' % row.title)
        folder = api.content.create(
            type='Folder', title=row.title, container=portal)
        folders[row.id] = folder
        api.content.transition(folder, transition='publish')
    transaction.commit()
    # consider "Root Asset" and "Site" to be root
    folders[35] = folders[1]
    return folders


# patch lxml html cleaner to preserve img src data
import lxml.html.clean
lxml.html.clean._is_javascript_scheme = re.compile(
    r'(?:javascript|jscript|livescript|vbscript|about|mocha):',
    re.I).search

def clean_html(text):
    html = lxml.html.clean.clean_html(text)
    if html.startswith('<div>') and html.endswith('</div>'):
        html = html[len('<div>'):-len('</div>')]
    return html


def create_article(row):
    with api.env.adopt_user(user=row.user):
        obj = api.content.create(
            type='Document',
            container=row.folder,
            title=row.title,
            description=row.description,
            text=RichTextValue(clean_html(row.text),
                               'text/html', 'text/html'),
            hits=row.hits,
        )
        # adjust dates
        obj.creation_date = row.creation_date
        obj.setModificationDate(row.modification_date)
        obj.reindexObject(idxs=['created', 'modified'])

        # move to original url and back
        # this leaves a redirect to the original url as a side effect
        # id = obj.id
        api.content.rename(obj, new_id='%d-%s' % (row.id, str(row.alias)))
        # api.content.rename(obj, new_id=id)

        # workflow state
        if row.state == 1:
            api.content.transition(obj, transition='publish')


def migrate_articles(portal, users, folders):
    rows = query('''
    SELECT c.id, c.title, c.alias, c.introtext description, c.fulltext text,
        c.created creation_date, c.modified modification_date, c.state,
        c.created_by user_id, a.parent_id folder_id,
        c.hits
        FROM j25_content c, j25_assets a
        where c.asset_id = a.id
        and c.state <> -2 -- exclude marked for deletion
        ''')
    for count, row in enumerate(rows):
        # move description to empty text
        if row.description and not row.text:
            row.text, row.description = row.description, ''
        # description should be pure text
        if row.description:
            html_desc = lxml.html.document_fromstring(row.description)
            row.description = unicode(html_desc.text_content())
        row.user = users[row.user_id]
        row.folder = folders[row.folder_id]
        print('Creating article [%s, %s] %s' % (
            row.id, row.alias, row.title))
        create_article(row)
        # commit every 10 items
        if not count % 10:
            transaction.commit()
    transaction.commit()
    return rows


def clean():
    for user in api.user.get_users():
        api.user.delete(user=user)
    for portal_type in ['Document', 'Folder']:
        for brain in api.content.find(portal_type=portal_type):
            api.content.delete(obj=brain.getObject(),
                               check_linkintegrity=False)
    transaction.commit()


def migrate(portal):
    setSite(portal)
    clean()
    users = migrate_users(['rosa'])
    folders = migrate_folders(portal)
    api.content.rename(folders[27], new_id='artigos-publicados')
    transaction.commit()
    articles = migrate_articles(portal, users, folders)
    transaction.commit()
    return users, folders, articles


def create_file(dir, filename, container):
    if filename in ['index.html', '.listing']:
        return
    path = os.path.join(dir, filename)
    with open(path, 'r') as f:
        data = f.read()
    if imghdr.what(path):
        # it's an image
        print('Creating image %s' % path)
        file = api.content.create(
            type='Image',
            # id=filename,
            title=filename,
            container=container,
            image=NamedBlobImage(data=data,
                                 filename=filename.decode('utf-8')))
        return file
    else:
        print('NOT AN IMAGE: %s' % path)


def migrate_files(portal, root):
    folder_name = os.path.basename(root)
    if folder_name not in portal:
        api.content.create(type='Folder', title=folder_name, container=portal)
    base_folder = portal[folder_name]

    ids = {}
    for dir, subdirs, filenames in os.walk(root):
        path = relpath(dir, root)
        # translate to normalized plone path
        for name, id in ids.items():
            path = path.replace(name, id)
        if path == '.':
            container = base_folder
        else:
            container = base_folder.unrestrictedTraverse(path)
        for sub in subdirs:
            print('Creating folder %s : %s' % (container, sub))
            folder = api.content.create(type='Folder', title=sub, container=container)
            ids[sub] = folder.id
        for filename in filenames:
            create_file(dir, filename, container)
    transaction.commit()


FTP_DIR = '/home/mazza/seva/rosa/ftp/public_html'


def extract_first_image_as_lead_image(page):
    # assumes page has lead image behaviour
    if getattr(page, 'image', None):
        return
    soup = BeautifulSoup(page.text.raw, 'lxml')
    if soup.img:
        soup.html.unwrap()
        soup.body.unwrap()
        img = soup.img.extract()

        # set text without the extracted first image
        page.text = RichTextValue(soup.text, 'text/html', 'text/html')

        # set image, if we can find it
        src = img.attrs['src']
        print('Extracting lead image for %s (from %s)' % (page, src))
        if src.startswith('images/'):
            path = os.path.join(FTP_DIR, urllib.unquote(src))
            if not os.path.exists(path):
                print('@@@@@@@@@@@@@@@@@@@ NAO ACHADA: %s' % path)
                data = None
            else:
                if not imghdr.what(path):
                    print('@@@@@@@@@@@@@@@@@@@ NAO PARECE SER IMAGEM %s' % path)
                with open(path, 'r') as f:
                    data = f.read()
        elif not src.strip():
            import ipdb; ipdb.set_trace()
            # simply remove empty img
            data = None
        else:
            try:
                res = requests.get(src, stream=True)
                data = res.raw.read()
            except ConnectionError:
                print('########  ConnectionError: %s' % src)
                transaction.abort()
                return
        if data:
            page.image = NamedBlobImage(data=data)
        transaction.commit()
