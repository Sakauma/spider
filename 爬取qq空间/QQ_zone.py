import re
import requests
import datetime
from selenium import webdriver
import time
from urllib import parse
from QQ_num import get_list
import os

# 获取cookie,g_tk,g_qzontoken这三个数据
def Login_QQ():
    '''gtk解密'''

    def getGTK(cookie):
        """ 根据cookie得到GTK """
        hashes = 5381
        for letter in cookie['p_skey']:
            hashes += (hashes << 5) + ord(letter)
        gtk = hashes & 0x7fffffff
        return gtk

    browser = webdriver.Chrome()
    url = "https://qzone.qq.com/"  
    browser.get(url)
    print("正在执行登录操作")
    time.sleep(10)
    print("睡眠时间结束, 登录")
    print(browser.title)  # 打印网页标题
    cookie = {}
    for element in browser.get_cookies():
        cookie[element['name']] = element['value']
    html = browser.page_source  
    pattern = re.compile(r'window\.g_qzonetoken = \(function\(\)\{ try\{return "(.*?)";\}')
    g_qzonetoken = re.search(pattern, html)
    g_qzonetoken = g_qzonetoken.group(1)
    gtk = getGTK(cookie) 
    browser.close()
    return (cookie, gtk, g_qzonetoken)
    
def parse_tid(tid,qq,gtk,headers):
    str_ = re.search('[^"]+',tid)#去除传入的“”
    tid = str_.group(0)
    like_url = 'https://user.qzone.qq.com/proxy/domain/r.qzone.qq.com/cgi-bin/user/qz_opcnt2?'
    unikey = 'http://user.qzone.qq.com/{0}/mood/{1}'.format(qq,tid)
    params = {
        "_stp": '',
        "unikey": unikey,
        'face': 0,
        'fupdate': 1,
        'g_tk': gtk,
        'qzonetoken': ''
    }
    like_url = like_url + parse.urlencode(params)
    like_content = requests.get(like_url, headers = headers, timeout=20).content.decode('utf-8')
    # like_content是所有的点赞信息，其中like字段为点赞数目，list是点赞的人列表，有的数据中list为空
    like_num = re.search('("like":)(\w+)',like_content)
    skim_num = re.search('("PRD":)(\w+)',like_content)
    try:#有些转发的说说会没有内容，导致报错
        like_num = like_num.group(2)
    except AttributeError as e:
        like_num = 0
    try:
        skim_num = skim_num.group(2)
    except AttributeError as e:
        skim_num = 0     
    return like_num , skim_num
    
def parse_mood(json):
    '''从返回的json中，提取我们想要的字段'''
    text = re.sub('"commentlist":.*?"conlist":', '', json)
    if text:
        myMood = {}
        myMood["isTransfered"] = False
        #Mood_cont:正文 ,date为日期,time为具体时间
        mood_cont = re.findall('\],"content":"(.*?)"', text)
        if len(mood_cont) == 2:  # 如果长度为2则判断为属于转载
            myMood["Mood_cont"] = "评语:" + mood_cont[0] + "--------->转载内容:" + mood_cont[1]  # 说说内容
            myMood["isTransfered"] = True
        elif len(mood_cont) == 1:
            myMood["Mood_cont"] = mood_cont[0]
        else:
            myMood["Mood_cont"] = ""
        if re.findall('"created_time":(\d+)', text):
            created_time = re.findall('"created_time":(\d+)', text)[0]
            temp_pubTime = datetime.datetime.fromtimestamp(int(created_time))
            temp_pubTime = temp_pubTime.strftime("%Y-%m-%d %H:%M:%S")
            dt = temp_pubTime.split(' ')
            time = dt[1]
            myMood['time'] = time
            date = dt[0]
            myMood['date'] = date
            cmtnum = re.findall('"cmtnum":(.*?),', text)[0]
            myMood['cmtnum'] = cmtnum
            tid = re.findall('"tid":(.*?),', text)[0]
            myMood['tid'] = tid
        
        return myMood

# 伪造浏览器头
headers = {
    'Host': 'user.qzone.qq.com',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.96 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive'
}
cookie, gtk, qzonetoken = Login_QQ()  # 通过登录函数取得cookies，gtk，qzonetoken
s = requests.session()  # 用requests初始化会话
qq_list = get_list().Login_QQ()

for qq in qq_list:  # 遍历qq号列表
    count = 0
    for p in range(0,50):
        pos = p * 20
        params = {
            'uin': qq,
            'ftype': '0',
            'sort': '0',
            'pos': pos ,  #爬取多少条说说
            'num': '20',
            'replynum': '100',
            'g_tk': gtk,
            'callback': '_preloadCallback',
            'code_version': '1',
            'format': 'jsonp',
            'need_private_comment': '1',
            'qzonetoken': qzonetoken,
        }

        response = s.request('GET',
                             'https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6?',
                           params=params, headers=headers, cookies=cookie)
        path = ''
        if response.status_code == 200:
            text = response.text
            textlist = re.split('\{"certified"', text)[1:]
            for json in textlist:
                myMood = parse_mood(json)
                tid = myMood['tid']
                like_num,skim_num = parse_tid(tid,qq,gtk,headers)
                like_num = '点赞人数  ' + str(like_num)
                skim_num = '浏览人数  ' + str(skim_num)
                file_name = '{0}QQ空间.txt'.format(qq)
                a_path = os.path.join(path, file_name)#将两个路径融合，得到存储的目的
                with open(str(a_path),'a') as f:
                    count += 1
                    lists =[]
                    lists = [myMood['Mood_cont'],myMood['date'],myMood['time'],myMood['cmtnum'],like_num,skim_num]
                    f.writelines('第%d条说说：%s \n\n'% (count,str(lists)))
#Mood_cont:正文 ,date为日期, comment_num为评论人数,like_num为点赞人数,skim_num为浏览人数

print('说说全部下载完成！')
