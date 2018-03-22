import os
import json
import pickle
import urllib
import requests
from multiprocessing import Pool
from pprint import pprint

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import conf


def cache_image(f):
    if not f[0]:
        return f[1]

    if not os.path.isfile(f[1]):
        urllib.request.urlretrieve(*f)
        os.system('convert {} -resize 480x360 {}'.format(f[1], f[1]))
    return f[1]


class KeyboardButton(QPushButton):
    def __init__(self, value):
        super().__init__(value)
        self.val = value
        self.clicked.connect(self._click)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Down, Qt.Key_Up, Qt.Key_Left, Qt.Key_Right):
            self.parent().keyPressEvent(event, self)
        elif event.key() == Qt.Key_Return:
            self.click_handler(self)
        else:
            super().keyPressEvent(event)

    def click_handler(self, btn):
        raise NotImplementedError

    def _click(self, i):
        self.click_handler(self)


class Keyboard(QWidget):
    position = [0, 0]

    ru_keys = (
        ('А', 'Б', 'В', 'Г', 'Д', 'Е', 'Ж', 'З', '<x'),
        ('И', 'Й', 'К', 'Л', 'М', 'Н', 'О', 'П', 'Clear'),
        ('Р', 'С', 'Т', 'У', 'Ф', 'Х', 'Ц', 'Ч', '123'),
        ('Ш', 'Щ', 'Ъ', 'Ы', 'Ь', 'Э', 'Ю', 'Я', 'En'),
        ('space', 'Enter'),
    )

    en_keys = (
        ('A', 'B', 'C', 'D', 'E', 'F', 'G', '<x'),
        ('H', 'I', 'J', 'K', 'L', 'M', 'N', 'Clear'),
        ('O', 'P', 'Q', 'R', 'S', 'T', 'U', '123'),
        ('V', 'W', 'X', 'Y', 'Z', '-', "'", 'Ru'),
        ('space', 'Enter'),
    )

    digital_keys = (
        ('1', '2', '3', '&', '#', '(', ')', '<x'),
        ('4', '5', '6', '@', '!', '?', ':', 'Clear'),
        ('7', '8', '9', '0', '.', '_', '"', 'Ru'),
        ('space', 'Enter'),
    )

    def __init__(self, parent=None, input_field=None):
        super().__init__(parent)
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.input_field = input_field

    def keyPressEvent(self, event, button=None):
        row_count = self.layout.rowCount()
        cols_count = self.layout.columnCount()
        pos = self.layout.getItemPosition(self.layout.indexOf(button))
        if event.key() == Qt.Key_Down:
            if pos[0] < row_count - 1:
                item = self.layout.itemAtPosition(pos[0]+1, pos[1])
                if item:
                    item.widget().setFocus()
                    self.position[0] = pos[0]+1
                else:
                    self.layout.itemAtPosition(pos[0]+1, 1).widget().setFocus()
                    self.position = [pos[0]+1, 1]
            else:
                self.parent().keyPressEvent(event, self)
        elif event.key() == Qt.Key_Up and pos[0]:
            self.layout.itemAtPosition(pos[0]-1, pos[1]).widget().setFocus()
            self.position[0] = pos[0]-1
        elif event.key() == Qt.Key_Left:
            if pos[1]:
                self.layout.itemAtPosition(pos[0], pos[1]-1).widget().setFocus()
                self.position[1] = pos[1]-1
            else:
                self.parent().keyPressEvent(event, self)
        elif event.key() == Qt.Key_Right:
            if pos[1] < cols_count - 1:
                self.layout.itemAtPosition(pos[0], pos[1]+1).widget().setFocus()
                self.position[1] = pos[1]+1
            else:
                self.parent().keyPressEvent(event, self)

    def setFocus(self):
        super().setFocus()
        self.layout.itemAtPosition(*self.position).widget().setFocus()

    def show(self, ktype):
        while self.layout.count():
            c = self.layout.takeAt(0)
            c.widget().deleteLater()

        for ri, row in enumerate(getattr(self, '{}_keys'.format(ktype), [])):
            for ci, col in enumerate(row):
                btn = KeyboardButton(col)
                btn.click_handler = self.handle_button
                self.layout.addWidget(btn, ri, ci)

    def handle_button(self, btn):
        val = btn.val.lower()
        if len(val) == 1 or val == 'space':
            self.input_field.insert(val == 'space' and ' ' or val)
        elif val in ('en', 'ru', '123'):
            self.show(val == '123' and 'digital' or val)
        elif val == '<x':
            self.input_field.backspace()
        elif val == 'clear':
            self.input_field.clear()
        elif val == 'enter':
            self.input_field.submit()


class KeyboardTips(QListWidget):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.parent().keyPressEvent(event, self)
        else:
            super().keyPressEvent(event)


class YouTubeView(QWidget):
    api = requests.session()
    current_focus = 0
    results = []
    rendered = False
    recs = []
    rec_next = None
    rec_continuation = None
    rec_end = False
    api_data = {
        "context": {
            "client": {
                "clientName": "TVHTML5",
                "clientVersion": "5.20160729",
                "screenWidthPoints": 1920,
                "screenHeightPoints": 1080,
                "screenPixelDensity": 1,
                "theme": "CLASSIC",
                "webpSupport": False,
                "animatedWebpSupport": False,
                "acceptRegion": "RU",
                "acceptLanguage": "ru",
                "tvAppInfo": {
                    "appQuality": "TV_APP_QUALITY_FULL_ANIMATION"
                }
            },
            "request": {},
            "user": {
                "enableSafetyMode": False
            }
        },
        "browseId": "default"
    }
    search_tips_data = {
        "client": "youtube-lr",
        "ds": "yt",
        "hl": "ru_RU",
        "xhr": "t",
        "oe": "utf-8",
        "q": ""
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        if os.path.isfile('cache/cookies'):
            with open('cache/cookies', 'rb') as f:
                self.api.cookies = requests.utils.cookiejar_from_dict(pickle.load(f))

        #self.parent = parent
        self.search = QLineEdit()
        self.search.keyPressEvent = self.search_activated
        self.search.submit = self.do_search
        self.search.textChanged.connect(self.tips_update)

        self.results = QListWidget(flow=QListView.LeftToRight)
        self.results.setViewMode(QListView.IconMode)
        self.results.setWrapping(False)
        self.results.setWordWrap(True)
        self.results.setIconSize(QSize(360, 480))
        self.results.itemActivated.connect(self.activate_item)

        self.layout = QVBoxLayout()
        #self.layout.setLabelAlignment(Qt.AlignHorizontal_Mask)

        self.search_layout = QHBoxLayout()
        self.search_layout.addWidget(QLabel('Search'))
        self.search_layout.addWidget(self.search)
        self.layout.addLayout(self.search_layout)

        self.keyboard_layout = QHBoxLayout()
        self.keyboard = Keyboard(input_field=self.search)
        self.keyboard_tips = KeyboardTips()
        self.keyboard_tips.itemActivated.connect(self.set_search_from_tip)
        self.keyboard_layout.addWidget(self.keyboard_tips)
        self.keyboard_layout.addWidget(self.keyboard)

        self.results_layout = QVBoxLayout()
        self.results_layout.addWidget(QLabel('Results'))
        self.results_layout.addWidget(self.results)

    def render(self):
        print('RENDER')
        self.setLayout(self.layout)
        self.recomendations()
        self.rendered = True

    def get(self, *args, **kwargs):
        kwargs['headers'] = {'Content-Type': 'application/json'}
        res = self.api.get(*args, **kwargs)
        with open('cache/cookies', 'wb+') as f:
            pickle.dump(requests.utils.dict_from_cookiejar(self.api.cookies), f)
        return res

    def post(self, *args, **kwargs):
        kwargs['headers'] = {'Content-Type': 'application/json'}
        res = self.api.post(*args, **kwargs)
        with open('cache/cookies', 'wb+') as f:
            pickle.dump(requests.utils.dict_from_cookiejar(self.api.cookies), f)
        return res

    #def show(self):
    #    self.setLayout(self.layout)

    def setFocus(self):
        super().setFocus()
        self.current_focus = 0
        w = self.layout.itemAt(self.current_focus).itemAt(1).widget()
        w.setFocus()
        self.window().container.ensureWidgetVisible(w, 0, 0)
        _si = lambda: True
        not getattr(w, 'selectedItems', _si)() and w.item(0) and w.item(0).setSelected(True)
        #print(self.layout.takeAt(self.current_focus))
       # print(w)
       # w.setFocus()
        #w.setCurrentRow(1)

    def keyPressEvent(self, event, elem=None):
        print(event.key())
        w = None
        _si = lambda: True
        if event.key() == Qt.Key_Down:
            if self.current_focus >= self.layout.count() - 1 and not self.rec_end:
                self.recomendations()
            w = self.layout.itemAt(self.current_focus+1).itemAt(1).widget()
            w.setFocus()

            not getattr(w, 'selectedItems', _si)() and w.item(0) and w.item(0).setSelected(True)
            self.current_focus += 1
        elif event.key() == Qt.Key_Up:
            w = self.layout.itemAt(self.current_focus-1).itemAt(1).widget()
            w.setFocus()
            not getattr(w, 'selectedItems', _si)() and w.item(0) and w.item(0).setSelected(True)

            self.current_focus -= 1
        elif event.key() == Qt.Key_Left:
            if elem == self.keyboard:
                self.keyboard_layout.itemAt(0).widget().setFocus()
            else:
                self.window().categories.show()
                self.window().categories.categories_list.setFocus()
        elif event.key() == Qt.Key_Right:
            if elem == self.keyboard_tips:
                self.keyboard.setFocus()
        self.window().container.ensureWidgetVisible(w, 0, 0)

    def activate_item(self, item):
        if hasattr(item, 'video_id') and item.video_id:
            self.play(item.video_id, item.playlist_id, item.title, item.img)
        elif hasattr(item, 'channel_id') and item.channel_id:
            self.render_channel(item.channel_id)

    def play(self, video_id, playlist_id, title, img):
        data = self.api_data.copy()
        data.pop('browseId', None)
        data.update({
            'contentCheckOk': True,
            'racyCheckOk': True,
            'playlistId': playlist_id,
            'videoId': video_id
        })

        url = '{}{}?key={}'.format(conf.YOUTUBE_API, 'next', conf.YOUTUBE_API_KEY)
        res = self.post(url, data=json.dumps(data))
        res = res.json()
        cont = res['contents']['singleColumnWatchNextResults']['pivot']['pivot']
        cont = cont['contents'][0]['pivotShelfRenderer']['content']
        plst = cont['pivotHorizontalListRenderer']
        playlist = [['https://www.youtube.com/watch?v={}'.format(video_id), title, img]]
        rows = []

        for row in plst['items']:
            r = row.get('pivotVideoRenderer')
            if r:
                url = 'https://www.youtube.com/watch?v={}'.format(r['videoId'])
                playlist.append([url, r['title']['runs'][0]['text'], None])
                rows.append(row)

        images = self.cache_images(rows)
        for i, img in enumerate(images):
            playlist[i+1][2] = img

        self.window().player.playlist = playlist
        self.window().player.current_index = plst.get('selectedIndex', 0)
        self.window().player.play()
        self.window().setFocus()

    def render_channel(self, id):
        print('Render channel', id)

    def recomendations(self):
        url = '{}{}?key={}'.format(conf.YOUTUBE_API, 'browse', conf.YOUTUBE_API_KEY)
        data = self.api_data.copy()
        if self.rec_next and self.rec_continuation:
            data['context']['clickTracking'] = {"clickTrackingParams": self.rec_next}
            data['continuation'] = self.rec_continuation
            data.pop('browseId', None)
        res = self.post(url, data=json.dumps(data))
        res = res.json()

        if self.rec_next and self.rec_continuation:
            content = res['continuationContents']['sectionListContinuation']['contents']
            continuations = res['continuationContents']['sectionListContinuation'].get('continuations', [{}])
        else:
            content = res['contents']['sectionListRenderer']['contents']
            continuations = res['contents']['sectionListRenderer'].get('continuations', [{}])

        for row in content:
            section = QVBoxLayout()
            section_title = row['shelfRenderer'].get('title', '')
            if section_title:
                section_title = section_title['runs'][0]['text']

            section.addWidget(QLabel(section_title))

            list_widget = QListWidget(flow=QListView.LeftToRight)
            list_widget.setViewMode(QListView.IconMode)
            list_widget.setWrapping(False)
            list_widget.setWordWrap(True)
            list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            list_widget.setFixedHeight(400)
            list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
            list_widget.setIconSize(QSize(360, 480))

            items = self.render_row_result(row['shelfRenderer']['content']['horizontalListRenderer']['items'])
            for item in items:
                list_widget.addItem(item)

            list_widget.itemActivated.connect(self.activate_item)
            section.addWidget(list_widget)
            self.recs.append(section)
            self.layout.addLayout(section)
        self.rec_next = continuations[0].get('nextContinuationData', {}).get('clickTrackingParams')
        self.rec_continuation = continuations[0].get('nextContinuationData', {}).get('continuation')

    def search_activated(self, event):
        if event.key() == Qt.Key_Return:
            while self.layout.count() > 1:
                c = self.layout.takeAt(1)
                c.itemAt(0).widget().deleteLater()
                c.itemAt(1).widget().deleteLater()
            self.layout.addLayout(self.keyboard_layout)
            self.keyboard.show('ru')
            self.keyboard.setFocus()
            self.keyboard.layout.itemAt(0).widget().setFocus()
            self.layout.addLayout(self.results_layout)
            self.current_focus = 1
            self.tips_update()
        elif event.key() in (Qt.Key_Up, Qt.Key_Right, Qt.Key_Down, Qt.Key_Left):
            self.keyPressEvent(event)

    def tips_update(self):
        data = self.search_tips_data.copy()
        data['q'] = self.search.text()
        res = self.get(conf.YOUTUBE_SEARCH_TIPS_API, params=data)
        if res.ok:
            while self.keyboard_tips.count():
                self.keyboard_tips.takeItem(0)

            self.keyboard_tips.insertItems(0, [i[0] for i in res.json()[1]])

    def do_search(self):
        url = '{}{}?key={}'.format(conf.YOUTUBE_API, 'search', conf.YOUTUBE_API_KEY)
        data = self.api_data.copy()
        data['query'] = self.search.text()
        res = self.post(url, data=json.dumps(data))
        res = res.json()
        contents = res['contents']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']
        self.set_results(self.render_row_result(contents))
        self.results.setFocus()
        self.results.item(0).setSelected(True)

    def set_search_from_tip(self, item):
        self.search.clear()
        self.search.insert(item.text())
        self.search.submit()

    def set_results(self, items):
        while self.results.count():
            self.results.takeItem(0)
        for item in items:
            self.results.addItem(item)

    def render_row_result(self, row):
        items = []

        images = self.cache_images(row)

        for i, col in enumerate(row):
            if 'gridButtonRenderer' in col:
                item = QListWidgetItem(QIcon('img/nav/ontop.png'), 'ON TOP')
                item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
                item.video_id = None
                item.channel_id = None
                items.append(item)
                self.rec_end = True
                item.setSelected(True)
                break

            it = col.get('gridVideoRenderer')
            if not it:
                it = col.get('gridChannelRenderer')
            if not it:
                it = col.get('compactVideoRenderer', {})

            if not it:
                continue

            title = it['title']['runs'][0]['text'][:32]
            if len(title) < len(it['title']['runs'][0]['text']):
                title += '...'

            badges = it.get('badges')
            mode = ''
            if badges:
                mode = '[{}] '.format(badges[0]['textBadge']['label']['runs'][0]['text'])

            try:
                item = QListWidgetItem(QIcon(images[i]), '{}{}'.format(mode, title))
                img = images[i]
            except IndexError as e:
                item = QListWidgetItem(QIcon('img/youtube_default.png'), '{}{}'.format(mode, title))
                img = 'img/youtube_default.png'
                print(i, images)
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            item.video_id = it.get('videoId')
            item.channel_id = it.get('channelId')
            item.playlist_id = it.get('navigationEndpoint', {}).get('watchEndpoint', {}).get('playlistId')
            item.title = title
            item.img = img
            items.append(item)
        return items

    def cache_images(self, row):
        images = []
        pool = Pool(processes=16)
        for col in row:
            it = col.get('gridVideoRenderer')
            if not it:
                it = col.get('gridChannelRenderer')
            if not it:
                it = col.get('pivotVideoRenderer')
            if not it:
                it = col.get('compactVideoRenderer', {})

            if not it:
                continue

            thumb = it.get('thumbnail')
            if thumb:
                thumbs = thumb['thumbnails']
                thumb = thumbs[-1]['url']
                url = not thumb.startswith('http') and 'https:{}'.format(thumb) or thumb
                filepath = 'cache/{}'.format(thumb.replace('/', '_'))
                images.append((url, filepath))
            else:
                filepath = 'img/youtube_default.png'
                images.append((None, filepath))
        return pool.map(cache_image, images)
