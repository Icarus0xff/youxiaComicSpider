#!/usr/bin/python
# coding=utf-8

import os, requests
from bs4 import BeautifulSoup
import gevent
from gevent import monkey
monkey.patch_socket()
import time, re, random, queue


import mysql.connector

here = os.path.abspath(os.path.dirname(__file__))
pic_dir = os.path.join(here, 'ali213')
if not os.path.exists(pic_dir):
    os.mkdir(pic_dir)


chapter_base_url = 'http://manhua.fhxxw.cn/comic/6122'

sleep_time = 2

qsize = 8192
sql_stmt_queue = queue.Queue()

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Accept-Language': 'zh-CN,zh;q=0.8,en;q=0.6,zh-TW;q=0.4',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.116 Safari/537.36',
}

end = 0xABCD

def get_whole_ali213_chapter_index():
    url = 'http://manhua.fhxxw.cn/list/0-0-0-0-0-0-%s.html'
    pagenum = 448
    threads = []
    for i in range(1, pagenum+1):
        t = url % i
        threads.append(gevent.spawn(get_ali213_curpage_index, t))

    gevent.joinall(threads)
    sql_stmt_queue.put(end)



def get_ali213_curpage_index(chapter_url):
    gevent.sleep(random.randint(1,sleep_time))
    req = requests.get(chapter_url, headers = headers)
    soup = BeautifulSoup(req.text)
    threads = []
    base_url = 'http://manhua.fhxxw.cn'
    dict = {}
    for div in soup.findAll('div', {'class':'type_rbmh_con_con_img'}):
        try:
            url = div.a.get('href')
            name = div.a.get('title').encode('iso8859-1').decode('utf-8')
            if (url and name):
                dict[base_url+url] = name
        except:
            print('FUCK')
            continue
    for (k,v) in dict.items():
        sql_stmt = 'insert into ali213_manga_chapter' \
                   ' values (\'{}\',\'{}\')'.format(k, v)
        print(sql_stmt)
        sql_stmt_queue.put(sql_stmt)
    print('one thread is complete!')
    return

def insert_mangainfo_to_db():
    conn = mysql.connector.connect(host = 'localhost', user = 'root', passwd = '852456', db = 'manga')
    cursor = conn.cursor()
    while True:
        print("insert_mangainfo_to_db")
        if sql_stmt_queue.empty():
            gevent.sleep(sleep_time)
            continue
        sql_stmt = sql_stmt_queue.get_nowait()
        if sql_stmt == end:
            print("everything is done!")
            conn.close()
            return
        print('sql stmt ' +  sql_stmt)
        try:
            cursor.execute(sql_stmt)
            conn.commit()
        except mysql.connector.Error as e:
            if e.errno == 1062:
                print(e)
                continue
    conn.close()

def get_chapters_ali213(chapter_url):
    base_url_ali213 = 'http://manhua.fhxxw.cn'
    req = requests.get(chapter_url)
    soup = BeautifulSoup(req.text)
    threads = []
    chapterset = set()
    for li in soup.findAll('li'):
        try:
            title = li.a.get('title').encode('iso8859-1').decode('utf-8')
            print(title)
            if title not in chapterset:
                chapterset.add(title)
                url = '%s%s' % (base_url_ali213, li.a.get('href'))
                threads.append(gevent.spawn(download_chapters_ali213, title, url))
            else:
                print('already in the chapterset!')
                continue
        except:
            print ('fuck! some problem happen')
            continue
    gevent.joinall(threads)

def download_chapters_ali213(title, url):
    print ('download_chapters...... %s:%s' % (title, url))
    baseurl = 'http://manhua.fhxxw.cn'
    #delay some seconds preventing banned by the host
    threads = []
    map = {}
    map[title] = 'unfinished'
    chapter_dir = os.path.join(pic_dir, title)
    if not os.path.exists(chapter_dir):
        os.mkdir(chapter_dir)
    chapter_sub_url = url[:-5]
    time.sleep(sleep_time)
    content = requests.get(url).text
    searchObj = re.search(r'var imgpath=\'(.*)\'', content)
    pageNum = int(re.search(r'var pages=(.*);', content).group(1))
    if searchObj:
        img_url = baseurl + searchObj.group(1)
        temp = img_url
    for i in range(0, pageNum):
        img_url = temp + '%d' % i + '.jpg'
        file_name = os.path.join(chapter_dir, '%s.jpg' % i)
        gevent.spawn(save_pic_ali213, file_name, img_url).join()
    print('chapter %s is complete!' % title)


def save_pic_ali213(file_name, url):
    time.sleep(sleep_time)
    print ('save_pic......', file_name, url)
    if os.path.exists(file_name):
        print('already exists in the dir')
        return
    img_url = url
    print ('img_url', img_url)

    fail_count = 0
    while(1):
        resp = requests.get(img_url, headers=headers, stream=True)
        if resp.status_code == 200:
            with open(file_name, 'wb') as f:
                for chunk in resp.iter_content(1024):
                    f.write(chunk)
            return
        else:
            fail_count += 1
            if fail_count >= 20:
                print("failed to get the pic at last!")
                return
            print ('error', resp)
            time.sleep(sleep_time)
            print('try again!')

def main():
    #get_ali213_curpage_index('http://manhua.fhxxw.cn/list/0-0-0-0-0-0-1.html')
    main_threads = []
    main_threads.append(gevent.spawn(insert_mangainfo_to_db))
    main_threads.append(gevent.spawn(get_whole_ali213_chapter_index))
    #insert_mangainfo_to_db()
    #get_whole_ali213_chapter_index()
    gevent.joinall(main_threads)
    #get_chapters_ali213('http://manhua.fhxxw.cn/comic/13800')

if __name__ == '__main__':
    main()
